"""Export des donnees de la base vers le format consomme par la carte web."""
import json
import os

import duckdb
import geopandas as gpd

ROOT = "/workspace/k2RTwgspVmeo0wQvNz2KflqHTVC3/6b826994-78cb-4540-af88-ec7a5afea2e5"
DB = os.path.join(ROOT, "geomarket/db/geomarket.duckdb")
WEB = os.path.join(ROOT, "geomarket/web/data")
os.makedirs(WEB, exist_ok=True)

con = duckdb.connect(DB)
con.execute("LOAD spatial;")

con.execute("""
CREATE OR REPLACE TABLE hex_export AS
SELECT s.cell_id, s.arrondissement, s.profil_marche, s.score_potentiel_brut,
       s.score_potentiel_net, s.rang_net, s.dist_min_m, s.enseigne_plus_proche,
       s.nb_batiments, s.dens_bat_km2, s.dens_routiere_m_km2, s.nb_commerces,
       s.nb_education, s.nb_sante, s.nb_banques, s.nb_restauration, s.nb_bureaux,
       s.nb_transport, s.nb_loisirs, s.nb_lieux_culte, s.nb_axes_structurants,
       s.longueur_principale_m, s.dens_commerces_km2, s.lat, s.lon, g.geom
FROM segments_ml s JOIN grille g USING (cell_id)
""")


def export_geojson(sql, path, name, simplify=0.0):
    gdf = con.execute(sql).df()
    wkbs = [bytes(g) if isinstance(g, (bytearray, memoryview)) else g
            for g in gdf["geom"]]
    gdf["geometry"] = gpd.GeoSeries.from_wkb(wkbs, crs="EPSG:4326")
    g = gpd.GeoDataFrame(gdf.drop(columns=["geom"]), geometry="geometry",
                         crs="EPSG:4326")
    if simplify:
        g["geometry"] = g.geometry.simplify(simplify, preserve_topology=True)
    g.to_file(path, driver="GeoJSON")
    print(f"  {name}: {len(g)} entites ({os.path.getsize(path)/1e6:.2f} Mo)")


print("Export des couches geographiques...")
export_geojson(
    "SELECT cell_id, arrondissement, profil_marche, score_potentiel_brut, "
    "score_potentiel_net, rang_net, round(dist_min_m) AS dist_min_m, "
    "enseigne_plus_proche, nb_batiments, round(dens_bat_km2) AS dens_bat_km2, "
    "round(dens_routiere_m_km2) AS dens_route_m_km2, nb_commerces, nb_education, "
    "nb_sante, nb_banques, nb_restauration, nb_bureaux, nb_transport, nb_loisirs, "
    "nb_lieux_culte, nb_axes_structurants, round(longueur_principale_m) AS longueur_principale_m, "
    "round(dens_commerces_km2,1) AS dens_commerces_km2, "
    "round(lat,6) AS lat, round(lon,6) AS lon, geom FROM hex_export",
    os.path.join(WEB, "hexagones.geojson"), "hexagones")

export_geojson("SELECT nom, niveau, geom FROM arrondissements ORDER BY nom",
               os.path.join(WEB, "arrondissements.geojson"), "arrondissements", 0.00008)
export_geojson("SELECT nom, arrondissement, geom FROM quartiers",
               os.path.join(WEB, "quartiers.geojson"), "quartiers", 0.00008)
export_geojson("""
SELECT nom, classe, geom FROM routes
WHERE classe IN ('motorway','trunk','primary','secondary','tertiary')
""", os.path.join(WEB, "routes.geojson"), "routes")
export_geojson("SELECT enseigne, name, geom FROM agences_existantes",
               os.path.join(WEB, "agences.geojson"), "agences")
export_geojson("""
SELECT categorie, name, geom FROM poi_points
WHERE categorie IN ('school','university','hospital','clinic','pharmacy',
                    'marketplace','shop_mall','shop_supermarket','bus_station')
""", os.path.join(WEB, "equipements.geojson"), "equipements")

classement = con.execute("""
SELECT rang_net, cell_id, arrondissement, profil_marche,
       round(score_potentiel_net,1) AS score, round(lat,5) AS lat,
       round(lon,5) AS lon, round(dist_min_m) AS dist_min_m, enseigne_plus_proche,
       nb_commerces, nb_education, nb_sante, nb_batiments,
       round(dens_bat_km2) AS dens_bat_km2, round(dens_routiere_m_km2) AS dens_route
FROM hex_export ORDER BY rang_net LIMIT 20
""").df().to_dict(orient="records")
with open(os.path.join(WEB, "classement.json"), "w", encoding="utf-8") as fh:
    json.dump(classement, fh, ensure_ascii=False, indent=1)

kpis = con.execute("""
SELECT
  (SELECT count(*) FROM batiments) AS batiments,
  (SELECT count(*) FROM routes) AS troncons_routiers,
  (SELECT count(*) FROM poi_points) AS points_interet,
  (SELECT count(*) FROM arrondissements) AS arrondissements,
  (SELECT count(*) FROM quartiers) AS quartiers,
  (SELECT count(*) FROM grille) AS cellules,
  (SELECT count(*) FROM agences_existantes) AS agences_concurrentes,
  (SELECT round(avg(score_potentiel_net),1) FROM hex_export) AS score_moyen,
  (SELECT round(max(score_potentiel_net),1) FROM hex_export) AS score_max,
  (SELECT round(sum(ST_Area(ST_Transform(geom,'EPSG:4326','EPSG:32632')))/1e6,1)
   FROM arrondissements) AS superficie_km2,
  (SELECT round(sum(surf_batie_m2)/1e6,1) FROM indicateurs_cellules) AS surface_batie_km2
""").df().to_dict(orient="records")[0]
with open(os.path.join(WEB, "kpis.json"), "w", encoding="utf-8") as fh:
    json.dump(kpis, fh, ensure_ascii=False, indent=1)
print("KPIs:", kpis)

moy_par_arr = con.execute("""
SELECT arrondissement, round(avg(score_potentiel_net),1) AS score_moyen,
       round(avg(score_potentiel_brut),1) AS score_brut,
       count(*) AS nb_cellules,
       round(avg(decote_cannibalisation)*100,1) AS decote_pct
FROM scores_net GROUP BY 1 ORDER BY score_moyen DESC
""").df().to_dict(orient="records")
with open(os.path.join(WEB, "arrondissements_scores.json"), "w", encoding="utf-8") as fh:
    json.dump(moy_par_arr, fh, ensure_ascii=False, indent=1)

src = os.path.join(ROOT, "geomarket/outputs/modele_ml.json")
with open(src, encoding="utf-8") as fh:
    modele = json.load(fh)
with open(os.path.join(WEB, "modele.json"), "w", encoding="utf-8") as fh:
    json.dump(modele, fh, ensure_ascii=False, indent=1)

con.close()
print("Export web termine.")
