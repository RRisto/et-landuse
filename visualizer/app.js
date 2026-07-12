/**
 * Estonia Land-Use Scenario Explorer
 * Interactive visualizer for land-use policy trade-offs.
 *
 * Uses Estonian-specific carbon and cost coefficients.
 */

// --- Constants (from carbon_tonnes.py and cost_eur.py) ---
const TOTAL_CELLS = 2806; // Lääne county grid cells
const CELL_AREA_HA = 100; // 1 km² = 100 ha

// Carbon rates: tCO2/ha/year [low, mid, high]
const CARBON_RATES = {
  afforest_mineral: [4.0, 7.0, 15.0],
  afforest_peat: [4.0, 7.0, 15.0], // same — afforestation doesn't depend much on peat
  rewet_peat: [15.0, 23.0, 30.0],
  rewet_mineral: [1.0, 3.0, 5.0],
  protect_forest: [2.0, 4.0, 6.0], // annual sequestration maintained
  protect_wetland: [0.0, 0.8, 2.0],
  grassland_convert: [0.8, 1.5, 3.0],
};

// Cost rates: EUR/ha [low, mid, high]
const COST_RATES = {
  afforest: [1500, 2500, 4000],
  rewet_peat: [2000, 5000, 15000],
  rewet_mineral: [1500, 4000, 12000],
  grassland: [300, 600, 1200],
  opportunity_agri_yr: [100, 180, 300],
};

const HORIZON_YEARS = 20;

// --- Presets ---
const PRESETS = {
  balanced: { afforest: 30, wetland: 15, area: 25, peat: 35 },
  'max-forest': { afforest: 70, wetland: 5, area: 35, peat: 20 },
  'restore-wetland': { afforest: 10, wetland: 60, area: 20, peat: 60 },
  protect: { afforest: 5, wetland: 5, area: 8, peat: 30 },
  custom: null,
};

// --- DOM refs ---
const slAfforest = document.getElementById('sl-afforest');
const slWetland = document.getElementById('sl-wetland');
const slArea = document.getElementById('sl-area');
const slPeat = document.getElementById('sl-peat');
const valAfforest = document.getElementById('val-afforest');
const valWetland = document.getElementById('val-wetland');
const valArea = document.getElementById('val-area');
const valPeat = document.getElementById('val-peat');
const resultsDiv = document.getElementById('results');
const barsDiv = document.getElementById('bars');
const tabs = document.querySelectorAll('.scenario-tab');

// --- Scenario calculation ---
function calculate() {
  const afforestPct = parseInt(slAfforest.value) / 100;
  const wetlandPct = parseInt(slWetland.value) / 100;
  const areaPct = parseInt(slArea.value) / 100;
  const peatShare = parseInt(slPeat.value) / 100;

  // Total area being changed
  const totalHaChanged = TOTAL_CELLS * CELL_AREA_HA * areaPct;
  const totalKm2Changed = totalHaChanged / 100;

  // Split changed area into action types
  const grasslandPct = Math.max(0, 1 - afforestPct - wetlandPct) * 0.3;
  const noChangePct = Math.max(0, 1 - afforestPct - wetlandPct - grasslandPct);

  const haAfforest = totalHaChanged * afforestPct;
  const haWetland = totalHaChanged * wetlandPct;
  const haGrassland = totalHaChanged * grasslandPct;
  const haProtect = TOTAL_CELLS * CELL_AREA_HA * (1 - areaPct); // unchanged area

  // Peat split for wetland restoration
  const haWetlandPeat = haWetland * peatShare;
  const haWetlandMineral = haWetland * (1 - peatShare);

  // --- Carbon calculation [low, mid, high] ---
  const carbonResults = [0, 1, 2].map(idx => {
    let tco2 = 0;
    tco2 += haAfforest * CARBON_RATES.afforest_mineral[idx];
    tco2 += haWetlandPeat * CARBON_RATES.rewet_peat[idx];
    tco2 += haWetlandMineral * CARBON_RATES.rewet_mineral[idx];
    tco2 += haGrassland * CARBON_RATES.grassland_convert[idx];
    // Protection bonus: maintained sequestration of existing forest/wetland
    // (simplified: ~50% of county is forest)
    const protectedForestHa = haProtect * 0.5;
    tco2 += protectedForestHa * CARBON_RATES.protect_forest[idx] * 0.1; // marginal bonus
    return tco2;
  });

  // --- Cost calculation [low, mid, high] ---
  const costResults = [0, 1, 2].map(idx => {
    let cost = 0;
    // Implementation
    cost += haAfforest * COST_RATES.afforest[idx];
    cost += haWetlandPeat * COST_RATES.rewet_peat[idx];
    cost += haWetlandMineral * COST_RATES.rewet_mineral[idx];
    cost += haGrassland * COST_RATES.grassland[idx];
    // Opportunity cost (lost agricultural income over horizon)
    const haFromAgri = totalHaChanged * 0.7; // assume 70% comes from agriculture
    cost += haFromAgri * COST_RATES.opportunity_agri_yr[idx] * HORIZON_YEARS;
    return cost;
  });

  // --- Biodiversity (simplified proxy) ---
  // Rohemeeter-informed: protection of high-bio cells + restoration of low-bio cells
  const bioScore = (
    (1 - areaPct) * 0.66 * 0.12 + // protection bonus (avg rohemeeter 0.66)
    afforestPct * areaPct * 0.6 * (1 - 0.66) * 0.6 +
    wetlandPct * areaPct * 0.8 * (1 - 0.66) * 0.34 // gated by wetland suitability ~0.34
  );

  return {
    carbon: carbonResults,
    cost: costResults,
    bioScore,
    totalKm2Changed,
    totalHaChanged,
    haAfforest,
    haWetland,
    haGrassland,
    haProtect: haProtect / 100, // in km²
  };
}

// --- Render results ---
function render() {
  // Update labels
  valAfforest.textContent = slAfforest.value + '%';
  valWetland.textContent = slWetland.value + '%';
  valArea.textContent = slArea.value + '%';
  valPeat.textContent = slPeat.value + '%';

  const r = calculate();

  // Cards
  const carbonClass = r.carbon[1] > 0 ? 'positive' : 'negative';
  const costM = r.cost[1] / 1e6;
  const costLowM = r.cost[0] / 1e6;
  const costHighM = r.cost[2] / 1e6;

  resultsDiv.innerHTML = `
    <div class="card">
      <h3>Carbon Sequestration</h3>
      <div class="value ${carbonClass}">${formatNum(r.carbon[1])}</div>
      <div class="unit">tCO₂/year</div>
      <div class="ci">CI: ${formatNum(r.carbon[0])} – ${formatNum(r.carbon[2])}</div>
    </div>
    <div class="card">
      <h3>Total Cost (${HORIZON_YEARS}yr)</h3>
      <div class="value neutral">€${costM.toFixed(1)}M</div>
      <div class="unit">implementation + opportunity</div>
      <div class="ci">CI: €${costLowM.toFixed(1)}M – €${costHighM.toFixed(1)}M</div>
    </div>
    <div class="card">
      <h3>Biodiversity Gain</h3>
      <div class="value positive">${(r.bioScore * 100).toFixed(2)}</div>
      <div class="unit">proxy score (×100)</div>
      <div class="ci">Rohemeeter-informed estimate</div>
    </div>
    <div class="card">
      <h3>Area Changed</h3>
      <div class="value neutral">${r.totalKm2Changed.toFixed(0)}</div>
      <div class="unit">km² of ${TOTAL_CELLS} km² total</div>
      <div class="ci">${(r.totalKm2Changed / TOTAL_CELLS * 100).toFixed(1)}% of county</div>
    </div>
    <div class="card">
      <h3>Cost Efficiency</h3>
      <div class="value neutral">€${(r.cost[1] / Math.max(r.carbon[1], 1)).toFixed(0)}</div>
      <div class="unit">per tCO₂/year</div>
      <div class="ci">Lower is better</div>
    </div>
    <div class="card">
      <h3>Carbon per km²</h3>
      <div class="value ${carbonClass}">${(r.carbon[1] / Math.max(r.totalKm2Changed, 1)).toFixed(1)}</div>
      <div class="unit">tCO₂/year per km² changed</div>
      <div class="ci">Spatial efficiency</div>
    </div>
  `;

  // Bars
  const maxHa = Math.max(r.haAfforest, r.haWetland, r.haGrassland, 1);
  const barData = [
    { label: 'Afforestation', ha: r.haAfforest, color: '#2d7d46' },
    { label: 'Wetland restore', ha: r.haWetland, color: '#1f78b4' },
    { label: 'Grassland', ha: r.haGrassland, color: '#b2df8a' },
    { label: 'No change', ha: r.haProtect * 100, color: '#cccccc' },
  ];

  const maxBar = Math.max(...barData.map(b => b.ha));
  barsDiv.innerHTML = barData.map(b => `
    <div class="bar">
      <div class="bar-label">${b.label}</div>
      <div class="bar-track">
        <div class="bar-fill" style="width:${(b.ha / maxBar * 100).toFixed(1)}%; background:${b.color}"></div>
      </div>
      <div class="bar-value">${(b.ha / 100).toFixed(0)} km²</div>
    </div>
  `).join('');
}

function formatNum(n) {
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'k';
  return n.toFixed(0);
}

// --- Event listeners ---
[slAfforest, slWetland, slArea, slPeat].forEach(sl => {
  sl.addEventListener('input', () => {
    // Switch to custom tab when user moves sliders
    tabs.forEach(t => t.classList.remove('active'));
    document.querySelector('[data-scenario="custom"]').classList.add('active');
    render();
  });
});

tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    const scenario = tab.dataset.scenario;
    tabs.forEach(t => t.classList.remove('active'));
    tab.classList.add('active');

    const preset = PRESETS[scenario];
    if (preset) {
      slAfforest.value = preset.afforest;
      slWetland.value = preset.wetland;
      slArea.value = preset.area;
      slPeat.value = preset.peat;
    }
    render();
  });
});

// Initial render
render();
