"""Construction de la grille d'analyse hexagonale et calcul des indicateurs.

Decoupe Yaounde en cellules hexagonales H3 (resolution 8, environ 0,74 km2)
et calcule, pour chaque cellule, les indicateurs du scoring : densite batie,
reseau routier, attractivite (points d'interet), concurrence.
"""
import json
import os
import time

import duckdb
import h3
import pandas as pd

ROOT = "/workspace/k2RTwgspVmeo0wQvNz2KflqHTVC3/6b826994-78cb-4540-af88-ec7a5afea2e5"
DB = os.path.join(ROOT, "geomarket/db/geomarket.duckdb")
RES = 8

con = duckdb.connect(DB)
con.execute("LOAD spatial;")

bounds = con.execute("""
SELECT ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e)
FROM (SELECT ST_Extent(geom) AS e FROM arrondissements)
""").fetchone()
print(f"Emprise etudiee : lon {bounds[0]:.4f}..{bounds[2]:.4f} | "
      f"lat {bounds[1]:.4f}..{bounds[3]:.4f}")

arr = con.execute("SELECT nom, ST_AsGeoJSON(geom) AS gj FROM arrondissements").df()
cells = {}
for _, row in arr.iterrows():
    geom = json.loads(row["gj"])
    if geom["type"] == "Polygon":
        poly = h3.LatLngPoly([(c[1], c[0]) for c in geom["coordinates"][0]])
    else:
        poly = h3.LatLngMultiPoly(
            [[(c[1], c[0]) for c in ring] for ring in geom["coordinates"][0]])
    try:
        found = h3.polygon_to_cells(poly, RES)
    except AttributeError:
        found = h3.polyfill(poly, RES, geo_json_concr=False)
    for cell in found:
        cells.setdefault(cell, row["nom"])
print(f"Cellules H3 resolution {RES} : {len(cells):,}")

rows = []
for cell, arr_name in cells.items():
    boundary = h3.cell_to_boundary(cell)
    ring = [[lon, lat] for lat, lon in boundary]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    lat, lon = h3.cell_to_latlng(cell)
    rows.append({
        "cell_id": cell, "arrondissement": arr_name,
        "lat": lat, "lon": lon,
        "wkt": "POLYGON((" + ", ".join(f"{x} {y}" for x, y in ring) + "))",
        "area_km2": h3.cell_area(cell, unit="km^2"),
    })
cells_df = pd.DataFrame(rows)
con.register("_cells", cells_df)
con.execute("""
CREATE OR REPLACE TABLE grille AS
SELECT cell_id, arrondissement, lat, lon, area_km2, ST_GeomFromText(wkt) AS geom
FROM _cells
""")
con.unregister("_cells")
print("Table grille creee :",
      con.execute("SELECT count(*) FROM grille").fetchone()[0], "cellules")
con.execute("CREATE INDEX idx_grille ON grille USING RTREE (geom)")

t0 = time.time()

print("Calcul de la densite batie...")
con.execute("""
CREATE OR REPLACE TABLE ind_bati AS
SELECT g.cell_id,
       count(b.geom) AS nb_batiments,
       coalesce(sum(ST_Area(ST_Transform(b.geom, 'EPSG:4326', 'EPSG:32632'))), 0) AS surf_batie_m2,
       count(*) FILTER (WHERE b.usage IN ('commercial','retail')) AS nb_bat_commerces,
       count(*) FILTER (WHERE b.type_batiment IN ('apartments','residential','house','terrace')) AS nb_bat_residentiels
FROM grille g
LEFT JOIN batiments b ON ST_Intersects(g.geom, b.geom)
GROUP BY g.cell_id
""")

print("Calcul du reseau routier...")
con.execute("""
CREATE OR REPLACE TABLE ind_routes AS
SELECT g.cell_id,
       coalesce(sum(ST_Length(ST_Transform(rt.geom,'EPSG:4326','EPSG:32632'))),0) AS longueur_totale_m,
       coalesce(sum(ST_Length(ST_Transform(rt.geom,'EPSG:4326','EPSG:32632')))
                FILTER (WHERE rt.classe IN ('motorway','trunk','primary')), 0) AS longueur_principale_m,
       coalesce(sum(ST_Length(ST_Transform(rt.geom,'EPSG:4326','EPSG:32632')))
                FILTER (WHERE rt.classe IN ('secondary','tertiary')), 0) AS longueur_secondaire_m,
       count(*) FILTER (WHERE rt.classe IN ('motorway','trunk','primary','secondary','tertiary')) AS nb_axes_structurants
FROM grille g
LEFT JOIN routes rt ON ST_Intersects(g.geom, rt.geom)
GROUP BY g.cell_id
""")

print("Calcul des points d'interet par cellule...")
con.execute("""
CREATE OR REPLACE TABLE ind_poi AS
SELECT g.cell_id,
       count(p.geom) AS nb_poi_total,
       count(*) FILTER (WHERE p.categorie IN ('school','university','college','kindergarten','office_educational_institution','training')) AS nb_education,
       count(*) FILTER (WHERE p.categorie IN ('hospital','clinic','doctors','dentist','pharmacy','healthcare','nursing_home')) AS nb_sante,
       count(*) FILTER (WHERE p.categorie IN ('shop_supermarket','shop_mall','shop_department_store','shop_convenience','marketplace','shop_clothes','shop_electronics','shop_hardware','shop_furniture')) AS nb_commerces,
       count(*) FILTER (WHERE p.categorie IN ('bank','atm','office_bank','office_financial','bureau_de_change')) AS nb_banques,
       count(*) FILTER (WHERE p.categorie IN ('restaurant','cafe','fast_food','bar','pub','nightclub','cinema')) AS nb_restauration,
       count(*) FILTER (WHERE p.categorie IN ('office_government','office_company','office_ngo','office_insurance','office_telecommunication','office_it','office_consulting','townhall','post_office','courthouse')) AS nb_bureaux,
       count(*) FILTER (WHERE p.categorie IN ('bus_station','fuel')) AS nb_transport,
       count(*) FILTER (WHERE p.categorie = 'place_of_worship') AS nb_lieux_culte,
       count(*) FILTER (WHERE p.categorie LIKE 'leisure_%') AS nb_loisirs
FROM grille g
LEFT JOIN poi_points p ON ST_Intersects(g.geom, p.geom)
GROUP BY g.cell_id
""")

print("Consolidation des indicateurs...")
con.execute("""
CREATE OR REPLACE TABLE indicateurs_cellules AS
SELECT g.cell_id, g.arrondissement, g.lat, g.lon, g.area_km2,
       coalesce(b.nb_batiments,0) AS nb_batiments,
       coalesce(b.surf_batie_m2,0) AS surf_batie_m2,
       coalesce(b.nb_bat_commerces,0) AS nb_bat_commerces,
       coalesce(r.longueur_totale_m,0) AS longueur_route_m,
       coalesce(r.longueur_principale_m,0) AS longueur_principale_m,
       coalesce(r.longueur_secondaire_m,0) AS longueur_secondaire_m,
       coalesce(r.nb_axes_structurants,0) AS nb_axes_structurants,
       coalesce(p.nb_poi_total,0) AS nb_poi_total,
       coalesce(p.nb_education,0) AS nb_education,
       coalesce(p.nb_sante,0) AS nb_sante,
       coalesce(p.nb_commerces,0) AS nb_commerces,
       coalesce(p.nb_banques,0) AS nb_banques,
       coalesce(p.nb_restauration,0) AS nb_restauration,
       coalesce(p.nb_bureaux,0) AS nb_bureaux,
       coalesce(p.nb_transport,0) AS nb_transport,
       coalesce(p.nb_lieux_culte,0) AS nb_lieux_culte,
       coalesce(p.nb_loisirs,0) AS nb_loisirs,
       coalesce(b.nb_batiments,0) / nullif(g.area_km2, 0) AS dens_bat_km2,
       coalesce(b.surf_batie_m2,0) / nullif(g.area_km2, 0) AS dens_batie_m2_km2,
       coalesce(r.longueur_totale_m,0) / nullif(g.area_km2, 0) AS dens_routiere_m_km2,
       coalesce(p.nb_poi_total,0) / nullif(g.area_km2, 0) AS dens_poi_km2,
       coalesce(p.nb_commerces,0) / nullif(g.area_km2, 0) AS dens_commerces_km2
FROM grille g
LEFT JOIN ind_bati b USING (cell_id)
LEFT JOIN ind_routes r USING (cell_id)
LEFT JOIN ind_poi p USING (cell_id)
""")

print(con.execute("""
SELECT count(*) AS cellules, round(avg(nb_batiments),1) AS moy_bat,
       round(median(nb_batiments),1) AS med_bat, max(nb_batiments) AS max_bat,
       round(avg(dens_routiere_m_km2),1) AS moy_dens_route,
       round(avg(nb_poi_total),1) AS moy_poi,
       round(sum(surf_batie_m2)/1e6,1) AS surf_batie_km2
FROM indicateurs_cellules
""").df().to_string(index=False))

print(f"Grille et indicateurs calcules en {time.time()-t0:.1f}s")
con.close()
