"""Modele d'apprentissage : segmentation et modele supervise de substitution.

1. Segmentation non supervisee (KMeans) : regroupe les cellules en profils de
   marche homogenes. Le nombre de classes est choisi par la methode du coude et
   la silhouette.
2. Modele supervise de substitution : un modele d'arbres (GradientBoosting)
   apprend a reproduire le score composite a partir des seuls indicateurs bruts.
"""
import json
import os

import duckdb
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score, silhouette_score
from sklearn.model_selection import KFold, cross_val_predict

ROOT = "/workspace/k2RTwgspVmeo0wQvNz2KflqHTVC3/6b826994-78cb-4540-af88-ec7a5afea2e5"
DB = os.path.join(ROOT, "geomarket/db/geomarket.duckdb")
OUT = os.path.join(ROOT, "geomarket/outputs")
os.makedirs(OUT, exist_ok=True)

FEATURES = [
    "nb_batiments", "dens_bat_km2", "dens_batie_m2_km2",
    "dens_routiere_m_km2", "longueur_principale_m", "nb_axes_structurants",
    "nb_transport", "dens_commerces_km2", "nb_commerces", "nb_restauration",
    "nb_bureaux", "nb_loisirs", "nb_education", "nb_sante", "nb_lieux_culte",
    "nb_banques", "dist_min_m",
]
CIBLE = "score_potentiel_net"

con = duckdb.connect(DB)
con.execute("LOAD spatial;")
df = con.execute("SELECT * FROM scores_net ORDER BY cell_id").df()
print(f"Cellules chargees : {len(df)}")

X = df[FEATURES].astype(float).fillna(0.0)
y = df[CIBLE].astype(float)

print("Segmentation : evaluation du nombre de classes...")
Xr = X.rank(pct=True)
inerties, silhouettes = {}, {}
for k in range(2, 9):
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    lab = km.fit_predict(Xr)
    inerties[k] = float(km.inertia_)
    silhouettes[k] = round(float(silhouette_score(Xr, lab)), 4)
for k in inerties:
    print(f"  k={k}  inertie={inerties[k]:12.1f}  silhouette={silhouettes[k]}")

k_sil = max(silhouettes, key=silhouettes.get)
print(f"Optimum statistique : k={k_sil} (silhouette={silhouettes[k_sil]})")
candidats = {k: v for k, v in silhouettes.items() if k >= 4}
k_opt = max((k for k, v in candidats.items()
             if abs(v - silhouettes[k_sil]) < 0.06), key=lambda k: silhouettes[k])
print(f"k retenu pour l'exploitation : k={k_opt} (silhouette={silhouettes[k_opt]})")

km = KMeans(n_clusters=k_opt, n_init=10, random_state=42)
df["cluster"] = km.fit_predict(Xr)

profil = (df.groupby("cluster")
            .agg(nb_cellules=("cell_id", "count"),
                 arrondissement_dominant=("arrondissement", lambda s: s.value_counts().idxmax()),
                 score_moyen=(CIBLE, "mean"),
                 dens_bat_moy=("dens_bat_km2", "mean"),
                 dens_route_moy=("dens_routiere_m_km2", "mean"),
                 commerce_moy=("nb_commerces", "mean"),
                 distance_moy_m=("dist_min_m", "mean"))
            .round(1).sort_values("score_moyen"))
print("\nProfils de marche :")
print(profil.to_string())

noms_ordre = ["Zone peu equipee", "Peripherie residentielle",
              "Quartier d'activite mixte", "Centre structure commercant",
              "Coeur urbain dense", "Axe structurant majeur", "Hypercentre"]
ordres = list(profil.index)
etiquettes = {c: noms_ordre[min(i, len(noms_ordre) - 1)] for i, c in enumerate(ordres)}
df["profil_marche"] = df["cluster"].map(etiquettes)

print("\nEntrainement du modele de substitution (validation croisee 5 plis)...")
modele = GradientBoostingRegressor(n_estimators=300, learning_rate=0.05,
                                   max_depth=3, subsample=0.9, random_state=42)
cv = KFold(n_splits=5, shuffle=True, random_state=42)
pred_cv = cross_val_predict(modele, X, y, cv=cv)
r2 = r2_score(y, pred_cv)
mae = mean_absolute_error(y, pred_cv)
rmse = float(np.sqrt(np.mean((y - pred_cv) ** 2)))
print(f"  R2 (validation croisee) : {r2:.3f}")
print(f"  Erreur absolue moyenne  : {mae:.2f} points")
print(f"  Erreur quadratique      : {rmse:.2f} points")

modele.fit(X, y)
imp = (pd.DataFrame({"indicateur": FEATURES,
                     "importance": modele.feature_importances_})
       .sort_values("importance", ascending=False).round(4))
print("\nImportance des indicateurs (top 10) :")
print(imp.head(10).to_string(index=False))

df["score_predit_cv"] = pred_cv.round(2)
df["ecart"] = (df["score_predit_cv"] - df[CIBLE]).round(2)

cols = ["cell_id", "arrondissement", "lat", "lon", "profil_marche", "cluster",
        "score_potentiel_brut", "score_potentiel_net", "score_predit_cv",
        "ecart", "rang_net", "dist_min_m", "nb_dans_1km", "nb_dans_3km",
        "enseigne_plus_proche"] + FEATURES
cols = list(dict.fromkeys(cols))
res = df[cols].sort_values("rang_net")
con.register("_ml", res)
con.execute("CREATE OR REPLACE TABLE segments_ml AS SELECT * FROM _ml")
con.unregister("_ml")
con.close()

with open(os.path.join(OUT, "modele_ml.json"), "w", encoding="utf-8") as fh:
    json.dump({
        "segmentation": {
            "algorithme": "KMeans sur rangs percentiles",
            "k_retenu": int(k_opt),
            "silhouette": silhouettes[k_opt],
            "optimum_statistique": int(k_sil),
            "inerties": inerties,
            "profils": json.loads(profil.reset_index().to_json(orient="records")),
        },
        "substitut": {
            "algorithme": "GradientBoostingRegressor (300 arbres, profondeur 3)",
            "cible": CIBLE,
            "r2_validation_croisee": round(r2, 3),
            "mae_points": round(mae, 2),
            "rmse_points": round(rmse, 2),
            "note": ("Cible derivee du score composite : la performance mesure la "
                     "fidelite du substitut, pas une validation terrain."),
            "importance": json.loads(imp.to_json(orient="records")),
        },
    }, fh, ensure_ascii=False, indent=2)

print(f"\nTable segments_ml ecrite avec {len(res)} cellules.")
print(df["profil_marche"].value_counts().to_string())
print(f"Resultats enregistres dans {OUT}/modele_ml.json")
