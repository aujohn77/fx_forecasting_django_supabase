// static/js/compare.js

const metrics = JSON.parse(document.getElementById('metrics-data').textContent);
const SERIES  = JSON.parse(document.getElementById('plot-data').textContent);

// ----- Render metrics table (unchanged) -----
let mt = '<table><thead><tr><th>Model</th><th>TF</th><th>Pair</th><th>MAE</th><th>RMSE</th><th>MAPE %</th><th>n</th></tr></thead><tbody>';
metrics.forEach(r=>{
  // support either {base_code,quote_code} or {base,quote} depending on view shape
  const base = r.base_code || r.base;
  const quote = r.quote_code || r.quote;
  mt += `<tr><td>${r.run_model}</td><td>${r.run_tf}</td><td>${base}->${quote}</td>
         <td>${(r.mae??0).toFixed(6)}</td><td>${(r.rmse??0).toFixed(6)}</td>
         <td>${r.mape!=null?r.mape.toFixed(3):'-'}</td><td>${r.n}</td></tr>`;
});
mt += '</tbody></table>';
document.getElementById('metrics').innerHTML = mt;

// ----- Controls -----
const tfPick    = document.getElementById('tfPick');
const modelPick = document.getElementById('modelPick');
const ccyPick   = document.getElementById('ccyPick');
const startPick = document.getElementById('startPick');

// Build unique value sets from data (tf, model, quote)
const TF_SET = new Set();
const MODEL_SET = new Set();
const CCY_SET = new Set();
(SERIES || []).forEach(s => {
  if (s.tf) TF_SET.add(s.tf);
  if (s.model) MODEL_SET.add(s.model);
  if (s.quote) CCY_SET.add(s.quote);
});

// Populate model + currency (tf has fixed options in HTML)
function addOpts(sel, items){
  items.sort().forEach(v=>{
    const o = document.createElement('option');
    o.value = v; o.text = v;
    sel.add(o);
  });
}
addOpts(modelPick, Array.from(MODEL_SET));
addOpts(ccyPick,   Array.from(CCY_SET));

// ----- Chart -----
let chart;
function draw() {
  const tf    = tfPick.value;
  const model = modelPick.value;
  const ccy   = ccyPick.value;
  const start = startPick.value ? new Date(startPick.value) : null;

  // pick the first series that matches filters
  const candidates = SERIES.filter(s =>
    (!tf    || s.tf    === tf) &&
    (!model || s.model === model) &&
    (!ccy   || s.quote === ccy)
  );

  if (candidates.length === 0) {
    if (chart) chart.destroy();
    const ctx = document.getElementById('btChart').getContext('2d');
    chart = new Chart(ctx, { type:'line', data:{labels:[],datasets:[]}, options:{plugins:{legend:{position:'bottom'}}} });
    return;
  }

  // If multiple match, default to the first; could enhance later with seriesPick
  const s = candidates[0];

  // Filter points by start date, if any
  const pts = !start ? s.points : s.points.filter(p => new Date(p.date) >= start);

  const labels   = pts.map(p=>p.date);
  const actual   = pts.map(p=>p.actual);
  const forecast = pts.map(p=>p.forecast);

  if (chart) chart.destroy();
  chart = new Chart(document.getElementById('btChart'), {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Actual',   data: actual,   borderWidth: 2, tension: 0.15 },
        { label: 'Forecast', data: forecast, borderWidth: 1, borderDash: [4,3], tension: 0.15 }
      ]
    },
    options: {
      responsive: true,
      plugins: { legend: { position: 'bottom' } },
      scales: { x: { ticks: { maxRotation: 0 } } }
    }
  });
}

// Initial draw + listeners
draw();
[tfPick, modelPick, ccyPick, startPick].forEach(el => el.addEventListener('change', draw));
