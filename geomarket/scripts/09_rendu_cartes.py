"""Rendu cartographique statique : figures de documentation et preuve visuelle."""
import json
import os

import duckdb
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

ROOT = "/workspace/k2RTwgspVmeo0wQvNz2KflqHTVC3/6b826994-78cb-4540-af88-ec7a5afea2e5"
DB = os.path.join(ROOT, "geomarket/db/geomarket.duckdb")
WEB = os.path.join(ROOT, "geomarket/web/data")
OUT = os.path.join(ROOT, "geomarket/outputs")
os.makedirs(OUT, exist_ok=True)

BLEU = ["#eef3f8", "#cfe0ee", "#a9c6e0", "#7ba7cd", "#4f86b8", "#2f6a9e",
        "#1b4b7a", "#0B2545"]
CMAP_BLEU = LinearSegmentedColormap.from_list("geoblue", BLEU)


def lire(nom):
    return gpd.read_file(os.path.join(WEB, nom))


hexagones = lire("hexagones.geojson")
arr = lire("arrondissements.geojson")
quartiers = lire("quartiers.geojson")
routes = lire("routes.geojson")
agences = lire("agences.geojson")

con = duckdb.connect(DB)
con.execute("LOAD spatial;")

fig, ax = plt.subplots(figsize=(11, 9))
quartiers.plot(ax=ax, facecolor="#f7f9fb", edgecolor="#e3e8ee", linewidth=0.4)
hexagones.plot(ax=ax, column="score_potentiel_net", cmap=CMAP_BLEU, linewidth=0.15,
               edgecolor="#ffffff", legend=True,
               legend_kwds={"label": "Potentiel net (0-100)", "shrink": 0.62})
routes.plot(ax=ax, color="#f0b429", linewidth=0.5, alpha=0.65)
arr.plot(ax=ax, facecolor="none", edgecolor="#0B2545", linewidth=1.4)
agences.plot(ax=ax, color="#b91c1c", markersize=16, zorder=6,
             edgecolor="white", linewidth=0.5)
for _, r in arr.iterrows():
    c = r.geometry.representative_point()
    ax.annotate(r["nom"], (c.x, c.y), fontsize=8.5, fontweight="bold",
                color="#0B2545", ha="center",
                bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="#c8d3de", lw=0.5))
top = hexagones.nlargest(10, "score_potentiel_net")
for i, (_, r) in enumerate(top.iterrows(), 1):
    c = r.geometry.representative_point()
    ax.annotate(str(i), (c.x, c.y), fontsize=7.5, fontweight="bold",
                color="#7c2d12", ha="center", va="center")
ax.set_title("AI GeoMarket : potentiel net par cellule hexagonale, Yaoundé",
             fontsize=13, fontweight="bold", color="#0B2545", pad=12)
ax.text(0.01, 0.015, "Cercles rouges : agences bancaires existantes. "
        "Chiffres : top 10 des zones.", transform=ax.transAxes,
        fontsize=8.5, color="#5b6b7c")
ax.set_axis_off()
plt.tight_layout()
fig.savefig(os.path.join(OUT, "carte_potentiel.png"), dpi=135, bbox_inches="tight")
plt.close(fig)
print("carte_potentiel.png")

fig, ax = plt.subplots(figsize=(11, 9))
routes[routes["classe"].isin(["motorway", "trunk", "primary"])].plot(
    ax=ax, color="#94a3b8", linewidth=0.6)
hexagones[hexagones["dist_min_m"] >= 2000].plot(
    ax=ax, color="#15803d", alpha=0.55, linewidth=0.15, edgecolor="white")
hexagones[(hexagones["dist_min_m"] > 1000) & (hexagones["dist_min_m"] < 2000)].plot(
    ax=ax, color="#f59e0b", alpha=0.45, linewidth=0.15, edgecolor="white")
hexagones[hexagones["dist_min_m"] <= 1000].plot(
    ax=ax, color="#b91c1c", alpha=0.4, linewidth=0.15, edgecolor="white")
agences.plot(ax=ax, color="#7f1d1d", markersize=22, edgecolor="white",
             linewidth=0.6, zorder=6)
arr.plot(ax=ax, facecolor="none", edgecolor="#0B2545", linewidth=1.3)
ax.legend(handles=[
    mpatches.Patch(color="#b91c1c", label="banque a moins de 1 km"),
    mpatches.Patch(color="#f59e0b", label="banque entre 1 et 2 km"),
    mpatches.Patch(color="#15803d", label="aucune banque a moins de 2 km"),
], loc="lower left", fontsize=9, framealpha=0.95)
n_libres = len(hexagones[hexagones["dist_min_m"] >= 2000])
ax.set_title("Zones de couverture concurrentielle a Yaounde",
             fontsize=13, fontweight="bold", color="#0B2545", pad=12)
ax.text(0.01, 0.965, f"{n_libres} cellules a plus de 2 km d'une agence bancaire",
        transform=ax.transAxes, fontsize=9, color="#5b6b7c")
ax.set_axis_off()
plt.tight_layout()
fig.savefig(os.path.join(OUT, "carte_concurrence.png"), dpi=135, bbox_inches="tight")
plt.close(fig)
print("carte_concurrence.png")

fig, ax = plt.subplots(figsize=(11, 9))
quartiers.plot(ax=ax, facecolor="#fbfcfd", edgecolor="#e7ecf1", linewidth=0.4)
profils = list(hexagones["profil_marche"].dropna().unique())
palette = ["#dbe4ee", "#9fbcd6", "#4f86b8", "#0B2545", "#6b7280", "#a16207", "#15803d"]
blocs = []
for p, col in zip(sorted(profils), palette):
    sub = hexagones[hexagones["profil_marche"] == p]
    sub.plot(ax=ax, color=col, linewidth=0.15, edgecolor="white")
    blocs.append(mpatches.Patch(color=col, label=f"{p} ({len(sub)})"))
arr.plot(ax=ax, facecolor="none", edgecolor="#0B2545", linewidth=1.2)
ax.legend(handles=blocs, loc="lower left", fontsize=8.5, framealpha=0.95)
ax.set_title("Profils de marche identifies par segmentation",
             fontsize=13, fontweight="bold", color="#0B2545", pad=12)
ax.set_axis_off()
plt.tight_layout()
fig.savefig(os.path.join(OUT, "carte_profils.png"), dpi=135, bbox_inches="tight")
plt.close(fig)
print("carte_profils.png")

scores = json.load(open(os.path.join(WEB, "arrondissements_scores.json"), encoding="utf-8"))
fig, ax = plt.subplots(figsize=(10, 4.6))
noms = [s["arrondissement"].replace("Yaoundé ", "") for s in scores]
vals = [s["score_moyen"] for s in scores]
ncell = [s["nb_cellules"] for s in scores]
barres = ax.bar(noms, vals, color="#1b4b7a", width=0.62)
for b, v, n in zip(barres, vals, ncell):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.8, f"{v}\n({n} cell.)",
            ha="center", fontsize=8.5, color="#0B2545")
ax.set_ylabel("Potentiel net moyen")
ax.set_ylim(0, max(vals) * 1.28)
ax.set_title("Potentiel net moyen par arrondissement de Yaounde",
             fontsize=13, fontweight="bold", color="#0B2545")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.grid(axis="y", alpha=0.2)
plt.tight_layout()
fig.savefig(os.path.join(OUT, "carte_arrondissements.png"), dpi=135, bbox_inches="tight")
plt.close(fig)
print("carte_arrondissements.png")

modele = json.load(open(os.path.join(OUT, "modele_ml.json"), encoding="utf-8"))
imp = modele["substitut"]["importance"][:12][::-1]
fig, ax = plt.subplots(figsize=(9, 5.4))
ax.barh([x["indicateur"] for x in imp], [x["importance"] for x in imp], color="#4f86b8")
ax.set_xlabel("Importance dans le modele")
ax.set_title("Indicateurs determinants du potentiel", fontsize=13,
             fontweight="bold", color="#0B2545")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.grid(axis="x", alpha=0.2)
plt.tight_layout()
fig.savefig(os.path.join(OUT, "graphique_importance.png"), dpi=135, bbox_inches="tight")
plt.close(fig)
print("graphique_importance.png")

con.close()
print("Figures generees dans", OUT)
