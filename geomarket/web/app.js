import { extraireCriteres, classerZones, redigerReponse } from "./agent.js";

const DATA = "data/";
const state = {
  cellules: [], arrondissements: [], quartiers: [], routes: [], agences: [],
  equipements: [], classement: [], kpis: {}, modele: {}, scoresParArr: [],
  poids: { demande: 40, accessibilite: 25, attractivite: 20, concurrence: 15 },
  filtres: { arrondissement: "", distance: 0, scoreMin: 0 },
  zonesActives: []
};

const COULEURS = ["#e8eef5", "#cfe0ee", "#a9c6e0", "#7ba7cd", "#4f86b8",
                  "#2f6a9e", "#1b4b7a", "#0B2545"];

const COUCHES = [
  { id: "hexagones", nom: "Potentiel par cellule", visible: true },
  { id: "routes", nom: "Réseau routier structurant", visible: true },
  { id: "quartiers", nom: "Quartiers", visible: false },
  { id: "agences", nom: "Agences bancaires existantes", visible: true },
  { id: "equipements", nom: "Écoles, santé, marchés", visible: false },
  { id: "top20", nom: "Top 20 des zones", visible: true }
];

async function chargerJson(nom) {
  const r = await fetch(DATA + nom);
  if (!r.ok) throw new Error(`${nom}: ${r.status}`);
  return r.json();
}

function couleurPour(score) {
  const s = Math.max(0, Math.min(100, score));
  const i = Math.min(COULEURS.length - 1, Math.floor((s / 100) * COULEURS.length));
  return COULEURS[i];
}

function construireKpis() {
  const k = state.kpis;
  const items = [
    [k.batiments?.toLocaleString("fr-FR"), "bâtiments"],
    [k.troncons_routiers?.toLocaleString("fr-FR"), "tronçons"],
    [k.points_interet?.toLocaleString("fr-FR"), "points d'intérêt"],
    [k.cellules, "cellules"],
    [k.arrondissements, "arrondissements"],
    [k.agences_concurrentes, "banques recensées"],
    [k.superficie_km2 + " km²", "surface analysée"]
  ];
  document.getElementById("kpis").innerHTML = items
    .map(([v, l]) => `<div><div class="v">${v ?? ""}</div><div class="l">${l}</div></div>`)
    .join("");
}

function construireSliders() {
  const libelles = { demande: "Demande", accessibilite: "Accessibilité",
                     attractivite: "Attractivité", concurrence: "Concurrence" };
  document.getElementById("sliders").innerHTML = Object.entries(state.poids)
    .map(([k, v]) => `
      <div class="slider">
        <label><span>${libelles[k]}</span><span class="val" id="v_${k}">${v}</span></label>
        <input type="range" min="0" max="60" step="5" value="${v}" data-poids="${k}">
      </div>`).join("");
  document.querySelectorAll("input[data-poids]").forEach(el => {
    el.addEventListener("input", e => {
      const k = e.target.dataset.poids;
      state.poids[k] = Number(e.target.value);
      document.getElementById("v_" + k).textContent = e.target.value;
      majCarte();
    });
  });
}

function construireCouches() {
  document.getElementById("couches").innerHTML = COUCHES.map(c => `
    <label class="field" style="display:flex;gap:8px;align-items:center">
      <input type="checkbox" data-couche="${c.id}" ${c.visible ? "checked" : ""}>
      <span style="margin:0">${c.nom}</span>
    </label>`).join("");
  document.querySelectorAll("input[data-couche]").forEach(el => {
    el.addEventListener("change", e => {
      const id = e.target.dataset.couche;
      const vis = e.target.checked ? "visible" : "none";
      for (const suffix of ["", "_cercle", "_etiquette", "_bord"]) {
        if (state.map.getLayer(id + suffix))
          state.map.setLayoutProperty(id + suffix, "visibility", vis);
      }
    });
  });
}

function construireExemples() {
  const ex = [
    "Trouve les 5 zones présentant le meilleur potentiel pour une nouvelle agence.",
    "Où ouvrir une agence accessible, avec beaucoup de commerces et peu de concurrence ?",
    "Donne-moi les 3 meilleures zones à Yaoundé V pour une clientèle aisée.",
    "Top 4 des zones bien desservies par les routes, à plus de 2 km d'une banque."
  ];
  document.getElementById("exemples").innerHTML = ex
    .map(t => `<button type="button">${t}</button>`).join("");
  document.querySelectorAll("#exemples button").forEach((b, i) => {
    b.addEventListener("click", () => {
      document.getElementById("question").value = ex[i];
      lancerAgent(ex[i]);
    });
  });
}

function criteresDepuisEtat() {
  return {
    ponderations: {
      demande: state.poids.demande / 100,
      accessibilite: state.poids.accessibilite / 100,
      attractivite: state.poids.attractivite / 100,
      concurrence: state.poids.concurrence / 100
    },
    arrondissements: state.filtres.arrondissement ? [state.filtres.arrondissement] : [],
    distanceMinM: Number(state.filtres.distance) || null,
    nbZones: state.cellules.length
  };
}

function majCarte() {
  if (!state.map || !state.map.getSource("hexagones")) return;
  const criteres = criteresDepuisEtat();
  const zones = classerZones(state.cellules, criteres, { scoreMin: state.filtres.scoreMin });
  const parId = Object.fromEntries(zones.map(z => [z.cell_id, z.score_question]));

  const fc = JSON.parse(JSON.stringify(state.hexagonesBrut));
  for (const f of fc.features) {
    const sc = parId[f.properties.cell_id];
    f.properties.score_aff = sc === undefined ? null : Number(sc.toFixed(1));
    f.properties.couleur = sc === undefined ? "#eef2f6" : couleurPour(sc);
  }
  state.map.getSource("hexagones").setData(fc);

  const visibles = zones.filter(z => z.score_question > 0);
  state.zonesActives = visibles;
  majClassement(visibles.slice(0, 12));
  majMarqueurs(visibles.slice(0, 20));
}

function majClassement(zones) {
  const el = document.getElementById("classement");
  el.innerHTML = zones.map((z, i) => `
    <div class="zone" data-lon="${z.lon}" data-lat="${z.lat}">
      <div class="head"><span class="nom">${i + 1}. ${z.arrondissement}</span>
        <span class="sc">${z.score_question.toFixed(1)}</span></div>
      <div class="det">${z.profil_marche} · ${z.nb_commerces} commerces, ${z.nb_education} écoles,
        ${z.nb_sante} structures de santé<br>Banque la plus proche : ${z.enseigne_plus_proche}
        à ${Math.round(z.dist_min_m)} m</div>
    </div>`).join("");
  el.querySelectorAll(".zone").forEach(d => {
    d.addEventListener("click", () => {
      state.map.flyTo({ center: [Number(d.dataset.lon), Number(d.dataset.lat)], zoom: 14 });
    });
  });
}

function majMarqueurs(zones) {
  const src = state.map.getSource("top20");
  if (!src) return;
  src.setData({
    type: "FeatureCollection",
    features: zones.map((z, i) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [Number(z.lon), Number(z.lat)] },
      properties: { rang: i + 1, score: z.score_question.toFixed(1),
                    arrondissement: z.arrondissement }
    }))
  });
}

function majModele() {
  const m = state.modele?.substitut;
  if (!m) return;
  const imp = (m.importance || []).slice(0, 5);
  document.getElementById("modele").innerHTML = `
    <div><b>Segmentation</b> : ${state.modele.segmentation.k_retenu} profils de marché
      (silhouette ${state.modele.segmentation.silhouette})</div>
    <div style="margin-top:8px"><b>Modèle de substitution</b> : R² ${m.r2_validation_croisee}
      en validation croisée, erreur moyenne ${m.mae_points} point</div>
    <div style="margin-top:8px"><b>Indicateurs les plus déterminants</b></div>
    ${imp.map(x => `<div style="font-size:11.5px">${x.indicateur}
      <div class="barre"><i style="width:${(x.importance * 100 / imp[0].importance).toFixed(0)}%"></i></div>
      </div>`).join("")}
    <div style="margin-top:6px;font-size:11px">${m.note}</div>`;
}

function lancerAgent(question) {
  const criteres = extraireCriteres(question);
  const zones = classerZones(state.cellules, criteres, { scoreMin: state.filtres.scoreMin });
  document.getElementById("reponse").textContent = redigerReponse(criteres, zones);
  majClassement(zones);
  majMarqueurs(zones);
  if (zones.length) state.map.flyTo({
    center: [Number(zones[0].lon), Number(zones[0].lat)], zoom: 13.2
  });
}

function initCarte() {
  const map = new maplibregl.Map({
    container: "map",
    style: {
      version: 8,
      sources: {
        osm: {
          type: "raster",
          tiles: ["https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png"],
          tileSize: 256,
          attribution: "© OpenStreetMap, © CARTO"
        }
      },
      layers: [{ id: "osm", type: "raster", source: "osm",
                 paint: { "raster-opacity": 0.55 } }]
    },
    center: [11.50, 3.87],
    zoom: 11.6
  });
  state.map = map;

  map.on("load", () => {
    const vide = { type: "FeatureCollection", features: [] };
    map.addSource("hexagones", { type: "geojson", data: state.hexagonesBrut });
    map.addSource("quartiers", { type: "geojson", data: state.quartiers });
    map.addSource("routes", { type: "geojson", data: state.routes });
    map.addSource("agences", { type: "geojson", data: state.agences });
    map.addSource("equipements", { type: "geojson", data: state.equipements });
    map.addSource("top20", { type: "geojson", data: vide });

    map.addLayer({
      id: "hexagones", type: "fill", source: "hexagones",
      paint: {
        "fill-color": ["get", "couleur"],
        "fill-opacity": ["case", ["==", ["get", "score_aff"], null], 0.16, 0.72]
      }
    });
    map.addLayer({
      id: "hexagones_bord", type: "line", source: "hexagones",
      paint: { "line-color": "#ffffff", "line-width": 0.3, "line-opacity": 0.5 }
    });
    map.addLayer({
      id: "quartiers", type: "line", source: "quartiers", layout: { visibility: "none" },
      paint: { "line-color": "#8a97a6", "line-width": 1.1, "line-dasharray": [3, 2] }
    });
    map.addLayer({
      id: "routes", type: "line", source: "routes",
      paint: {
        "line-color": ["match", ["get", "classe"],
          "motorway", "#b45309", "trunk", "#d97706", "primary", "#f59e0b",
          "secondary", "#fbbf24", "#fcd34d"],
        "line-width": ["match", ["get", "classe"],
          "motorway", 2.6, "trunk", 2.2, "primary", 1.8, "secondary", 1.3, 1]
      }
    });
    map.addLayer({
      id: "agences", type: "circle", source: "agences",
      paint: {
        "circle-radius": 5, "circle-color": "#b91c1c",
        "circle-stroke-color": "#ffffff", "circle-stroke-width": 1.3
      }
    });
    map.addLayer({
      id: "equipements", type: "circle", source: "equipements",
      layout: { visibility: "none" },
      paint: { "circle-radius": 3, "circle-color": "#15803d", "circle-opacity": 0.75 }
    });
    map.addLayer({
      id: "top20", type: "circle", source: "top20",
      paint: {
        "circle-radius": 9, "circle-color": "rgba(217,119,6,0.22)",
        "circle-stroke-color": "#d97706", "circle-stroke-width": 1.8
      }
    });
    map.addLayer({
      id: "top20_etiquette", type: "symbol", source: "top20",
      layout: {
        "text-field": ["to-string", ["get", "rang"]], "text-size": 10.5,
        "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"]
      },
      paint: { "text-color": "#0B2545" }
    });

    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
    map.on("mousemove", "hexagones", e => {
      const p = e.features[0].properties;
      if (p.score_aff === null) { popup.remove(); return; }
      popup.setLngLat(e.lngLat).setHTML(`
        <div style="font-size:12px;line-height:1.5">
          <b>${p.arrondissement}</b><br>${p.profil_marche}<br>
          Score ${p.score_aff}/100 · rang ${p.rang_net}<br>
          ${p.nb_commerces} commerces · ${p.nb_education} écoles · ${p.nb_sante} santé<br>
          Banque la plus proche : ${p.enseigne_plus_proche}<br>à ${Math.round(p.dist_min_m)} m</div>`)
        .addTo(map);
    });
    map.on("mouseleave", "hexagones", () => popup.remove());
    map.on("mousemove", "agences", e => {
      popup.setLngLat(e.lngLat)
        .setHTML(`<div style="font-size:12px"><b>${e.features[0].properties.enseigne}</b></div>`)
        .addTo(map);
    });
    map.on("mouseleave", "agences", () => popup.remove());

    majCarte();
  });
}

async function init() {
  const [hex, arr, quart, routes, agences, equip, classement, kpis, modele] =
    await Promise.all([
      chargerJson("hexagones.geojson"), chargerJson("arrondissements.geojson"),
      chargerJson("quartiers.geojson"), chargerJson("routes.geojson"),
      chargerJson("agences.geojson"), chargerJson("equipements.geojson"),
      chargerJson("classement.json"), chargerJson("kpis.json"), chargerJson("modele.json")
    ]);
  Object.assign(state, {
    hexagonesBrut: hex, arrondissements: arr, quartiers: quart,
    routes, agences, equipements: equip, classement, kpis, modele,
    cellules: hex.features.map(f => ({ cell_id: f.properties.cell_id, ...f.properties }))
  });
  construireKpis(); construireSliders(); construireCouches(); construireExemples();
  majModele();
  initCarte();
  majCarte();
}

async function demarrer() {
  await init();
  const sel = document.getElementById("filtreArr");
  const parArr = await chargerJson("arrondissements_scores.json");
  parArr.forEach(a => {
    const o = document.createElement("option");
    o.value = a.arrondissement;
    o.textContent = `${a.arrondissement} (${a.score_moyen})`;
    sel.appendChild(o);
  });
  sel.addEventListener("change", e => {
    state.filtres.arrondissement = e.target.value; majCarte();
  });
  document.getElementById("filtreDist").addEventListener("change", e => {
    state.filtres.distance = Number(e.target.value); majCarte();
  });
  document.getElementById("filtreScore").addEventListener("input", e => {
    state.filtres.scoreMin = Number(e.target.value);
    document.getElementById("filtreScoreVal").textContent = e.target.value;
    majCarte();
  });
  document.getElementById("formAgent").addEventListener("submit", e => {
    e.preventDefault();
    const q = document.getElementById("question").value.trim();
    if (q) lancerAgent(q);
  });
  document.getElementById("reset").addEventListener("click", () => {
    state.poids = { demande: 40, accessibilite: 25, attractivite: 20, concurrence: 15 };
    state.filtres = { arrondissement: "", distance: 0, scoreMin: 0 };
    construireSliders();
    document.getElementById("filtreArr").value = "";
    document.getElementById("filtreDist").value = "0";
    document.getElementById("filtreScore").value = 0;
    document.getElementById("filtreScoreVal").textContent = "0";
    majCarte();
  });
  lancerAgent("Trouve les 5 zones présentant le meilleur potentiel pour une nouvelle agence.");
}

demarrer().catch(err => {
  document.getElementById("reponse").textContent = "Erreur de chargement : " + err.message;
  console.error(err);
});
