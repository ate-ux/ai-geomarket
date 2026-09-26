# Méthodologie

## Question posée

Où ouvrir une nouvelle agence bancaire à Yaoundé ? La réponse doit être
argumentée, reproductible et honnête sur les limites des données disponibles.

## Démarche en sept temps

### 1. Choix des données

Les données de population et de revenu au niveau quartier ne sont pas ouvertes au
Cameroun, ni pour la ville de Yaoundé. Aucune source ne permet de descendre à
l'échelle d'une cellule de 0,7 km² sur ces deux variables.

Le projet repose donc sur des proxys ouverts et vérifiables, tirés
d'OpenStreetMap : le bâti révèle la concentration d'habitants, le réseau routier
mesure l'accessibilité, les équipements publics et commerciaux traduisent
l'activité et la solvabilité indirecte. Cette substitution est assumée et
documentée plutôt que masquée.

### 2. Grille d'analyse

La ville est découpée en 431 cellules hexagonales de résolution 8 (environ
0,74 km²). L'hexagone évite les effets de bord des carrés et s'adapte à la forme
irrégulière des arrondissements. La grille pave les sept arrondissements, soit
284,8 km².

### 3. Indicateurs par cellule

Chaque cellule reçoit 24 indicateurs, par intersection spatiale entre la grille
et les couches géographiques :

- nombre et surface de bâtiments ; surface bâtie par km² ;
- longueur de voirie, dont voies structurantes ; nombre d'axes principaux ;
- commerces, écoles, santé, bureaux, restauration, transports, loisirs ;
- nombre d'agences bancaires.

La surface bâtie est mesurée en projection UTM 32N, correcte pour la latitude de
Yaoundé, plutôt qu'en degrés qui déformeraient les surfaces.

### 4. Scoring multicritère

Les indicateurs sont convertis en rangs percentiles, ce qui évite qu'une variable
à forte amplitude, comme le nombre de bâtiments, écrase les autres. Les rangs
sont agrégés en quatre axes, dont les pondérations par défaut sont :

| Axe | Poids | Justification |
|---|---|---|
| Demande | 40 % | le volume de clientèle conditionne la viabilité |
| Accessibilité | 25 % | une agence mal desservie capte moins de flux |
| Attractivité | 20 % | le passage et l'activité soutiennent l'activité bancaire |
| Concurrence | 15 % | la pression concurrentielle est une pénalité, non un atout |

La concurrence est soustraite et non ajoutée : une zone saturée en agences perd
des points. Les pondérations sont modifiables à l'exécution, dans le script comme
dans la carte.

### 5. Cannibalisation

Pour chaque cellule, la distance à l'agence bancaire la plus proche est calculée
en UTM 32N. La décote appliquée suit un dégradé linéaire :

- 35 % de décote pour une agence à moins de 1 km ;
- décroissance linéaire entre 1 km et 3 km ;
- aucune décote au-delà de 3 km.

Le seuil de 35 % traduit une hypothèse commerciale : une agence à moins d'un
kilomètre capte l'essentiel de la clientèle de proximité, sans l'annuler, d'où
une décote forte mais partielle.

### 6. Segmentation et modèle

Deux traitements d'apprentissage complètent l'analyse :

- une segmentation KMeans sur les rangs percentiles regroupe les cellules en
  profils de marché homogènes, pour piloter une stratégie différenciée ;
- un modèle d'arbres (GradientBoosting) apprend à reproduire le score composite à
  partir des seuls indicateurs bruts, afin de disposer d'un substitut rapide.

Le nombre de profils est choisi par la méthode de la silhouette. L'optimum
statistique tombe à k = 2, trop grossier pour piloter une implantation. Le k
retenu est donc 4, le plus petit nombre dont la silhouette reste à moins de 0,06
de l'optimum (0,3035 contre 0,3545) tout en produisant des profils actionnables.
Ce choix est documenté et reproduit par le script.

Le modèle de substitution atteint un R² de 0,972 en validation croisée à cinq
plis, avec une erreur absolue moyenne de 1,01 point de score. Ces chiffres
mesurent la fidélité du substitut au score composite, non une validation terrain :
la cible est dérivée du score lui-même.

### 7. Agent en langage naturel

L'agent traduit une demande française en critères pondérés, par reconnaissance de
vocabulaire métier. Il ajuste les poids des axes selon les termes employés
(« commerces », « peu de concurrence », « accessible », « clientèle aisée »),
détecte un arrondissement, une distance minimale et un nombre de zones, puis
interroge la base et restitue un classement argumenté.

Le moteur est déterministe et local. Il ne dépend d'aucune API externe, ce qui
garantit des réponses reproductibles et auditables.

## Limites assumées

**Pas de données de population ni de revenu.** La densité bâtie est une
approximation. Un quartier dense en bâti commercial peut abriter peu de résidents.
La lecture des résultats doit donc rester qualitative sur la solvabilité.

**Couverture OSM inégale.** Les quartiers centraux sont mieux cartographiés que
les périphéries. Le nombre de commerces ou d'écoles sous-estime les zones mal
couvertes par la cartographie contributive. L'analyse reflète l'état de la base
au 24 septembre 2026.

**Concurrence bancaire partielle.** Les agences recensées sont celles
cartographiées dans OSM. Des agences physiques absentes de la base ne sont pas
comptées, ce qui peut surestimer le potentiel de certaines zones.

**Cible synthétique.** Le modèle supervisé apprend le score composite, pas une
performance commerciale réelle. Il sert au prototypage et au calcul rapide, non à
la prévision. Une calibration sur des données d'ouverture réelles serait
nécessaire avant tout usage opérationnel.

**Pas de données de flux.** Les déplacements domicile-travail, les pôles
d'attraction réels et les projets d'urbanisme ne sont pas intégrés. Une agence
peut réussir dans une zone dense sans commerces, ou échouer dans une zone
commerçante sans résidents.

## Ce que le système ne fait pas

Il ne prédit pas le chiffre d'affaires d'une agence. Il ne remplace pas une étude
de marché avec enquête de terrain. Il éclaire le choix d'implantation par une
lecture spatiale structurée et reproductible, sur des données ouvertes.

## Rejouer l'analyse

Les onze scripts s'enchaînent sans intervention. Les tests automatisés (64
contrôles) vérifient l'intégrité des données, la cohérence des indicateurs et des
scores, la performance du modèle et le comportement de l'agent. La commande de
reproduction figure dans le modèle de données.
