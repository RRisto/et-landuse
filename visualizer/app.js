/** Saved Estonian land-use scenarios rendered with Leaflet. */

const SCENARIOS = [
  { id: 'balanced', label: 'Tasakaalustatud' },
  { id: 'food_security', label: 'Toidujulgeolek' },
  { id: 'green_maximum', label: 'Roheline maksimum' },
  { id: 'low_budget', label: 'Väike eelarve' },
  { id: 'sustainable_agriculture', label: 'Kestlik põllumajandus' },
  { id: 'wetland_priority', label: 'Märgalade eelistus' },
];
const ACTION_COLORS = { forest: '#2d7d46', wetland: '#1f78b4', grassland: '#b2df8a', agriculture: '#f4a261', no_change: '#dddddd' };
const METRICS = [
  ['Biodiversity gain', 'Elurikkuse muutus', percent], ['Carbon gain', 'Süsiniku muutus', percent], ['Cost', 'Kulu', decimal],
  ['Changed land', 'Muutunud maa', percent], ['Agriculture loss', 'Põllumajandusmaa kadu', percent], ['Agriculture gain', 'Põllumajandusmaa kasv', percent],
  ['Gross agriculture gain', 'Põllumajandusmaa kogukasv', percent], ['Wetland gain', 'Märgala kasv', percent],
];
const CURRENT_COLORS = { forest: '#228b22', wetland: '#4682b4', agriculture: '#daa520', grassland: '#90ee90' };
let selectedScenario = 'balanced'; let geojsonData; let summaryRows = []; let mapCurrent; let mapAction; let currentLayer; let actionLayer;

function percent(value) { return `${(Number(value || 0) * 100).toFixed(2)}%`; }
function decimal(value) { return Number(value || 0).toFixed(3); }
function bioColor(value) { const v = Math.max(0, Math.min(1, value || 0)); return v < .5 ? `rgb(${Math.round(215-v*100)},${Math.round(48+v*400)},${Math.round(39+v*100)})` : `rgb(${Math.round(165-(v-.5)*278)},${Math.round(248-(v-.5)*192)},${Math.round(89-(v-.5)*18)})`; }

function renderTabs() {
  document.getElementById('scenario-tabs').innerHTML = SCENARIOS.map(({ id, label }) => `<button class="scenario-tab ${id === selectedScenario ? 'active' : ''}" data-scenario="${id}">${label}</button>`).join('');
  document.querySelectorAll('.scenario-tab').forEach(tab => tab.addEventListener('click', () => selectScenario(tab.dataset.scenario)));
}
function renderComparison() {
  const head = `<tr><th>Stsenaarium</th>${METRICS.map(([, label]) => `<th>${label}</th>`).join('')}</tr>`;
  const body = summaryRows.map(row => `<tr class="${row['Selection rule'] === selectedScenario ? 'selected' : ''}"><td>${row.Scenario}</td>${METRICS.map(([field,, format]) => `<td>${format(row[field])}</td>`).join('')}</tr>`).join('');
  document.getElementById('comparison-table').innerHTML = `<table><thead>${head}</thead><tbody>${body}</tbody></table>`;
}
function renderActionMap() {
  if (!geojsonData) return;
  if (actionLayer) mapAction.removeLayer(actionLayer);
  actionLayer = L.geoJSON(geojsonData, { style: feature => ({ fillColor: ACTION_COLORS[feature.properties.action] || '#888', fillOpacity: .78, weight: .3, color: '#666', opacity: .3 }), onEachFeature: (feature, layer) => layer.bindPopup(`<b>Ruut ${feature.properties.cell_id}</b><br>Suurim kasv: <b>${feature.properties.action}</b>`) }).addTo(mapAction);
}
function renderCurrentMap() {
  if (!geojsonData) return;
  if (currentLayer) mapCurrent.removeLayer(currentLayer);
  currentLayer = L.geoJSON(geojsonData, { style: feature => {
    const p = feature.properties;
    const groups = ['forest', 'wetland', 'agriculture', 'grassland'];
    const dominant = groups.reduce((best, group) => Number(p[`current_${group}`] || 0) > Number(p[`current_${best}`] || 0) ? group : best, groups[0]);
    return { fillColor: CURRENT_COLORS[dominant], fillOpacity: .78, weight: .3, color: '#666', opacity: .3 };
  }, onEachFeature: (feature, layer) => {
    const p = feature.properties;
    const groups = ['forest', 'wetland', 'agriculture', 'grassland'];
    const dominant = groups.reduce((best, group) => Number(p[`current_${group}`] || 0) > Number(p[`current_${best}`] || 0) ? group : best, groups[0]);
    layer.bindPopup(`<b>Ruut ${p.cell_id}</b><br>Praegu domineerib: <b>${dominant}</b>`);
  }}).addTo(mapCurrent);
}
async function selectScenario(scenario) {
  selectedScenario = scenario; renderTabs(); renderComparison(); document.getElementById('map-status').textContent = 'Kaardi laadimine…';
  try { const response = await fetch(`scenario_maps/${scenario}.geojson`); if (!response.ok) throw new Error(response.statusText); geojsonData = await response.json(); renderCurrentMap(); renderActionMap(); const bounds = actionLayer.getBounds(); if (bounds.isValid()) { mapCurrent.fitBounds(bounds, { padding: [12, 12] }); mapAction.fitBounds(bounds, { padding: [12, 12] }); } document.getElementById('map-status').textContent = 'Kuvatakse salvestatud modelleerimistulemused.'; }
  catch (error) { console.error('Stsenaariumi laadimine ebaõnnestus:', error); document.getElementById('map-status').textContent = 'Stsenaariumi kaarti ei õnnestunud laadida.'; }
}
function initMaps() { mapCurrent = L.map('map-current').setView([58.95, 23.7], 9); mapAction = L.map('map-action').setView([58.95, 23.7], 9); const tiles = 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png'; const options = { attribution: '&copy; OpenStreetMap, &copy; CARTO', maxZoom: 15 }; L.tileLayer(tiles, options).addTo(mapCurrent); L.tileLayer(tiles, options).addTo(mapAction); }
async function init() { initMaps(); renderTabs(); try { const response = await fetch('scenario_summary.json'); if (!response.ok) throw new Error(response.statusText); summaryRows = await response.json(); renderComparison(); } catch (error) { console.error('Võrdlusandmete laadimine ebaõnnestus:', error); document.getElementById('comparison-table').innerHTML = '<p class="status">Võrdlusandmeid ei õnnestunud laadida.</p>'; } selectScenario(selectedScenario); }
init();
