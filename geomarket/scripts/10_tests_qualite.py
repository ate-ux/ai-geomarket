"""Controles de qualite et tests automatises pour AI GeoMarket.

Couvre trois niveaux : integrite des donnees source, coherence des indicateurs
et des scores, comportement de l'agent conversationnel.
"""
import json
import os
import sys

import duckdb
import numpy as np
import pandas as pd

ROOT = "/workspace/k2RTwgspVmeo0wQvNz2KflqHTVC3/6b826994-78cb-4540-af88-ec7a5afea2e5"
DB = os.path.join(ROOT, "geomarket/db/geomarket.duckdb")
WEB = os.path.join(ROOT, "geomarket/web/data")
sys.path.insert(0, os.path.join(ROOT, "geomarket/scripts"))

resultats = []


def test(nom, condition, detail=""):
    resultats.append((nom, bool(condition), detail))
    marque = "OK  " if condition else "ECHEC"
    print(f"[{marque}] {nom}" + (f" ({detail})" if detail else ""))


con = duckdb.connect(DB)
con.execute("LOAD spatial;")

print("=" * 78)
print("A. INTEGRITE DES DONNEES SOURCE")
print("=" * 78)

n_bat = con.execute("SELECT count(*) FROM batiments").fetchone()[0]
test("A1. Les batiments sont charges", n_bat > 300000, f"{n_bat:,} batiments")

n_routes = con.execute("SELECT count(*) FROM routes").fetchone()[0]
test("A2. Le reseau routier est charge", n_routes > 20000, f"{n_routes:,} troncons")

n_poi = con.execute("SELECT count(*) FROM poi_points").fetchone()[0]
test("A3. Les points d'interet sont charges", n_poi > 5000, f"{n_poi:,} points")

n_arr = con.execute("SELECT count(*) FROM arrondissements").fetchone()[0]
test("A4. Les sept arrondissements sont presents", n_arr == 7, f"{n_arr} arrondissements")

n_q = con.execute("SELECT count(*) FROM quartiers").fetchone()[0]
test("A5. Les quartiers sont rattaches", n_q > 50, f"{n_q} quartiers")

n_manquants = con.execute(
    "SELECT count(*) FROM quartiers WHERE arrondissement IS NULL").fetchone()[0]
n_exclus = con.execute("SELECT count(*) FROM quartiers_hors_ville").fetchone()[0]
test("A6. Chaque quartier retenu a un arrondissement",
     n_manquants == 0,
     f"{n_manquants} sans rattachement, {n_exclus} quartier(s) peripherique(s) exclu(s)")

vides = con.execute("SELECT count(*) FROM batiments WHERE geom IS NULL").fetchone()[0]
test("A7. Aucune geometrie de batiment n'est vide", vides == 0, f"{vides} vides")

hors = con.execute("""
SELECT count(*) FROM batiments
WHERE ST_XMax(geom) < 11.30 OR ST_XMin(geom) > 11.70
   OR ST_YMax(geom) < 3.60 OR ST_YMin(geom) > 4.10
""").fetchone()[0]
test("A8. Les batiments restent dans l'emprise attendue", hors == 0, f"{hors} hors emprise")

print()
print("=" * 78)
print("B. GRILLE ET INDICATEURS")
print("=" * 78)

n_cell = con.execute("SELECT count(*) FROM grille").fetchone()[0]
test("B1. La grille hexagonale est construite", n_cell > 400, f"{n_cell} cellules")

dup = con.execute("""
SELECT count(*) FROM (
  SELECT cell_id FROM grille GROUP BY cell_id HAVING count(*) > 1
)""").fetchone()[0]
test("B2. Les identifiants de cellule sont uniques", dup == 0, f"{dup} doublons")

ind = con.execute("SELECT * FROM indicateurs_cellules").df()
test("B3. Chaque cellule a des indicateurs", len(ind) == n_cell,
     f"{len(ind)} lignes pour {n_cell} cellules")

negatifs = int((ind[["nb_batiments", "nb_poi_total", "longueur_route_m"]] < 0)
               .sum().sum())
test("B4. Aucun indicateur de comptage n'est negatif", negatifs == 0,
     f"{negatifs} valeurs negatives")

sans_bat = int((ind["nb_batiments"] == 0).sum())
test("B5. Les cellules sans batiment restent minoritaires",
     sans_bat < len(ind) * 0.1, f"{sans_bat} cellules sur {len(ind)}")

dans_grille = int(ind["arrondissement"].notna().sum())
test("B6. Chaque cellule est rattachee a un arrondissement",
     dans_grille == len(ind), f"{dans_grille} sur {len(ind)}")

print()
print("=" * 78)
print("C. SCORING ET POTENTIEL NET")
print("=" * 78)

sc = con.execute("SELECT * FROM scores_net").df()
test("C1. Le score brut est borne entre 0 et 100",
     sc["score_potentiel_brut"].between(0, 100).all(),
     f"min {sc['score_potentiel_brut'].min():.1f}, max {sc['score_potentiel_brut'].max():.1f}")

test("C2. Le score net est borne entre 0 et 100",
     sc["score_potentiel_net"].between(0, 100).all())

test("C3. Le score net ne depasse jamais le score brut",
     (sc["score_potentiel_net"] <= sc["score_potentiel_brut"] + 1e-6).all())

test("C4. La decote de cannibalisation reste dans les bornes",
     sc["decote_cannibalisation"].between(0, 0.35).all(),
     f"max {sc['decote_cannibalisation'].max()*100:.1f} %")

rangs = sorted(sc["rang_net"].tolist())
test("C5. Les rangs nets sont uniques et continus",
     rangs == list(range(1, len(sc) + 1)))

test("C6. Aucun score manquant", sc["score_potentiel_net"].notna().all())

sans_concur = int((sc["dist_min_m"] >= 2000).sum())
test("C7. Des zones sans concurrence proche existent", sans_concur > 100,
     f"{sans_concur} cellules a plus de 2 km")

# Les quatre axes doivent tous contribuer : aucun ne doit etre constant.
for axe in ("demande", "accessibilite", "attractivite", "concurrence"):
    s = sc[f"score_{axe}"]
    test(f"C8.{axe}. L'axe {axe} discrimine les cellules", s.std() > 0.01,
         f"ecart-type {s.std():.3f}")

print()
print("=" * 78)
print("D. SEGMENTATION ET MODELE")
print("=" * 78)

with open(os.path.join(ROOT, "geomarket/outputs/modele_ml.json"), encoding="utf-8") as fh:
    modele = json.load(fh)

seg = con.execute("SELECT * FROM segments_ml").df()
test("D1. La table de segmentation couvre toutes les cellules", len(seg) == n_cell,
     f"{len(seg)} lignes")

test("D2. Toutes les cellules ont un profil de marche",
     seg["profil_marche"].notna().all())

k = modele["segmentation"]["k_retenu"]
test("D3. Le nombre de profils est exploitable", 3 <= k <= 8, f"k = {k}")

test("D4. Le modele de substitution est performant",
     modele["substitut"]["r2_validation_croisee"] > 0.9,
     f"R2 = {modele['substitut']['r2_validation_croisee']}")

test("D5. L'erreur moyenne du modele reste faible",
     modele["substitut"]["mae_points"] < 3,
     f"{modele['substitut']['mae_points']} point")

test("D6. La performance est mesuree en validation croisee",
     modele["substitut"]["r2_validation_croisee"] < 1.0)

imp = modele["substitut"]["importance"]
test("D7. Les importances forment une distribution valide",
     abs(sum(x["importance"] for x in imp) - 1.0) < 0.01,
     f"somme {sum(x['importance'] for x in imp):.3f}")

test("D8. Plusieurs indicateurs contribuent au modele",
     sum(1 for x in imp if x["importance"] > 0.01) >= 5)

con.close()

print()
print("=" * 78)
print("E. AGENT CONVERSATIONNEL")
print("=" * 78)

import importlib
agent = importlib.import_module("07_agent_langage_naturel")

c1 = agent.extraire_criteres(
    "Trouve les 5 zones presentant le meilleur potentiel pour une nouvelle agence")
test("E1. L'agent extrait le nombre de zones demande", c1["nb_zones"] == 5)

z1 = agent.interroger(c1)
test("E2. L'agent retourne le nombre de zones demande", len(z1) == 5)

test("E3. Les zones sont classees par score decroissant",
     all(z1[i]["score_question"] >= z1[i + 1]["score_question"] for i in range(len(z1) - 1)))

test("E4. Chaque zone porte un identifiant de cellule", all(z.get("cell_id") for z in z1))

test("E5. Chaque zone est localisee", all(z.get("lat") and z.get("lon") for z in z1))

c2 = agent.extraire_criteres("Donne-moi les 3 meilleures zones a Yaounde V")
test("E6. L'agent reconnait un arrondissement",
     c2["arrondissements"] == ["Yaoundé V"], str(c2["arrondissements"]))

z2 = agent.interroger(c2)
test("E7. Le filtre geographique est applique",
     all(z["arrondissement"] == "Yaoundé V" for z in z2))

c3 = agent.extraire_criteres(
    "Top 4 des zones bien desservies par les routes, a plus de 2 km d'une banque")
test("E8. L'agent reconnait une distance minimale",
     c3["distance_min_m"] == 2000, str(c3["distance_min_m"]))

z3 = agent.interroger(c3)
test("E9. Le filtre de distance est applique",
     all(z["dist_min_m"] >= 2000 for z in z3))

c4 = agent.extraire_criteres("Ouvrir pres des commerces et des bureaux")
test("E10. L'agent module la ponderation d'attractivite",
     c4["ponderations"]["attractivite"] > agent.POIDS_DEFAUT["attractivite"])

test("E11. L'agent gere une demande sans nombre explicite",
     agent.extraire_criteres("Ou ouvrir une agence ?")["nb_zones"] == 5)

texte = agent.expliquer(c1, z1)
test("E12. La reponse est redigee en francais", "Ponderations" in texte or "pondera" in texte.lower())
test("E13. La reponse detaille chaque zone", texte.count("score") >= 5)

print()
print("=" * 78)
print("F. COHERENCE DES LIVRABLES WEB")
print("=" * 78)

for fichier in ("hexagones.geojson", "arrondissements.geojson", "quartiers.geojson",
                "routes.geojson", "agences.geojson", "equipements.geojson",
                "classement.json", "kpis.json", "modele.json",
                "arrondissements_scores.json"):
    p = os.path.join(WEB, fichier)
    test(f"F. {fichier} est present et lisible",
         os.path.exists(p) and os.path.getsize(p) > 100,
         f"{os.path.getsize(p)/1024:.0f} Ko" if os.path.exists(p) else "absent")

hexa = json.load(open(os.path.join(WEB, "hexagones.geojson"), encoding="utf-8"))
test("F11. La couche hexagonale exportee couvre toutes les cellules",
     len(hexa["features"]) == n_cell, f"{len(hexa['features'])} entites")

props = hexa["features"][0]["properties"]
for champ in ("cell_id", "arrondissement", "score_potentiel_net", "rang_net",
              "profil_marche", "dist_min_m"):
    test(f"F12.{champ}. Le champ {champ} est present dans l'export", champ in props)

kpi = json.load(open(os.path.join(WEB, "kpis.json"), encoding="utf-8"))
test("F13. Les indicateurs cles sont coherents avec la base",
     kpi["cellules"] == n_cell and kpi["batiments"] == n_bat)

print()
print("=" * 78)
reussis = sum(1 for _, ok, _ in resultats if ok)
total = len(resultats)
print(f"RESULTAT : {reussis}/{total} controles reussis")
echecs = [(n, d) for n, ok, d in resultats if not ok]
if echecs:
    print("\nControles en echec :")
    for n, d in echecs:
        print(f"  - {n} ({d})")
print("=" * 78)

txt = os.path.join(ROOT, "geomarket/outputs/sortie_tests.txt")
with open(txt, "w", encoding="utf-8") as fh:
    fh.write(f"AI GeoMarket : controles de qualite\n{'=' * 60}\n")
    for n, ok, d in resultats:
        fh.write(f"[{'OK' if ok else 'ECHEC'}] {n}" + (f" ({d})" if d else "") + "\n")
    fh.write(f"\nResultat : {reussis}/{total} controles reussis\n")
print(f"\nRapport ecrit dans {txt}")
sys.exit(0 if not echecs else 1)
