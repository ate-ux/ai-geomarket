"""Extraction des limites administratives et des quartiers de Yaounde.

Source : extrait Geofabrik Cameroun osm.pbf (OSM du 24/09/2026).
Sortie : raw_data/geo/limites_administratives.geojson
"""
import json
import os
from collections import Counter

import osmium

ROOT = "/workspace/k2RTwgspVmeo0wQvNz2KflqHTVC3/6b826994-78cb-4540-af88-ec7a5afea2e5"
PBF = os.path.join(ROOT, "raw_data/osm/cameroon-latest.osm.pbf")
OUT = os.path.join(ROOT, "raw_data/geo")

MINLON, MINLAT, MAXLON, MAXLAT = 11.30, 3.60, 11.70, 4.10
LEVELS = {"4", "5", "6", "7", "8", "9", "10", "11"}


def rings_to_geom(area):
    outers, inners = [], []
    for ring in area.outer_rings():
        outers.append([[round(p.lon, 6), round(p.lat, 6)] for p in ring])
        for iring in area.inner_rings(ring):
            inners.append([[round(p.lon, 6), round(p.lat, 6)] for p in iring])
    if not outers:
        return None
    if len(outers) == 1:
        return {"type": "Polygon", "coordinates": [outers[0]] + inners}
    return {"type": "MultiPolygon", "coordinates": [[r] for r in outers]}


def overlaps(coords):
    if len(coords) < 4:
        return False
    lon = [c[0] for c in coords]
    lat = [c[1] for c in coords]
    return not (max(lon) < MINLON or min(lon) > MAXLON
                or max(lat) < MINLAT or min(lat) > MAXLAT)


class Collect(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.admin = []
        self.places = []
        self.counts = Counter()

    def area(self, a):
        if not a.is_area():
            return
        t = dict(a.tags)
        if not t:
            return
        g = rings_to_geom(a)
        if g is None:
            return
        first = g["coordinates"][0]
        flat = first if g["type"] == "Polygon" else (first[0] if first else [])
        if not overlaps(flat):
            return
        if t.get("boundary") == "administrative" and t.get("admin_level") in LEVELS:
            self.admin.append({
                "type": "Feature", "geometry": g,
                "properties": {
                    "osm_id": a.orig_id(), "nom": t.get("name", ""),
                    "niveau": int(t["admin_level"]),
                    "type_admin": t.get("admin_level", ""),
                    "population": t.get("population", ""),
                },
            })
            self.counts["admin_" + t["admin_level"]] += 1
        elif t.get("place") in {"suburb", "quarter", "neighbourhood", "city",
                                "town", "village"}:
            self.places.append({
                "type": "Feature", "geometry": g,
                "properties": {
                    "osm_id": a.orig_id(), "nom": t.get("name", ""),
                    "type_lieu": t.get("place", ""),
                    "population": t.get("population", ""),
                },
            })
            self.counts["place_" + t["place"]] += 1


h = Collect()
print("Lecture du fichier OSM avec localisation des arenes...", flush=True)
h.apply_file(PBF, locations=True)
print("admin:", len(h.admin), "| lieux surfaciques:", len(h.places))
print("compteurs:", dict(h.counts))

p = os.path.join(OUT, "limites_administratives.geojson")
with open(p, "w", encoding="utf-8") as fh:
    json.dump({"type": "FeatureCollection", "name": "limites",
               "features": h.admin}, fh, ensure_ascii=False)
print(f"  limites_administratives.geojson: {len(h.admin)} entites "
      f"({os.path.getsize(p)/1e6:.2f} Mo)")

p2 = os.path.join(OUT, "lieux_surfaciques.geojson")
with open(p2, "w", encoding="utf-8") as fh:
    json.dump({"type": "FeatureCollection", "name": "quartiers",
               "features": h.places}, fh, ensure_ascii=False)
print(f"  lieux_surfaciques.geojson: {len(h.places)} entites")

noms = [(f["properties"]["niveau"], f["properties"]["nom"]) for f in h.admin]
for lvl in sorted({n for n, _ in noms}):
    sel = [nm for n, nm in noms if n == lvl]
    print(f"niveau {lvl}: {len(sel)} -> {sel[:30]}")
