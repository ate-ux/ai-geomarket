# AI GeoMarket

Système d'intelligence géomarketing pour le choix d'implantation d'agence
bancaire à Yaoundé. Le système répond à la question « où ouvrir ? » par une
analyse spatiale multicritère, un agent en langage naturel et une carte
interactive.

## Ce que fait le système

À partir des données OpenStreetMap de Yaoundé, il découpe la ville en 431 cellules
hexagonales (0,74 km²), calcule 24 indicateurs par cellule, agrège quatre axes de
décision pondérés, applique une décote de cannibalisation selon la proximité
concurrentielle, segmente les zones en profils de marché, puis classe les
meilleurs emplacements.

L'agent conversationnel traduit une demande en français, comme « trouve les 5
zones présentant le meilleur potentiel pour une nouvelle agence », en critères
pondérés, interroge la base spatiale et restitue un classement argumenté.

## Structure du dépôt

```
geomarket/
  scripts/     onze scripts Python, de l'extraction à la livraison
  docs/        modèle de données, méthodologie, dictionnaire des indicateurs
  db/          base DuckDB spatiale (reconstruite par les scripts)
  data/        couches GeoJSON extraites d'OpenStreetMap
  web/         carte interactive MapLibre GL et agent JavaScript
  outputs/     cartes PNG, résultats des tests, métriques du modèle
```

## Démarrage rapide

```bash
pip install duckdb geopandas shapely pyproj osmium h3 scikit-learn matplotlib pillow

# Télécharger l'extrait OSM du Cameroun (213 Mo)
curl -o raw_data/osm/cameroon-latest.osm.pbf \
  https://download.geofabrik.de/africa/cameroon-latest.osm.pbf

# Construire la chaîne complète
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

# Ouvrir la carte
cd geomarket/web && python -m http.server 8000
```

## Résultats de référence

| Mesure | Valeur |
|---|---|
| Bâtiments analysés | 383 958 |
| Tronçons routiers | 30 429 |
| Points d'intérêt | 11 868 |
| Cellules hexagonales | 431 |
| Arrondissements couverts | 7 |
| Quartiers rattachés | 63 |
| Agences bancaires concurrentes | 82 |
| Superficie analysée | 284,8 km² |
| Surface bâtie dans la grille | 43,8 km² |
| Cellules sans banque à moins de 2 km | 231 |

Qualité : 64 contrôles sur 64 réussis.

## Le scoring en bref

Quatre axes pondérés (demande 40 %, accessibilité 25 %, attractivité 20 %,
concurrence 15 % en pénalité), sur des rangs percentiles. La concurrence applique
ensuite une décote de cannibalisation allant jusqu'à 35 % dans un rayon de 1 km.

Résultats : Yaoundé V, VI et VII concentrent les meilleurs potentiels nets. Les
trois premières zones recommandées sont dans les arrondissements V et VII, toutes
à plus de 2 km d'une agence bancaire existante.

## Modèle d'apprentissage

Segmentation KMeans en 4 profils de marché : centre structuré commerçant,
quartier d'activité mixte, périphérie résidentielle, zone peu équipée.

Modèle de substitution par arbres (GradientBoosting) : R² de 0,972 en validation
croisée à cinq plis, erreur absolue moyenne de 1,01 point. Les facteurs les plus
déterminants sont la distance à la concurrence, l'équipement en santé et la
densité commerciale.

## Limites des données

La population et le revenu ne sont pas disponibles au niveau quartier au
Cameroun. Le système s'appuie sur des proxys ouverts (densité bâtie, réseau
routier, équipements), assumés et documentés. La couverture OpenStreetMap est
inégale, plus dense au centre. La concurrence bancaire recensée reflète la
cartographie contributive, non un registre officiel. Détail complet dans
`docs/methodologie.md`.

## Documentation

- `docs/modele_donnees.md` : schéma complet des tables et enchaînement des scripts
- `docs/methodologie.md` : démarche, hypothèses, limites assumées
- `docs/dictionnaire_indicateurs.md` : définition des 24 indicateurs et des scores

## Données et licence

Données OpenStreetMap, extrait Geofabrik du Cameroun, millésime du 24 septembre
2026. OpenStreetMap est distribué sous licence ODbL. Le code du projet est
fourni pour usage d'analyse et de démonstration.
