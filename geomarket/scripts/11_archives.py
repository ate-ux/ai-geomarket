"""Constitution des archives livrables.

Deux archives complementaires :
- la version complete : code, carte web, documentation, figures et resultats,
  sans la base DuckDB ni l'extrait OSM brut, tous deux reconstruits par les
  scripts (environ 20 secondes pour la base) ;
- la version legere : documentation, figures compressees et resultats, sous la
  contrainte de telechargement de l'environnement cible.
"""
import io
import os
import zipfile

from PIL import Image

ROOT = "/workspace/k2RTwgspVmeo0wQvNz2KflqHTVC3/6b826994-78cb-4540-af88-ec7a5afea2e5"
SRC = os.path.join(ROOT, "geomarket")
OUT = os.path.join(ROOT, "outputs")
os.makedirs(OUT, exist_ok=True)

# Dossiers et fichiers exclus de l'archive complete : volumineux et
# integralement reconstruits par les scripts du depot.
EXCLUS_DIRS = {os.path.join(SRC, "db"), os.path.join(SRC, "data"),
               os.path.join(SRC, "scripts", "__pycache__")}
EXCLUS_FICH = {".DS_Store"}

# --- Archive complete ------------------------------------------------------
complet = os.path.join(OUT, "ai_geomarket_complet.zip")
with zipfile.ZipFile(complet, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for dossier, sous, fichiers in os.walk(SRC):
        if any(dossier.startswith(d) for d in EXCLUS_DIRS):
            continue
        sous[:] = [s for s in sous
                   if not any(os.path.join(dossier, s).startswith(d)
                              for d in EXCLUS_DIRS)]
        for f in fichiers:
            if f.endswith(".pyc") or f in EXCLUS_FICH:
                continue
            plein = os.path.join(dossier, f)
            z.write(plein, os.path.relpath(plein, os.path.dirname(SRC)))
    z.writestr("ai_geomarket/LISEZ_MOI.txt", (
        "AI GeoMarket, archive complete\n"
        "==============================\n\n"
        "Contenu : scripts Python, couches GeoJSON du projet, carte web\n"
        "interactive, documentation, figures et resultats.\n\n"
        "Non inclus, car reconstruits par les scripts :\n"
        "  - la base spatiale DuckDB (geomarket/db/), environ 20 secondes de calcul ;\n"
        "  - l'extrait OpenStreetMap brut du Cameroun (213 Mo), a telecharger\n"
        "    depuis Geofabrik (adresse dans le README).\n\n"
        "Pour reconstruire la chaine complete, suivre le README.md.\n"
    ))
taille = os.path.getsize(complet)
print(f"ai_geomarket_complet.zip : {taille/1e6:.2f} Mo")

# --- Archive legere -------------------------------------------------------
# Les cartes sont reduites en JPEG compresse pour respecter la limite de
# telechargement de l'environnement cible.
leger = os.path.join(OUT, "ai_geomarket_leger.zip")

IMAGES = [
    ("outputs/carte_potentiel.png", "cartes/carte_potentiel.jpg", (1240, 1015), 58),
    ("outputs/carte_concurrence.png", "cartes/carte_concurrence.jpg", (1240, 1015), 58),
    ("outputs/carte_profils.png", "cartes/carte_profils.jpg", (1120, 920), 56),
    ("outputs/carte_arrondissements.png", "cartes/carte_arrondissements.jpg", (1120, 515), 58),
    ("outputs/graphique_importance.png", "cartes/graphique_importance.jpg", (1000, 600), 58),
]
TEXTES = [
    ("README.md", "README.md"),
    ("docs/modele_donnees.md", "docs/modele_donnees.md"),
    ("docs/methodologie.md", "docs/methodologie.md"),
    ("docs/dictionnaire_indicateurs.md", "docs/dictionnaire_indicateurs.md"),
    ("outputs/sortie_tests.txt", "resultats/tests_qualite.txt"),
    ("outputs/agent_demo.txt", "resultats/agent_demo.txt"),
    ("outputs/modele_ml.json", "resultats/modele_ml.json"),
    ("outputs/poids_scoring.json", "resultats/poids_scoring.json"),
]

with zipfile.ZipFile(leger, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for src_rel, dest, taille_max, qualite in IMAGES:
        plein = os.path.join(SRC, src_rel)
        if not os.path.exists(plein):
            print(f"  absent, ignore : {src_rel}")
            continue
        im = Image.open(plein).convert("RGB")
        im.thumbnail(taille_max, Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=qualite, optimize=True, progressive=True)
        z.writestr("ai_geomarket_leger/" + dest, buf.getvalue())
    for src_rel, dest in TEXTES:
        plein = os.path.join(SRC, src_rel)
        if os.path.exists(plein):
            z.write(plein, "ai_geomarket_leger/" + dest)
        else:
            print(f"  absent, ignore : {src_rel}")
    z.writestr("ai_geomarket_leger/LISEZ_MOI.txt", (
        "AI GeoMarket, version legere\n"
        "============================\n\n"
        "Cette archive contient la documentation, les cinq figures, les mesures\n"
        "du projet et les resultats des tests. Le code complet et la carte\n"
        "interactive se trouvent dans ai_geomarket_complet.zip.\n\n"
        "Le systeme repond a la question : ou ouvrir une nouvelle agence bancaire\n"
        "a Yaounde. Il s'appuie sur 431 cellules hexagonales de 0,74 km2,\n"
        "24 indicateurs et quatre axes de decision ponderes (demande 40 pour cent,\n"
        "accessibilite 25, attractivite 20, concurrence 15 en penalite), plus une\n"
        "decote de cannibalisation allant jusqu'a 35 pour cent dans un rayon de 1 km.\n\n"
        "Qualite : 64 controles sur 64 reussis.\n"
    ))
t = os.path.getsize(leger)
print(f"ai_geomarket_leger.zip   : {t/1024:.0f} Ko "
      f"({'ok' if t < 400_000 else 'au-dessus de 400 Ko'})")
