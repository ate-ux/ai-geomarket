"""Agent en langage naturel pour AI GeoMarket.

L'agent traduit une demande exprimee en francais en criteres ponderes,
interroge la base spatiale DuckDB, puis restitue un classement argumente.

Le moteur est deterministe et local : aucune API externe n'est requise.
"""
import re
import unicodedata

import duckdb
import pandas as pd

DB = ("/workspace/k2RTwgspVmeo0wQvNz2KflqHTVC3/6b826994-78cb-4540-af88-ec7a5afea2e5"
      "/geomarket/db/geomarket.duckdb")

POIDS_DEFAUT = {"demande": 0.40, "accessibilite": 0.25,
                "attractivite": 0.20, "concurrence": 0.15}

AXES = {
    "demande": ["dens_bat_km2", "dens_batie_m2_km2", "nb_education",
                "nb_sante", "nb_lieux_culte"],
    "accessibilite": ["dens_routiere_m_km2", "longueur_principale_m",
                      "nb_axes_structurants", "nb_transport"],
    "attractivite": ["dens_commerces_km2", "nb_commerces", "nb_restauration",
                     "nb_bureaux", "nb_loisirs"],
    "concurrence": ["nb_banques"],
}

MOTS_CLES = [
    (r"\bpopulation\b|\bdemograph|\bdensite|habitants|clients potentiels|volume",
     {"demande": +0.20}),
    (r"\brevenu|\bsolvab|pouvoir d'achat|aise|richesse|premium|haut de gamme",
     {"demande": +0.10, "attractivite": +0.15}),
    (r"accessible|accessibilite|\broute|\bvoirie|transport|\baxe|\bcarrefour|desserte",
     {"accessibilite": +0.25}),
    (r"central|centre-ville|hypercentre|coeur|dense|animation|commerce|boutique|marche",
     {"attractivite": +0.25}),
    (r"concurrence|concurrent|rivaux|banques en place|deja implant|saturation|cannibalisation",
     {"concurrence": +0.20}),
    (r"peu de concurrence|zone vierge|non desservi|non couvert|sans banque|opportunite",
     {"concurrence": +0.25, "demande": +0.10}),
    (r"ecole|education|universite|etudiant|jeune|scolaris|formation|lycee|college",
     {"demande": +0.05, "attractivite": +0.10}),
    (r"sante|hospital|clinique|pharmacie|dispensaire|medical",
     {"attractivite": +0.10}),
    (r"entreprise|bureau|affaires|professionnel|siege|pme|b2b",
     {"attractivite": +0.15, "accessibilite": +0.05}),
]

ARRONDISSEMENTS = {
    "yaounde i": "Yaoundé I", "yaounde 1": "Yaoundé I",
    "yaounde ii": "Yaoundé II", "yaounde 2": "Yaoundé II",
    "yaounde iii": "Yaoundé III", "yaounde 3": "Yaoundé III",
    "yaounde iv": "Yaoundé IV", "yaounde 4": "Yaoundé IV",
    "yaounde v": "Yaoundé V", "yaounde 5": "Yaoundé V",
    "yaounde vi": "Yaoundé VI", "yaounde 6": "Yaoundé VI",
    "yaounde vii": "Yaoundé VII", "yaounde 7": "Yaoundé VII",
}


def normaliser(texte: str) -> str:
    texte = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in texte if unicodedata.category(c) != "Mn")


def extraire_criteres(question: str) -> dict:
    """Traduit une question en criteres : ponderations, filtres, nombre de zones."""
    q = normaliser(question)
    ponderations = dict(POIDS_DEFAUT)
    explique = []
    for motif, deltas in MOTS_CLES:
        trouve = re.findall(motif, q)
        if trouve:
            for axe, delta in deltas.items():
                ponderations[axe] += delta
            explique.append(trouve[0])

    filtres_arr = [v for k, v in ARRONDISSEMENTS.items() if k in q]

    m = re.search(r"\b(\d{1,2})\s*(?:zones?|sites?|cellules?|quartiers?|emplacements?|"
                  r"meilleures?|meilleurs?|meilleur|top)\b", q)
    if not m:
        m = re.search(r"\btop\s*(\d{1,2})\b", q)
    nb_zones = max(1, min(int(m.group(1)) if m else 5, 25))

    dmin = re.search(r"(?:au moins|minimum|min|plus de|a plus de|superieur a)\s*"
                     r"(\d+(?:[.,]\d+)?)\s*(km|kilometre|m|metre)", q)
    dist_min = None
    if dmin:
        v = float(dmin.group(1).replace(",", "."))
        dist_min = v * 1000 if dmin.group(2).startswith(("km", "kilo")) else v

    return {
        "question": question,
        "ponderations": {k: round(v, 3) for k, v in ponderations.items()},
        "arrondissements": filtres_arr,
        "nb_zones": nb_zones,
        "distance_min_m": dist_min,
        "criteres_reconnus": sorted(set(explique)),
    }


def interroger(criteres: dict, table: str = "segments_ml") -> "list[dict]":
    """Execute la requete de classement et renvoie les zones retenues."""
    p = criteres["ponderations"]
    total = sum(p.values()) or 1.0
    p = {k: v / total for k, v in p.items()}

    con = duckdb.connect(DB)
    con.execute("LOAD spatial;")
    df = con.execute(f"SELECT * FROM {table}").df()
    con.close()

    def pct(s):
        return s.rank(pct=True, method="average").fillna(0.0)

    scores = {}
    for axe, cols in AXES.items():
        cols = [c for c in cols if c in df.columns]
        scores[axe] = (pd.concat([pct(df[c].astype(float)) for c in cols], axis=1)
                       .mean(axis=1) if cols else 0.0)

    potentiel = (p["demande"] * scores["demande"]
                 + p["accessibilite"] * scores["accessibilite"]
                 + p["attractivite"] * scores["attractivite"]
                 - p["concurrence"] * scores["concurrence"])
    plancher = -p["concurrence"]
    df["score_question"] = (((potentiel - plancher) / (1 - plancher)) * 100
                            ).clip(0, 100).round(2)

    if criteres["arrondissements"]:
        df = df[df["arrondissement"].isin(criteres["arrondissements"])]
    if criteres["distance_min_m"]:
        df = df[df["dist_min_m"] >= criteres["distance_min_m"]]

    df = df.sort_values("score_question", ascending=False).head(criteres["nb_zones"])
    cols = ["cell_id", "arrondissement", "profil_marche", "lat", "lon",
            "score_question", "score_potentiel_net", "dist_min_m",
            "enseigne_plus_proche", "nb_commerces", "nb_education", "nb_sante",
            "dens_routiere_m_km2", "dens_bat_km2"]
    cols = [c for c in cols if c in df.columns]
    return df[cols].round(2).to_dict(orient="records")


def expliquer(criteres: dict, zones: "list[dict]") -> str:
    """Redige une reponse en francais, structuree et citable."""
    p = criteres["ponderations"]
    total = sum(p.values()) or 1.0
    pct = {k: round(v / total * 100) for k, v in p.items()}
    lignes = []
    lignes.append("Analyse de la demande : " + criteres["question"].strip())
    lignes.append("")
    lignes.append("Criteres retenus et ponderations")
    libelles = {"demande": "demande (densite batie, equipements publics)",
                "accessibilite": "accessibilite (reseau routier, transports)",
                "attractivite": "attractivite (commerce, bureaux, loisirs)",
                "concurrence": "pression concurrentielle (penalite)"}
    for axe, val in pct.items():
        lignes.append(f"  - {libelles[axe]} : {val} %")
    if criteres["arrondissements"]:
        lignes.append(f"  - Filtre : {', '.join(criteres['arrondissements'])}")
    if criteres["distance_min_m"]:
        lignes.append(f"  - Distance minimale a un concurrent : "
                      f"{criteres['distance_min_m']:.0f} m")
    if criteres["criteres_reconnus"]:
        lignes.append(f"  - Termes reconnus : {', '.join(criteres['criteres_reconnus'])}")

    lignes.append("")
    lignes.append(f"{len(zones)} zones recommandees, classees par potentiel")
    for i, z in enumerate(zones, 1):
        lignes.append(
            f"  {i}. {z['arrondissement']} ({z['profil_marche']}) - "
            f"score {z['score_question']:.1f}/100\n"
            f"     coordonnees {z['lat']:.5f}, {z['lon']:.5f} ; "
            f"{int(z['nb_commerces'])} commerces, {int(z['nb_education'])} etablissements "
            f"scolaires, {int(z['nb_sante'])} structures de sante ;\n"
            f"     concurrent le plus proche : {z['enseigne_plus_proche']} "
            f"a {z['dist_min_m']:.0f} m"
        )
    lignes.append("")
    lignes.append("Lecture : le score agrege les quatre axes avec les ponderations "
                  "ci-dessus. Il s'appuie sur des proxys ouverts (densite batie OSM, "
                  "reseau routier, equipements), et non sur des donnees de revenu "
                  "fines, qui ne sont pas disponibles au niveau quartier.")
    return "\n".join(lignes)


def repondre(question: str) -> dict:
    criteres = extraire_criteres(question)
    zones = interroger(criteres)
    return {"criteres": criteres, "zones": zones,
            "reponse": expliquer(criteres, zones)}


if __name__ == "__main__":
    exemples = [
        "Trouve les 5 zones presentant le meilleur potentiel pour une nouvelle agence",
        "Ou ouvrir une agence accessible avec beaucoup de commerces et peu de concurrence ?",
        "Donne-moi les 3 meilleures zones a Yaounde V pour une clientele aisee",
        "Top 4 des zones bien dessertees par les routes, a plus de 2 km d'une banque",
    ]
    for q in exemples:
        print("=" * 78)
        print(repondre(q)["reponse"])
        print()
