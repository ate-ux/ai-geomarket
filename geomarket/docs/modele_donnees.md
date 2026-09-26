# AI GeoMarket : modèle de données

## Vue d'ensemble

La base DuckDB `geomarket/db/geomarket.duckdb` regroupe l'ensemble des couches
géographiques, des indicateurs et des scores. Elle est reconstruite de bout en
bout par les scripts numérotés, sans intervention manuelle.

## Source des données

Toutes les données proviennent d'OpenStreetMap, extrait Geofabrik du Cameroun
(fichier `cameroon-latest.osm.pbf`, données OSM du 24 septembre 2026), filtré sur
l'emprise de la Communauté urbaine de Yaoundé.

| Couche source | Nombre d'entités | Usage dans l'analyse |
|---|---|---|
| Bâtiments | 383 958 | densité bâtie, proxy de population |
| Tronçons routiers | 30 429 | accessibilité, axes structurants |
| Points d'intérêt | 11 868 | attractivité, équipements, concurrence |
| Limites administratives | 95 | arrondissements, quartiers, emprise |
| Lieux nommés | 102 | repères de quartier |

## Schéma des tables

### Tables de référence

`limites` : toutes les limites administratives extraites de l'emprise (niveaux 4
à 10), avec `osm_id`, `nom`, `niveau` et `population` quand elle est renseignée.

`arrondissements` : les sept arrondissements de Yaoundé (niveau administratif 8,
nom commençant par « Yaound »).

`quartiers` : les quartiers de niveau 10 dont le centroïde tombe dans un
arrondissement, avec leur rattachement. 63 quartiers retenus.

`quartiers_hors_ville` : les quartiers de niveau 10 situés hors des sept
arrondissements, exclus de l'analyse et conservés pour la traçabilité. Un cas :
NTOUTMEVOUM, à environ 4 km à l'est de l'emprise urbaine.

### Tables géographiques

`batiments` : emprises bâties, avec `type_batiment`, `niveaux` et `usage`.

`routes` : tronçons routiers, avec `classe` (motorway à residential), `nom`,
`voies` et `surface`.

`points_interet` : 73 catégories d'équipements (écoles, santé, commerces,
banques, bureaux, transports, loisirs, lieux de culte).

`poi_points` : les mêmes points d'intérêt ramenés à leur centroïde, pour
l'affectation spatiale aux cellules.

`lieux` : lieux nommés de l'emprise (places, quartiers ponctuels).

### Table d'analyse

`grille` : 431 cellules hexagonales H3 de résolution 8, soit environ 0,74 km²
chacune, pavant les sept arrondissements. Colonnes : `cell_id`, `arrondissement`,
`lat`, `lon`, `area_km2`, `geom`.

### Tables d'indicateurs et de scores

`indicateurs_cellules` : 24 indicateurs par cellule, construits par intersection
spatiale entre la grille et les couches géographiques (comptages, surfaces,
longueurs, densités).

`scores` : scores par axe et potentiel brut, après normalisation par rangs
percentiles.

`agences_existantes` : 82 agences bancaires retenues comme concurrents directs,
après exclusion des distributeurs automatiques, des bureaux financiers non
bancaires et des réseaux de transfert d'argent.

`distances_concurrence2` : distance en mètres (projection UTM 32N) de chaque
cellule à l'agence la plus proche, nombre d'agences dans un rayon de 1 km et de
3 km, enseigne la plus proche.

`scores_net` : score brut, décote de cannibalisation et potentiel net, avec le
rang net.

`segments_ml` : table finale enrichie, avec le profil de marché issu de la
segmentation, le score prédit en validation croisée et l'écart au score composite.

## Enchaînement des scripts

| Script | Rôle | Sortie principale |
|---|---|---|
| `01_extraction_osm.py` | extraction des couches OSM | 4 GeoJSON dans `raw_data/geo/` |
| `02_limites_quartiers.py` | limites administratives | `limites_administratives.geojson` |
| `03_base_spatiale.py` | chargement et index dans DuckDB | base complète |
| `04_grille_indicateurs.py` | grille H3 et indicateurs | `grille`, `indicateurs_cellules` |
| `moteur_scoring.py` | scoring multicritère | `scores` |
| `05_distances_cannibalisation.py` | concurrence et potentiel net | `scores_net` |
| `06_modele_ml.py` | segmentation et modèle | `segments_ml`, `modele_ml.json` |
| `07_agent_langage_naturel.py` | agent conversationnel | réponses texte |
| `08_export_web.py` | export pour la carte | `web/data/` |
| `09_rendu_cartes.py` | figures statiques | 5 images PNG |
| `10_tests_qualite.py` | contrôles automatisés | `sortie_tests.txt` |
| `11_archives.py` | archives livrables | 2 fichiers ZIP |

## Reproduire la chaîne complète

```bash
pip install duckdb geopandas shapely pyproj osmium h3 scikit-learn matplotlib pillow
python geomarket/scripts/01_extraction_osm.py
python geomarket/scripts/02_limites_quartiers.py
python geomarket/scripts/03_base_spatiale.py
python geomarket/scripts/04_grille_indicateurs.py
python geomarket/scripts/moteur_scoring.py
python geomarket/scripts/05_distances_cannibalisation.py
python geomarket/scripts/06_modele_ml.py
python geomarket/scripts/08_export_web.py
python geomarket/scripts/09_rendu_cartes.py
python geomarket/scripts/10_tests_qualite.py
python geomarket/scripts/11_archives.py
```

L'extraction OSM est l'étape longue (environ 4 minutes pour les 213 Mo du
fichier Cameroun). Les étapes suivantes s'exécutent en quelques secondes à
quelques dizaines de secondes.
