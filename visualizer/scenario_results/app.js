const SCENARIO_LABELS = {
  green_maximum: "Rohelahendus",
  food_security: "Toidujulgeolek",
  low_budget: "Väike eelarve",
  wetland_priority: "Märgala prioriteet",
  sustainable_agriculture: "Kestlik põllumajandus",
  balanced: "Tasakaalustatud",
};

const SCENARIO_DESCRIPTIONS = {
  green_maximum: "Maksimaalne ökoloogiline kasu väiksema põllumajanduse kaitsega.",
  food_security: "Põllumaa säilitamisele suunatud lahendus.",
  low_budget: "Vähese sekkumise ja madalama kuluga lahendus.",
  wetland_priority: "Taassoostamisele ja märgala kasvule keskenduv lahendus.",
  sustainable_agriculture: "Põllumajandusmaa netokasvu nõude ja ökoloogiliste piirangutega lahendus.",
  balanced: "Elurikkuse, süsiniku, kulu ja muutuse ulatuse tasakaalustatud kompromiss.",
};

const METRICS = [
  ["Biodiversity gain", "Elurikkuse kasv", "modelPercent"],
  ["Carbon gain", "Süsinikukasu", "modelPercent"],
  ["Cost", "Sekkumise kulu", "cost"],
  ["Changed land", "Muutunud maa", "percent"],
  ["Agriculture loss", "Põllumaa kadu", "percent"],
  ["Agriculture gain", "Põllumaa kasv", "percent"],
  ["Wetland gain", "Märgala kasv", "percent"],
];

const ACTION_COLORS = {
  no_change: "#d7ddd6",
  forest: "#176b4d",
  wetland: "#287ba5",
  agriculture: "#d69d3b",
  grassland: "#8dbc74",
};

const state = { data: null, scenario: "balanced", mapLayer: "action", chartMetric: "Biodiversity gain" };

const scenarioSelector = document.getElementById("scenario-selector");
const mapLayerSelector = document.getElementById("map-layer");
const chartMetricSelector = document.getElementById("comparison-metric");

function formatValue(value, kind) {
  const number = Number(value || 0);
  if (kind === "cost") return number.toFixed(3);
  return `${(number * 100).toFixed(2)}%`;
}

function layerColor(layer, value) {
  if (layer === "action") return ACTION_COLORS[value] || "#b3bab5";
  const magnitude = Math.min(Math.abs(Number(value || 0)) / (layer === "change_intensity" ? 0.25 : 0.15), 1);
  if (layer === "change_intensity") return `rgb(${Math.round(244 - 120 * magnitude)}, ${Math.round(246 - 80 * magnitude)}, ${Math.round(235 - 180 * magnitude)})`;
  return value >= 0 ? `rgb(${Math.round(235 - 150 * magnitude)}, ${Math.round(246 - 50 * magnitude)}, ${Math.round(235 - 135 * magnitude)})` : `rgb(${Math.round(245)}, ${Math.round(238 - 155 * magnitude)}, ${Math.round(235 - 150 * magnitude)})`;
}

function mapLegend() {
  const container = document.getElementById("map-legend");
  if (state.mapLayer === "action") {
    container.innerHTML = Object.entries(ACTION_COLORS).map(([key, color]) => `<span class="legend-item"><i class="swatch" style="background:${color}"></i>${({no_change: "Muutuseta", forest: "Mets", wetland: "Märgala", agriculture: "Põllumajandus", grassland: "Rohumaa"})[key]}</span>`).join("");
  } else {
    container.innerHTML = `<span class="legend-item"><i class="swatch" style="background:#eaf6eb"></i>Väike muutus</span><span class="legend-item"><i class="swatch" style="background:#558e64"></i>Suur positiivne muutus</span><span class="legend-item"><i class="swatch" style="background:#b64e43"></i>Negatiivne muutus</span>`;
  }
}

function populateScenarioSelector() {
  scenarioSelector.innerHTML = Object.keys(state.data.scenarios)
    .map((id) => `<option value="${id}">${SCENARIO_LABELS[id] || id}</option>`)
    .join("");
  scenarioSelector.value = state.scenario;
}

function renderMetrics() {
  const summary = state.data.scenarios[state.scenario];
  document.getElementById("scenario-description").textContent = SCENARIO_DESCRIPTIONS[state.scenario] || "";
  document.getElementById("scenario-status").textContent = summary.Status === "feasible" ? "Teostatav lahendus" : "Piirangut rikkuv lahendus";
  document.getElementById("metric-cards").innerHTML = METRICS.map(([key, label, kind]) => `<article class="metric"><h3>${label}</h3><strong>${formatValue(summary[key], kind)}</strong><small>${kind === "cost" ? "Suhteline kulude indeks" : "Mudelisisendite põhjal"}</small></article>`).join("");
}

function renderComparison() {
  const rows = Object.entries(state.data.scenarios).map(([id, summary]) => {
    const active = id === state.scenario ? "active" : "";
    return `<tr class="${active}"><td><strong>${SCENARIO_LABELS[id] || id}</strong></td><td>${formatValue(summary["Biodiversity gain"], "modelPercent")}</td><td>${formatValue(summary["Carbon gain"], "modelPercent")}</td><td>${formatValue(summary.Cost, "cost")}</td><td>${formatValue(summary["Changed land"], "percent")}</td><td>${formatValue(summary["Agriculture gain"] - summary["Agriculture loss"], "percent")}</td><td>${formatValue(summary["Wetland gain"], "percent")}</td></tr>`;
  });
  document.getElementById("comparison-table").innerHTML = rows.join("");
}

function geometryBounds(features) {
  const bounds = [Infinity, Infinity, -Infinity, -Infinity];
  function visit(coords) {
    if (typeof coords[0] === "number") { bounds[0] = Math.min(bounds[0], coords[0]); bounds[1] = Math.min(bounds[1], coords[1]); bounds[2] = Math.max(bounds[2], coords[0]); bounds[3] = Math.max(bounds[3], coords[1]); return; }
    coords.forEach(visit);
  }
  features.forEach((feature) => visit(feature.geometry.coordinates));
  return bounds;
}

function drawMap() {
  if (!state.data) return;
  const canvas = document.getElementById("scenario-map");
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(rect.width * ratio);
  canvas.height = Math.round(rect.height * ratio);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, rect.width, rect.height);
  const [minX, minY, maxX, maxY] = geometryBounds(state.data.grid.features);
  const padding = 12;
  const scale = Math.min((rect.width - padding * 2) / (maxX - minX), (rect.height - padding * 2) / (maxY - minY));
  const offsetX = (rect.width - (maxX - minX) * scale) / 2;
  const offsetY = (rect.height - (maxY - minY) * scale) / 2;
  const project = ([x, y]) => [offsetX + (x - minX) * scale, rect.height - offsetY - (y - minY) * scale];
  const values = state.data.maps[state.scenario];

  function polygon(coords) {
    coords.forEach((ring) => {
      ring.forEach((point, index) => { const [x, y] = project(point); index ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
      ctx.closePath();
    });
  }

  state.data.grid.features.forEach((feature) => {
    const value = values[String(feature.properties.cell_id)]?.[state.mapLayer];
    ctx.beginPath();
    if (feature.geometry.type === "Polygon") polygon(feature.geometry.coordinates);
    else feature.geometry.coordinates.forEach(polygon);
    ctx.fillStyle = layerColor(state.mapLayer, value);
    ctx.fill();
  });
  mapLegend();
}

function drawComparisonChart() {
  const canvas = document.getElementById("comparison-chart");
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(rect.width * ratio);
  canvas.height = Math.round(rect.height * ratio);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, rect.width, rect.height);
  const entries = Object.entries(state.data.scenarios);
  const values = entries.map(([, item]) => Number(item[state.chartMetric] || 0));
  const maximum = Math.max(...values.map(Math.abs), 0.01);
  const margin = { top: 24, right: 24, bottom: 58, left: 48 };
  const chartHeight = rect.height - margin.top - margin.bottom;
  const width = (rect.width - margin.left - margin.right) / entries.length;
  ctx.strokeStyle = "#cbd7cf";
  ctx.beginPath(); ctx.moveTo(margin.left, margin.top + chartHeight); ctx.lineTo(rect.width - margin.right, margin.top + chartHeight); ctx.stroke();
  entries.forEach(([id], index) => {
    const value = values[index];
    const barHeight = Math.abs(value) / maximum * chartHeight;
    const x = margin.left + index * width + width * .18;
    const y = value >= 0 ? margin.top + chartHeight - barHeight : margin.top + chartHeight;
    ctx.fillStyle = id === state.scenario ? "#176b4d" : "#9db6a5";
    ctx.fillRect(x, y, width * .64, value >= 0 ? barHeight : -barHeight);
    ctx.fillStyle = "#213730";
    ctx.font = "12px system-ui";
    ctx.textAlign = "center";
    ctx.fillText(SCENARIO_LABELS[id], x + width * .32, rect.height - 18);
    ctx.fillText(state.chartMetric === "Cost" ? value.toFixed(3) : `${(value * 100).toFixed(2)}%`, x + width * .32, Math.max(14, y - 6));
  });
}

function selectScenario(id) {
  state.scenario = id;
  scenarioSelector.value = id;
  renderMetrics();
  renderComparison();
  drawMap();
  drawComparisonChart();
}

function render() { selectScenario(state.scenario); }

async function loadDashboard() {
  try {
    const response = await fetch("data/scenario-results.json");
    if (!response.ok) throw new Error("Andmefaili ei leitud.");
    state.data = await response.json();
    if (!state.data.scenarios[state.scenario]) state.scenario = Object.keys(state.data.scenarios)[0];
    populateScenarioSelector();
    render();
  } catch (error) {
    document.querySelector(".dashboard").insertAdjacentHTML("afterbegin", `<p class="error">Juhtpaneeli andmeid ei õnnestunud laadida. Genereeri esmalt fail <code>data/scenario-results.json</code> ja ava leht veebiserverist.</p>`);
  }
}

scenarioSelector.addEventListener("change", (event) => selectScenario(event.target.value));
mapLayerSelector.addEventListener("change", (event) => { state.mapLayer = event.target.value; drawMap(); });
chartMetricSelector.addEventListener("change", (event) => { state.chartMetric = event.target.value; drawComparisonChart(); });
window.addEventListener("resize", () => { drawMap(); drawComparisonChart(); });
loadDashboard();
