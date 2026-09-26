"""Extraction des donnees OpenStreetMap pour la zone de Yaounde.

Source : extrait Geofabrik Cameroun (osm.pbf), donnees OSM du 24/09/2026.
Sortie : fichiers GeoJSON dans raw_data/geo/ + un bilan d'extraction.
"""
import json
import os
from collections import Counter

import osmium

ROOT = "/workspace/k2RTwgspVmeo0wQvNz2KflqHTVC3/6b826994-78cb-4540-af88-ec7a5afea2e5"
PBF = os.path.join(ROOT, "raw_data/osm/cameroon-latest.osm.pbf")
OUT = os.path.join(ROOT, "raw_data/geo")
os.makedirs(OUT, exist_ok=True)

# Bounding box de la Communaute urbaine de Yaounde, avec marge de securite
MINLON, MINLAT, MAXLON, MAXLAT = 11.39, 3.69, 11.60, 3.99

POI_AMENITY = {
    "hospital", "clinic", "doctors", "dentist", "pharmacy", "school",
    "university", "college", "kindergarten", "bank", "atm", "marketplace",
    "police", "fire_station", "restaurant", "cafe", "fast_food", "fuel",
    "bus_station", "townhall", "post_office", "place_of_worship", "library",
    "community_centre", "social_facility", "nursing_home", "veterinary",
    "bureau_de_change", "courthouse", "embassy", "driving_school",
    "training", "childcare", "nightclub", "bar", "pub", "cinema",
}
POI_SHOP = {"supermarket", "mall", "department_store", "convenience", "clothes",
            "electronics", "hardware", "furniture", "bakery", "butcher",
            "mobile_phone", "car", "motorcycle", "beauty", "hairdresser"}
POI_OFFICE = {"government", "company", "ngo", "insurance", "financial",
              "estate_agent", "educational_institution", "telecommunication",
              "lawyer", "accountant", "consulting", "it", "bank", "notary"}
POI_LEISURE = {"sports_centre", "stadium", "pitch", "park", "garden",
               "fitness_centre", "playground", "swimming_pool"}
PLACE_TYPES = {"city", "suburb", "quarter", "neighbourhood", "village",
               "town", "hamlet", "borough"}

roads, buildings, pois, places = [], [], [], []
counters = Counter()


def geom_way(coords):
    return {"type": "LineString", "coordinates": coords} if len(coords) >= 2 else None


def geom_poly(coords):
    if len(coords) < 4:
        return None
    if coords[0] != coords[-1]:
        coords = coords + [coords[0]]
    return {"type": "Polygon", "coordinates": [coords]}


def inside(lon, lat):
    return MINLON <= lon <= MAXLON and MINLAT <= lat <= MAXLAT


class NodeCollector(osmium.SimpleHandler):
    """Collecte les noeuds de la bbox (coordonnees + POI + lieux nommes)."""
    def node(self, n):
        lon, lat = n.location.lon, n.location.lat
        if not inside(lon, lat):
            return
        nodes[n.id] = (round(lon, 6), round(lat, 6))
        tags = dict(n.tags)
        if not tags:
            return
        if tags.get("place") in PLACE_TYPES:
            places.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"osm_id": n.id, "name": tags.get("name", ""),
                               "place": tags.get("place"),
                               "population": tags.get("population")},
            })
            counters["place_node"] += 1
        cat = None
        if tags.get("amenity") in POI_AMENITY:
            cat = tags["amenity"]
        elif tags.get("shop") in POI_SHOP:
            cat = "shop_" + tags["shop"]
        elif tags.get("office") in POI_OFFICE:
            cat = "office_" + tags["office"]
        elif tags.get("leisure") in POI_LEISURE:
            cat = "leisure_" + tags["leisure"]
        elif tags.get("healthcare"):
            cat = "healthcare"
        if cat or tags.get("amenity") == "bank":
            pois.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "osm_id": n.id, "categorie": cat or "autre",
                    "name": tags.get("name", ""),
                    "amenity": tags.get("amenity", ""),
                    "brand": tags.get("brand", tags.get("operator", "")),
                    "source": "node",
                },
            })
            counters["poi_node"] += 1


class WayCollector(osmium.SimpleHandler):
    """Collecte les voies : routes, batiments, POI surfaciques."""
    def way(self, w):
        tags = dict(w.tags)
        if not tags:
            return
        coords = []
        touched = False
        for nd in w.nodes:
            c = nodes.get(nd.ref)
            if c is None:
                continue
            coords.append([c[0], c[1]])
            touched = True
        if not touched or len(coords) < 2:
            return
        if "highway" in tags:
            roads.append({
                "type": "Feature",
                "geometry": geom_way(coords),
                "properties": {
                    "osm_id": w.id, "nom": tags.get("name", ""),
                    "classe": tags["highway"],
                    "sens_unique": tags.get("oneway", ""),
                    "voies": tags.get("lanes", ""),
                    "surface": tags.get("surface", ""),
                    "pont": tags.get("bridge", ""),
                },
            })
            counters["route"] += 1
        elif "building" in tags:
            g = geom_poly([list(c) for c in coords])
            if not g:
                return
            buildings.append({
                "type": "Feature",
                "geometry": g,
                "properties": {
                    "osm_id": w.id, "type_batiment": tags.get("building", "yes"),
                    "niveaux": tags.get("building:levels", ""),
                    "usage": tags.get("building:use", tags.get("amenity", "")),
                },
            })
            counters["batiment"] += 1
        else:
            cat = None
            if tags.get("amenity") in POI_AMENITY:
                cat = tags["amenity"]
            elif tags.get("shop") in POI_SHOP:
                cat = "shop_" + tags["shop"]
            elif tags.get("office") in POI_OFFICE:
                cat = "office_" + tags["office"]
            elif tags.get("leisure") in POI_LEISURE:
                cat = "leisure_" + tags["leisure"]
            elif tags.get("landuse") in {"industrial", "commercial", "retail"}:
                cat = "landuse_" + tags["landuse"]
            if cat:
                g = geom_poly([list(c) for c in coords]) or geom_way(coords)
                if not g:
                    return
                lon = sum(c[0] for c in coords) / len(coords)
                lat = sum(c[1] for c in coords) / len(coords)
                pois.append({
                    "type": "Feature",
                    "geometry": g,
                    "properties": {
                        "osm_id": w.id, "categorie": cat,
                        "name": tags.get("name", ""),
                        "amenity": tags.get("amenity", ""),
                        "brand": tags.get("brand", tags.get("operator", "")),
                        "source": "way", "centroide_lon": round(lon, 6),
                        "centroide_lat": round(lat, 6),
                    },
                })
                counters["poi_way"] += 1


nodes = {}
print("Passage 1/2 : noeuds et points d'interet...", flush=True)
NodeCollector().apply_file(PBF)
print(f"  noeuds dans la bbox : {len(nodes):,}", flush=True)

print("Passage 2/2 : routes, batiments et surfaces...", flush=True)
WayCollector().apply_file(PBF)


def write_fc(name, feats, kind):
    feats = [f for f in feats if f["geometry"] is not None]
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"type": "FeatureCollection", "name": kind,
                   "crs": {"type": "name",
                           "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
                   "features": feats}, fh, ensure_ascii=False)
    print(f"  {name}: {len(feats):,} entites ({os.path.getsize(path)/1e6:.1f} Mo)", flush=True)
    return len(feats)


summary = {
    "source": "Geofabrik Cameroun osm.pbf, donnees OSM du 2026-09-24",
    "bbox": [MINLON, MINLAT, MAXLON, MAXLAT],
    "routes": write_fc("routes.geojson", roads, "routes"),
    "batiments": write_fc("batiments.geojson", buildings, "batiments"),
    "points_interet": write_fc("points_interet.geojson", pois, "points_interet"),
    "lieux": write_fc("lieux.geojson", places, "lieux"),
    "compteurs": dict(counters),
}

cat = Counter(f["properties"]["categorie"] for f in pois)
summary["categories_poi"] = dict(cat.most_common())
cls = Counter(f["properties"]["classe"] for f in roads)
summary["classes_routes"] = dict(cls.most_common())

with open(os.path.join(OUT, "bilan_extraction.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, ensure_ascii=False, indent=2)

print("\nBILAN", json.dumps(summary, ensure_ascii=False, indent=2))
