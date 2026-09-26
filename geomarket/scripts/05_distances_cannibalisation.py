"""Analyse de la concurrence, distances et potentiel net (cannibalisation).

Identifie les agences bancaires reelles (hors distributeurs automatiques et
hors reseaux de transfert d'argent), calcule pour chaque cellule la distance
au concurrent le plus proche, puis applique une decote de cannibalisation au
score de potentiel brut afin d'obtenir un potentiel net.
"""
import os

import duckdb

ROOT = "/workspace/k2RTwgspVmeo0wQvNz2KflqHTVC3/6b826994-78cb-4540-af88-ec7a5afea2e5"
DB = os.path.join(ROOT, "geomarket/db/geomarket.duckdb")

# Reseaux de transfert d'argent et de monnaie electronique : ce ne sont pas des
# agences bancaires et ne comptent donc pas comme concurrents directs.
TRANSFERT = ("express union", "expres union", "western union", "express exchange",
             "emi money", "fiffa", "advans", "cca bank", "credit communaut",
             "micro finance")

RAYON_FORT = 1000      # en deca : forte cannibalisation
RAYON_NUL = 3000       # au dela : aucune cannibalisation
DECOTE_MAX = 0.35      # part maximale du score perdue a cause de la proximite

con = duckdb.connect(DB)
con.execute("LOAD spatial;")

import os as _os
liste = ",".join("'" + m.replace("'", "''") + "'" for m in TRANSFERT)

con.execute(f"""
CREATE OR REPLACE TABLE agences_existantes AS
SELECT p.osm_id,
       coalesce(nullif(p.brand,''), nullif(p.name,''), 'Agence bancaire') AS enseigne,
       p.name, p.brand, p.geom
FROM poi_points p
WHERE p.categorie IN ('bank', 'office_bank')
  AND NOT EXISTS (
      SELECT 1 FROM unnest([{liste}]) AS t(motif)
      WHERE lower(coalesce(p.brand,'') || ' ' || coalesce(p.name,'')) LIKE '%' || t.motif || '%'
  )
""")
n = con.execute("SELECT count(*) FROM agences_existantes").fetchone()[0]
print(f"Agences bancaires retenues comme concurrents directs : {n}")
print(con.execute("""
SELECT enseigne, count(*) AS n FROM agences_existantes
GROUP BY 1 ORDER BY n DESC LIMIT 12
""").df().to_string(index=False))

print("\nCalcul des distances (projection UTM 32N)...")
con.execute(f"""
CREATE OR REPLACE TABLE distances_concurrence AS
WITH cel AS (
  SELECT cell_id, arrondissement,
         ST_Transform(ST_Centroid(geom), 'EPSG:4326', 'EPSG:32632') AS pt
  FROM grille
), ag AS (
  SELECT enseigne, ST_Transform(geom, 'EPSG:4326', 'EPSG:32632') AS pt
  FROM agences_existantes
)
SELECT c.cell_id, c.arrondissement,
       min(ST_Distance(c.pt, a.pt)) AS dist_min_m,
       count(*) FILTER (WHERE ST_Distance(c.pt, a.pt) <= {RAYON_FORT}) AS nb_dans_1km,
       count(*) FILTER (WHERE ST_Distance(c.pt, a.pt) <= {RAYON_NUL}) AS nb_dans_3km
FROM cel c CROSS JOIN ag a
GROUP BY c.cell_id, c.arrondissement
""")

con.execute("""
CREATE OR REPLACE TABLE distances_concurrence2 AS
SELECT d.cell_id, d.arrondissement, d.dist_min_m, d.nb_dans_1km, d.nb_dans_3km,
       (SELECT a.enseigne FROM agences_existantes a
        ORDER BY ST_Distance(ST_Transform(g.geom,'EPSG:4326','EPSG:32632'),
                             ST_Transform(a.geom,'EPSG:4326','EPSG:32632'))
        LIMIT 1) AS enseigne_plus_proche
FROM distances_concurrence d
JOIN grille g USING (cell_id)
""")

print("Calcul du potentiel net...")
decote = (f"CASE WHEN d.dist_min_m IS NULL THEN 0.0 "
          f"WHEN d.dist_min_m <= {RAYON_FORT} THEN {DECOTE_MAX} "
          f"WHEN d.dist_min_m >= {RAYON_NUL} THEN 0.0 "
          f"ELSE {DECOTE_MAX} * ({RAYON_NUL} - d.dist_min_m) / ({RAYON_NUL} - {RAYON_FORT}) END")
con.execute(f"""
CREATE OR REPLACE TABLE scores_net AS
SELECT s.*, d.dist_min_m, d.nb_dans_1km, d.nb_dans_3km, d.enseigne_plus_proche,
       {decote} AS decote_cannibalisation,
       round(s.score_potentiel_brut * (1 - ({decote})), 2) AS score_potentiel_net
FROM scores s
LEFT JOIN distances_concurrence2 d USING (cell_id)
""")
con.execute("""
CREATE OR REPLACE TABLE scores_net AS
SELECT *, row_number() OVER (ORDER BY score_potentiel_net DESC, cell_id) AS rang_net
FROM scores_net
""")

print("\nTop 12 par potentiel net :")
print(con.execute("""
SELECT rang_net, arrondissement, score_potentiel_brut AS brut,
       score_potentiel_net AS net, round(decote_cannibalisation*100,1) AS decote_pct,
       round(dist_min_m) AS dist_m, nb_dans_1km, enseigne_plus_proche
FROM scores_net ORDER BY rang_net LIMIT 12
""").df().to_string(index=False))

print("\nMoyenne par arrondissement :")
print(con.execute("""
SELECT arrondissement, round(avg(score_potentiel_brut),1) AS brut,
       round(avg(score_potentiel_net),1) AS net,
       round(avg(decote_cannibalisation)*100,1) AS decote_pct,
       round(avg(dist_min_m)) AS dist_moy_m
FROM scores_net GROUP BY 1 ORDER BY net DESC
""").df().to_string(index=False))

print("\nSans banque a moins de 2 km :",
      con.execute("SELECT count(*) FROM scores_net WHERE dist_min_m >= 2000").fetchone()[0])
print("Avec banque a moins de 1 km :",
      con.execute("SELECT count(*) FROM scores_net WHERE dist_min_m <= 1000").fetchone()[0])
con.close()
