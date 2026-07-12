/**
 * Estonia Land-Use Scenario Explorer
 * Interactive visualizer with Leaflet maps.
 */

// --- Constants ---
const TOTAL_CELLS = 2806;
const CELL_AREA_HA = 100;
const HORIZON_YEARS = 20;

// Carbon: tCO2/ha/year [low, mid, high]
const C = {
  afforest: [4.0, 7.0, 15.0],
  rewet_peat: [15.0, 23.0, 30.0],
  rewet_mineral: [1.0, 3.0, 5.0],
  grassland: [0.8, 1.5, 3.0],
};
// Cost: EUR/ha [low, mid, high]
const K = {
  afforest: [1500, 2500, 4000],
  rewet_peat: [2000, 5000, 15000],
  rewet_mineral: [1500, 4000, 12000],
  grassland: [300, 600, 1200],
  opp_yr: [100, 180, 300],
};

const PRESETS = {
  balanced: { afforest: 30, wetland: 15, area: 25, peat: 35 },
  'max-forest': { afforest: 70, wetland: 5, area: 35, peat: 20 },
  'restore-wetland': { afforest: 10, wetland: 60, area: 20, peat: 60 },
  protect: { afforest: 5, wetland: 5, area: 8, peat: 30 },
  custom: null,
};

const ACTION_COLORS = {
  afforest: '#2d7d46',
  restore_wetland: '#1f78b4',
  grassland: '#b2df8a',
  no_change: '#dddddd',
  constrained: '#888888',
};

// --- State ---
let geojsonData = null;
let mapAction = null;
let mapBio = null;
let actionLayer = null;
let bioLayer = null;

// --- DOM ---
const sliders = {
  afforest: document.getElementById('sl-afforest'),
  wetland: document.getElementById('sl-wetland'),
  area: document.getElementById('sl-area'),
  peat: document.getElementById('sl-peat'),
};
const vals = {
  afforest: document.getElementById('val-afforest'),
  wetland: document.getElementById('val-wetland'),
  area: document.getElementById('val-area'),
  peat: document.getElementById('val-peat'),
};
const resultsDiv = document.getElementById('results');
const tabs = document.querySelectorAll('.scenario-tab');


// --- Action assignment per cell ---
function assignAction(props, afforestPct, wetlandPct, areaPct) {
  // Constrained cells: high urban/water or protected
  if ((props.urban_pct || 0) > 0.5 || (props.water_pct || 0) > 0.5) return 'constrained';
  if ((props.protected_overlap_pct || 0) > 0.8) return 'constrained';

  // Score each cell for action suitability
  const bio = props.rohemeeter_norm || 0.5;
  const wetSuit = props.wetland_suitability || 0;
  const forestPct = props.forest_pct || 0;
  const agriPct = props.agriculture_pct || 0;

  // High biodiversity → protect (no change)
  if (bio > 0.8 && Math.random() > areaPct) return 'no_change';

  // Threshold: only change a fraction of cells based on area slider
  if (Math.random() > areaPct * 1.5) return 'no_change';

  // Wetland restoration: needs suitability + user wants it
  if (wetSuit > 0.3 && Math.random() < wetlandPct && agriPct > 0.1) {
    return 'restore_wetland';
  }

  // Afforestation: broad applicability
  if (forestPct < 0.7 && Math.random() < afforestPct && agriPct > 0.05) {
    return 'afforest';
  }

  // Grassland: fallback for remaining changes
  if (agriPct > 0.3 && Math.random() < 0.3) return 'grassland';

  return 'no_change';
}

// --- Calculation ---
function calculate() {
  const af = parseInt(sliders.afforest.value) / 100;
  const wt = parseInt(sliders.wetland.value) / 100;
  const ar = parseInt(sliders.area.value) / 100;
  const pt = parseInt(sliders.peat.value) / 100;

  const totalHa = TOTAL_CELLS * CELL_AREA_HA * ar;
  const haAf = totalHa * af;
  const haWt = totalHa * wt;
  const haWtPeat = haWt * pt;
  const haWtMin = haWt * (1 - pt);
  const haGr = totalHa * Math.max(0, 1 - af - wt) * 0.3;

  const carbon = [0, 1, 2].map(i =>
    haAf * C.afforest[i] + haWtPeat * C.rewet_peat[i] +
    haWtMin * C.rewet_mineral[i] + haGr * C.grassland[i]
  );
  const cost = [0, 1, 2].map(i =>
    haAf * K.afforest[i] + haWtPeat * K.rewet_peat[i] +
    haWtMin * K.rewet_mineral[i] + haGr * K.grassland[i] +
    totalHa * 0.7 * K.opp_yr[i] * HORIZON_YEARS
  );

  const bio = (1 - ar) * 0.66 * 0.12 +
    af * ar * 0.6 * 0.34 * 0.6 +
    wt * ar * 0.8 * 0.34 * 0.34;

  return { carbon, cost, bio, totalKm2: totalHa / 100, haAf, haWt, haGr };
}

// --- Render metrics ---
function renderMetrics() {
  vals.afforest.textContent = sliders.afforest.value + '%';
  vals.wetland.textContent = sliders.wetland.value + '%';
  vals.area.textContent = sliders.area.value + '%';
  vals.peat.textContent = sliders.peat.value + '%';

  const r = calculate();
  const fmt = n => Math.abs(n) >= 1e3 ? (n/1e3).toFixed(1)+'k' : n.toFixed(0);

  resultsDiv.innerHTML = `
    <div class="card"><h3>CO₂ sequestered</h3>
      <div class="value positive">${fmt(r.carbon[1])}</div>
      <div class="ci">tCO₂/yr [${fmt(r.carbon[0])}–${fmt(r.carbon[2])}]</div></div>
    <div class="card"><h3>Cost (${HORIZON_YEARS}yr)</h3>
      <div class="value neutral">€${(r.cost[1]/1e6).toFixed(1)}M</div>
      <div class="ci">[€${(r.cost[0]/1e6).toFixed(1)}M–€${(r.cost[2]/1e6).toFixed(1)}M]</div></div>
    <div class="card"><h3>Biodiversity</h3>
      <div class="value positive">${(r.bio*100).toFixed(2)}</div>
      <div class="ci">proxy score ×100</div></div>
    <div class="card"><h3>Area changed</h3>
      <div class="value neutral">${r.totalKm2.toFixed(0)} km²</div>
      <div class="ci">${(r.totalKm2/TOTAL_CELLS*100).toFixed(1)}% of county</div></div>
    <div class="card"><h3>€/tCO₂/yr</h3>
      <div class="value neutral">€${(r.cost[1]/Math.max(r.carbon[1],1)).toFixed(0)}</div>
      <div class="ci">cost efficiency</div></div>
  `;
}


// --- Map rendering ---
function bioColor(val) {
  // RdYlGn colormap: 0=red, 0.5=yellow, 1=green
  const v = Math.max(0, Math.min(1, val));
  if (v < 0.5) {
    const t = v * 2;
    const r = Math.round(215 - t * 50);
    const g = Math.round(48 + t * 200);
    const b = Math.round(39 + t * 50);
    return `rgb(${r},${g},${b})`;
  } else {
    const t = (v - 0.5) * 2;
    const r = Math.round(165 - t * 139);
    const g = Math.round(248 - t * 96);
    const b = Math.round(89 - t * 9);
    return `rgb(${r},${g},${b})`;
  }
}

function updateActionMap() {
  if (!geojsonData || !mapAction) return;

  const af = parseInt(sliders.afforest.value) / 100;
  const wt = parseInt(sliders.wetland.value) / 100;
  const ar = parseInt(sliders.area.value) / 100;

  if (actionLayer) mapAction.removeLayer(actionLayer);

  // Seed random for reproducibility per setting
  let seed = Math.round(af * 100 + wt * 1000 + ar * 10000);
  const seededRandom = () => {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  };

  // Override Math.random temporarily for deterministic assignment
  const origRandom = Math.random;
  Math.random = seededRandom;

  actionLayer = L.geoJSON(geojsonData, {
    style: feature => {
      const action = assignAction(feature.properties, af, wt, ar);
      return {
        fillColor: ACTION_COLORS[action] || '#ddd',
        fillOpacity: 0.75,
        weight: 0.3,
        color: '#666',
        opacity: 0.3,
      };
    },
    onEachFeature: (feature, layer) => {
      const p = feature.properties;
      const action = assignAction(p, af, wt, ar);
      layer.bindPopup(`
        <b>Cell ${p.cell_id}</b><br>
        Action: <b>${action}</b><br>
        Forest: ${((p.forest_pct||0)*100).toFixed(0)}%
        Agri: ${((p.agriculture_pct||0)*100).toFixed(0)}%<br>
        Wetland suit: ${((p.wetland_suitability||0)*100).toFixed(0)}%
        Rohemeeter: ${((p.rohemeeter_norm||0)*100).toFixed(0)}
      `);
    },
  }).addTo(mapAction);

  Math.random = origRandom;
}

function initBioMap() {
  if (!geojsonData || !mapBio) return;

  if (bioLayer) mapBio.removeLayer(bioLayer);

  bioLayer = L.geoJSON(geojsonData, {
    style: feature => ({
      fillColor: bioColor(feature.properties.rohemeeter_norm || 0.5),
      fillOpacity: 0.8,
      weight: 0.3,
      color: '#666',
      opacity: 0.3,
    }),
    onEachFeature: (feature, layer) => {
      const p = feature.properties;
      layer.bindPopup(`
        <b>Cell ${p.cell_id}</b><br>
        Rohemeeter: <b>${((p.rohemeeter_norm||0)*100).toFixed(0)}/100</b><br>
        Forest: ${((p.forest_pct||0)*100).toFixed(0)}%
        Wetland: ${((p.wetland_pct||0)*100).toFixed(0)}%<br>
        Protected: ${((p.protected_overlap_pct||0)*100).toFixed(0)}%
      `);
    },
  }).addTo(mapBio);
}

// --- Init maps ---
function initMaps() {
  mapAction = L.map('map-action').setView([58.95, 23.7], 9);
  mapBio = L.map('map-bio').setView([58.95, 23.7], 9);

  const tiles = 'https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png';
  const attr = '&copy; OpenStreetMap, &copy; CARTO';

  L.tileLayer(tiles, { attribution: attr, maxZoom: 15 }).addTo(mapAction);
  L.tileLayer(tiles, { attribution: attr, maxZoom: 15 }).addTo(mapBio);
}

// --- Load data and start ---
async function init() {
  initMaps();
  renderMetrics();

  try {
    const resp = await fetch('grid.geojson');
    geojsonData = await resp.json();
    updateActionMap();
    initBioMap();
  } catch (e) {
    console.error('Failed to load grid.geojson:', e);
    document.getElementById('map-action').innerHTML =
      '<p style="padding:2rem;color:#c53030">Failed to load grid.geojson. Run: uv run python visualizer/export_geojson.py</p>';
  }
}

// --- Events ---
Object.values(sliders).forEach(sl => {
  sl.addEventListener('input', () => {
    tabs.forEach(t => t.classList.remove('active'));
    document.querySelector('[data-scenario="custom"]').classList.add('active');
    renderMetrics();
    updateActionMap();
  });
});

tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    const preset = PRESETS[tab.dataset.scenario];
    tabs.forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    if (preset) {
      sliders.afforest.value = preset.afforest;
      sliders.wetland.value = preset.wetland;
      sliders.area.value = preset.area;
      sliders.peat.value = preset.peat;
    }
    renderMetrics();
    updateActionMap();
  });
});

init();
