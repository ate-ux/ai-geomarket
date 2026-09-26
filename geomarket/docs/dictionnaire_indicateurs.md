# Dictionnaire des indicateurs

Tous les indicateurs sont calculés pour les 431 cellules hexagonales de la
grille d'analyse (résolution 8, environ 0,74 km² par cellule).

## Axe 1 : demande

Proxy du volume et de la solvabilité de la clientèle potentielle.

| Indicateur | Définition | Poids dans l'axe |
|---|---|---|
| `dens_bat_km2` | nombre de bâtiments par km² | principal |
| `dens_batie_m2_km2` | surface bâtie en m² par km² | principal |
| `nb_education` | établissements scolaires et de formation | secondaire |
| `nb_sante` | structures de santé (hôpitaux, cliniques, pharmacies) | secondaire |
| `nb_lieux_culte` | lieux de culte (proxy d'ancrage résidentiel) | secondaire |

La densité bâtie remplace une densité de population, indisponible au niveau
quartier. Elle mesure la concentration du bâti, corrélée au nombre de résidents
et d'usagers.

## Axe 2 : accessibilité

Capacité d'une zone à être atteinte et à drainer une clientèle élargie.

| Indicateur | Définition |
|---|---|
| `dens_routiere_m_km2` | longueur totale du réseau routier par km² |
| `longueur_principale_m` | longueur des voies motorway, trunk et primary |
| `nb_axes_structurants` | nombre de tronçons de rang motorway à tertiary |
| `nb_transport` | gares routières et stations-service |

Un axe structurant (nationale, voie de contournement) améliore la visibilité et
l'accès. Une voirie dense de desserte facilite les déplacements de proximité.

## Axe 3 : attractivité

Intensité de l'activité économique et de l'animation urbaine, qui conditionne le
flux de passage.

| Indicateur | Définition |
|---|---|
| `dens_commerces_km2` | commerces par km² (supermarchés, boutiques, marchés, quincailleries) |
| `nb_commerces` | nombre de commerces |
| `nb_restauration` | restaurants, cafés, bars, cinémas |
| `nb_bureaux` | bureaux, administrations, assurances, télécoms |
| `nb_loisirs` | équipements sportifs, parcs, salles de sport |

Les bureaux et administrations sont particulièrement pertinents pour une agence
bancaire : ce sont des générateurs de flux de clientèle professionnelle.

## Axe 4 : concurrence

Pression concurrentielle directe. Cet axe est une pénalité : plus la zone est
desservie, plus le score de l'axe est élevé et plus il retire de points.

| Indicateur | Définition |
|---|---|
| `nb_banques` | agences bancaires dans la cellule |

## Indicateurs de concurrence spatiale

| Indicateur | Définition |
|---|---|
| `dist_min_m` | distance en mètres à l'agence bancaire la plus proche (UTM 32N) |
| `nb_dans_1km` | nombre d'agences dans un rayon de 1 km |
| `nb_dans_3km` | nombre d'agences dans un rayon de 3 km |
| `enseigne_plus_proche` | nom de l'enseigne la plus proche |
| `decote_cannibalisation` | part du score perdue par proximité concurrentielle |

## Indicateurs de synthèse

| Indicateur | Définition | Étendue |
|---|---|---|
| `score_demande` | moyenne des rangs percentiles de l'axe 1 | 0 à 1 |
| `score_accessibilite` | moyenne des rangs percentiles de l'axe 2 | 0 à 1 |
| `score_attractivite` | moyenne des rangs percentiles de l'axe 3 | 0 à 1 |
| `score_concurrence` | rang percentile de la densité bancaire | 0 à 1 |
| `score_potentiel_brut` | agrégation pondérée des quatre axes | 0 à 100 |
| `score_potentiel_net` | potentiel brut diminué de la décote de concurrence | 0 à 100 |
| `rang_net` | classement par potentiel net | 1 à 431 |
| `profil_marche` | profil issu de la segmentation | 4 valeurs |

## Signification des profils de marché

| Profil | Cellules | Score net moyen | Caractéristiques dominantes |
|---|---|---|---|
| Centre structuré commerçant | 58 | 42,5 | fort équipement commercial, densité bâtie élevée |
| Quartier d'activité mixte | 75 | 41,8 | commerces et bureaux, voirie dense |
| Périphérie résidentielle | 124 | 36,6 | bâti résidentiel, faible équipement commercial |
| Zone peu équipée | 174 | 29,5 | faible densité de bâti et de services |

## Mesures de référence

| Mesure | Valeur |
|---|---|
| Cellules analysées | 431 |
| Superficie couverte | 284,8 km² |
| Surface bâtie détectée dans les cellules | 43,8 km² |
| Agences bancaires concurrentes | 82 |
| Cellules sans banque à moins de 2 km | 231 |
| Cellules avec banque à moins de 1 km | 84 |
| Potentiel net moyen | 35,4 |
| Potentiel net maximal | 67,2 |

La surface bâtie totale extraite est de 54,7 km². La surface rattachée aux
cellules est plus faible (43,8 km²) car les bâtiments situés hors de la grille
hexagonale, principalement en périphérie rurale, ne sont pas comptés.
