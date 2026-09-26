"""Construction de la base spatiale DuckDB pour AI GeoMarket.

Charge les couches OSM (limites, routes, batiments, POI) dans une base DuckDB
avec extension spatiale, colonnes geometriques et index.
"""
import os
import time

import duckdb
import geopandas as gpd

ROOT = "/workspace/k2RTwgspVmeo0wQvNz2KflqHTVC3/6b826994-78cb-4540-af88-ec7a5afea2e5"
GEO = os.path.join(ROOT, "raw_data/geo")
DB = os.path.join(ROOT, "geomarket/db/geomarket.duckdb")

os.makedirs(os.path.dirname(DB), exist_ok=True)
if os.path.exists(DB):
    os.remove(DB)
con = duckdb.connect(DB)
con.execute("INSTALL spatial; LOAD spatial;")

t0 = time.time()


def load(name, path, keep_cols=None, simplify=0.0):
    gdf = gpd.read_file(path)
    if gdf.empty:
        print(f"  {name}: fichier vide, ignore")
        return 0
    if keep_cols:
        cols = [c for c in keep_cols if c in gdf.columns]
        gdf = gdf[cols + ["geometry"]]
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")
    if simplify:
        gdf["geometry"] = gdf.geometry.simplify(simplify, preserve_topology=True)
    gdf["geometry"] = gdf.geometry.apply(
        lambda g: g.wkt if g is not None and not g.is_empty else None)
    gdf = gdf[gdf["geometry"].notna()]
    con.register("_tmp", gdf)
    con.execute(f"CREATE OR REPLACE TABLE {name} AS "
                f"SELECT * EXCLUDE (geometry), ST_GeomFromText(geometry) AS geom FROM _tmp")
    con.unregister("_tmp")
    n = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
    print(f"  {name}: {n:,} entites")
    return n


print("Chargement des couches OSM dans DuckDB...")
load("limites", os.path.join(GEO, "limites_administratives.geojson"),
     ["osm_id", "nom", "niveau", "population"])
load("routes", os.path.join(GEO, "routes.geojson"),
     ["osm_id", "nom", "classe", "voies", "surface", "pont", "sens_unique"])
load("points_interet", os.path.join(GEO, "points_interet.geojson"),
     ["osm_id", "categorie", "name", "amenity", "brand", "source"])
load("lieux", os.path.join(GEO, "lieux.geojson"),
     ["osm_id", "name", "place", "population"])

print("Chargement des batiments (couche volumineuse)...")
load("batiments", os.path.join(GEO, "batiments.geojson"),
     ["osm_id", "type_batiment", "niveaux", "usage"])

con.execute("""
CREATE OR REPLACE TABLE arrondissements AS
SELECT osm_id, nom, niveau, TRY_CAST(population AS BIGINT) AS population, geom
FROM limites WHERE niveau = 8 AND nom LIKE 'Yaound%'
""")
# Les limites de niveau 10 de l'emprise comprennent des quartiers peripheriques
# situes hors des sept arrondissements de Yaounde (par exemple NTOUTMEVOUM, a
# environ 4 km a l'est de l'emprise urbaine). Ces quartiers sont exclus de
# l'analyse : ils ne relevent pas de la zone etudiee. Le nombre d'exclus est
# conserve pour la tracabilite.
con.execute("""
CREATE OR REPLACE TABLE quartiers_hors_ville AS
SELECT l.osm_id, l.nom, l.geom
FROM limites l
WHERE l.niveau = 10
  AND NOT EXISTS (
      SELECT 1 FROM arrondissements a
      WHERE ST_Contains(a.geom, ST_Centroid(l.geom))
  )
""")
con.execute("""
CREATE OR REPLACE TABLE quartiers AS
SELECT l.osm_id, l.nom, l.niveau, TRY_CAST(l.population AS BIGINT) AS population,
       a.nom AS arrondissement, l.geom
FROM limites l
JOIN arrondissements a
  ON ST_Contains(a.geom, ST_Centroid(l.geom))
WHERE l.niveau = 10
""")
print("  quartiers hors des arrondissements (exclus) :",
      con.execute("SELECT count(*) FROM quartiers_hors_ville").fetchone()[0])
con.execute("""
CREATE OR REPLACE TABLE poi_points AS
SELECT osm_id, categorie, name, amenity, brand, ST_Centroid(geom) AS geom
FROM points_interet
""")
print("  arrondissements:",
      con.execute("SELECT count(*) FROM arrondissements").fetchone()[0])
print("  quartiers:", con.execute("SELECT count(*) FROM quartiers").fetchone()[0])
print("  poi_points:", con.execute("SELECT count(*) FROM poi_points").fetchone()[0])

print("Creation des index spatiaux...")
for tbl in ("arrondissements", "quartiers", "routes", "batiments",
            "poi_points", "limites"):
    try:
        con.execute(f"CREATE INDEX idx_{tbl} ON {tbl} USING RTREE (geom)")
        print(f"  index {tbl}: OK")
    except Exception as e:
        print(f"  index {tbl}: {type(e).__name__} {str(e)[:70]}")

info = con.execute("""
SELECT ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e)
FROM (SELECT ST_Extent(geom) AS e FROM arrondissements)
""").fetchone()
print("Emprise des arrondissements (lon/lat):", [round(v, 4) for v in info])

con.execute("""
CREATE OR REPLACE TABLE arrondissements_km2 AS
SELECT nom,
       ST_Area(ST_Transform(geom, 'EPSG:4326', 'EPSG:32632')) / 1e6 AS superficie_km2
FROM arrondissements
""")
print(con.execute("SELECT nom, round(superficie_km2,1) AS km2 "
                  "FROM arrondissements_km2 ORDER BY km2 DESC").df().to_string(index=False))

print(f"\nBase construite en {time.time()-t0:.1f}s -> {DB}")
print("Tables:", [r[0] for r in con.execute("SHOW TABLES").fetchall()])
con.close()
