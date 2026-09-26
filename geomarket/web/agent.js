/* Agent géomarketing côté navigateur.
   Portage en JavaScript du moteur Python : reconnaissance du vocabulaire
   métier français, ajustement des pondérations, filtres puis classement.
   Aucun appel réseau : tout le raisonnement s'exécute sur les données chargées. */

const AXES = {
  demande: ["dens_bat_km2", "nb_education", "nb_sante", "nb_lieux_culte"],
  accessibilite: ["dens_route_m_km2", "longueur_principale_m", "nb_axes_structurants", "nb_transport"],
  attractivite: ["dens_commerces_km2", "nb_commerces", "nb_restauration", "nb_bureaux", "nb_loisirs"],
  concurrence: ["nb_banques"]
};

const POIDS_DEFAUT = { demande: 0.40, accessibilite: 0.25, attractivite: 0.20, concurrence: 0.15 };

const MOTS_CLES = [
  [/population|demograph|densite|habitants|clients potentiels|volume/, { demande: 0.20 }],
  [/revenu|solvab|pouvoir d'achat|aise|richesse|premium|haut de gamme/, { demande: 0.10, attractivite: 0.15 }],
  [/accessible|accessibilite|route|voirie|transport|axe|carrefour|desserte/, { accessibilite: 0.25 }],
  [/central|centre-ville|hypercentre|coeur|dense|animation|commerce|boutique|marche/, { attractivite: 0.25 }],
  [/concurrence|concurrent|rivaux|banques en place|deja implant|saturation|cannibalisation/, { concurrence: 0.20 }],
  [/peu de concurrence|zone vierge|non desservi|non couvert|sans banque|opportunite/, { concurrence: 0.25, demande: 0.10 }],
  [/ecole|education|universite|etudiant|jeune|scolaris|formation|lycee|college/, { demande: 0.05, attractivite: 0.10 }],
  [/sante|hospital|clinique|pharmacie|dispensaire|medical/, { attractivite: 0.10 }],
  [/entreprise|bureau|affaires|professionnel|siege|pme|b2b/, { attractivite: 0.15, accessibilite: 0.05 }]
];

const ARRONDISSEMENTS = {
  "yaounde i": "Yaoundé I", "yaounde 1": "Yaoundé I", "yaounde ii": "Yaoundé II",
  "yaounde 2": "Yaoundé II", "yaounde iii": "Yaoundé III", "yaounde 3": "Yaoundé III",
  "yaounde iv": "Yaoundé IV", "yaounde 4": "Yaoundé IV", "yaounde v": "Yaoundé V",
  "yaounde 5": "Yaoundé V", "yaounde vi": "Yaoundé VI", "yaounde 6": "Yaoundé VI",
  "yaounde vii": "Yaoundé VII", "yaounde 7": "Yaoundé VII"
};

const LIBELLES = {
  demande: "demande (densité bâtie, équipements publics)",
  accessibilite: "accessibilité (réseau routier, transports)",
  attractivite: "attractivité (commerce, bureaux, loisirs)",
  concurrence: "pression concurrentielle (pénalité)"
};

function normaliser(t) {
  return t.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

/* Traduit la question en critères pondérés, filtres et nombre de zones. */
export function extraireCriteres(question) {
  const q = normaliser(question);
  const ponderations = { ...POIDS_DEFAUT };
  const reconnus = [];
  for (const [motif, deltas] of MOTS_CLES) {
    if (motif.test(q)) {
      for (const [axe, d] of Object.entries(deltas)) ponderations[axe] += d;
      reconnus.push(motif.source.split("|")[0].replace(/\\b/g, ""));
    }
  }
  const arr = Object.entries(ARRONDISSEMENTS)
    .filter(([k]) => q.includes(k)).map(([, v]) => v);

  let m = q.match(/(\d{1,2})\s*(?:zones?|sites?|cellules?|quartiers?|emplacements?|meilleures?|meilleurs?|meilleur|top)/);
  if (!m) m = q.match(/top\s*(\d{1,2})/);
  const nbZones = m ? Math.max(1, Math.min(parseInt(m[1], 10), 25)) : 5;

  let distMin = null;
  const d = q.match(/(?:au moins|minimum|min|plus de|a plus de|superieur a)\s*(\d+(?:[.,]\d+)?)\s*(km|kilometre|m|metre)/);
  if (d) {
    const v = parseFloat(d[1].replace(",", "."));
    distMin = d[2].startsWith("km") || d[2].startsWith("kilo") ? v * 1000 : v;
  }
  return {
    question, ponderations, arrondissements: [...new Set(arr)], nbZones,
    distanceMinM: distMin, criteresReconnus: [...new Set(reconnus)]
  };
}

/* Rang percentile (0 à 1) sur un tableau de valeurs, ex æquo départagés. */
export function percentiles(valeurs) {
  const idx = valeurs.map((v, i) => [v, i]).sort((a, b) => a[0] - b[0]);
  const rangs = new Array(valeurs.length);
  let i = 0;
  while (i < idx.length) {
    let j = i;
    while (j + 1 < idx.length && idx[j + 1][0] === idx[i][0]) j++;
    const rang = (i + j) / 2 + 1;
    for (let k = i; k <= j; k++) rangs[idx[k][1]] = rang / idx.length;
    i = j + 1;
  }
  return rangs;
}

/* Recalcule les scores pour les pondérations et filtres retenus. */
export function classerZones(cellules, criteres, etat) {
  const p = { ...criteres.ponderations };
  const total = Object.values(p).reduce((a, b) => a + b, 0) || 1;
  for (const k of Object.keys(p)) p[k] /= total;

  const scores = {};
  for (const [axe, cols] of Object.entries(AXES)) {
    const dispo = cols.filter(c => cellules[0] && c in cellules[0]);
    if (!dispo.length) { scores[axe] = cellules.map(() => 0); continue; }
    const parCol = dispo.map(c => percentiles(cellules.map(r => Number(r[c]) || 0)));
    scores[axe] = cellules.map((_, i) =>
      parCol.reduce((s, col) => s + col[i], 0) / parCol.length);
  }
  const plancher = -p.concurrence;
  let lignes = cellules.map((r, i) => {
    const pot = p.demande * scores.demande[i] + p.accessibilite * scores.accessibilite[i]
      + p.attractivite * scores.attractivite[i] - p.concurrence * scores.concurrence[i];
    return {
      ...r,
      score_question: Math.max(0, Math.min(100, ((pot - plancher) / (1 - plancher)) * 100))
    };
  });

  if (criteres.arrondissements.length)
    lignes = lignes.filter(r => criteres.arrondissements.includes(r.arrondissement));
  if (criteres.distanceMinM)
    lignes = lignes.filter(r => Number(r.dist_min_m) >= criteres.distanceMinM);
  if (etat && etat.scoreMin)
    lignes = lignes.filter(r => r.score_question >= etat.scoreMin);

  lignes.sort((a, b) => b.score_question - a.score_question);
  return lignes.slice(0, criteres.nbZones);
}

/* Rédige la réponse en français à partir des critères et des zones retenues. */
export function redigerReponse(criteres, zones) {
  const total = Object.values(criteres.ponderations).reduce((a, b) => a + b, 0) || 1;
  const L = [];
  L.push("Pondérations retenues");
  for (const [axe, v] of Object.entries(criteres.ponderations))
    L.push(`  - ${LIBELLES[axe]} : ${Math.round(v / total * 100)} %`);
  if (criteres.arrondissements.length) L.push(`  - Filtre : ${criteres.arrondissements.join(", ")}`);
  if (criteres.distanceMinM) L.push(`  - Distance minimale à un concurrent : ${criteres.distanceMinM} m`);
  L.push("");
  L.push(`${zones.length} zones recommandées, classées par potentiel`);
  zones.forEach((z, i) => {
    L.push(`  ${i + 1}. ${z.arrondissement} (${z.profil_marche}) - score ${z.score_question.toFixed(1)}/100`);
    L.push(`     ${z.nb_commerces} commerces, ${z.nb_education} établissements scolaires, ${z.nb_sante} structures de santé ; concurrent le plus proche : ${z.enseigne_plus_proche} à ${Math.round(z.dist_min_m)} m`);
  });
  L.push("");
  L.push("Lecture : le score agrège les quatre axes avec ces pondérations. Il s'appuie sur des proxys ouverts (densité bâtie OSM, réseau routier, équipements) et non sur des données de revenu fines, indisponibles au niveau quartier.");
  return L.join("\n");
}
