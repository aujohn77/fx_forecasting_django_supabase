document.addEventListener('DOMContentLoaded', () => {
  const latestActual = JSON.parse(document.getElementById('latest-actual').textContent);
  const byKey = JSON.parse(document.getElementById('latest-forecast').textContent);
  const currencyNames = JSON.parse(document.getElementById('currency-names').textContent || '{}'); // NEW

  const MODEL_SET = new Set();
  const TF_SET = new Set();
  for (const k of Object.keys(byKey)) {
    const i = k.lastIndexOf("-");
    const model = i > -1 ? k.slice(0, i) : k;
    const tf    = i > -1 ? k.slice(i + 1) : "daily";
    MODEL_SET.add(model);
    TF_SET.add(tf);
  }

  const modelSelect = document.getElementById('modelPick');
  const tfSelect = document.getElementById('timePick');

  function fillSelect(sel, values) {
    sel.innerHTML = "";
    (Array.isArray(values) ? values : Array.from(values)).forEach(v => {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = v;
      sel.add(opt);
    });
  }

  const MEMORY_KEY = 'fx_overview_choice_v1';
  const saveChoice = () =>
    localStorage.setItem(MEMORY_KEY, JSON.stringify({ model: modelSelect.value, tf: tfSelect.value }));
  const loadChoice = () => { try { return JSON.parse(localStorage.getItem(MEMORY_KEY) || '{}'); } catch { return {}; } };

  fillSelect(modelSelect, [...MODEL_SET].sort());
  fillSelect(tfSelect,   [...TF_SET].sort());

  function pickFirstAvailable() {
    for (const k of Object.keys(byKey)) {
      const i = k.lastIndexOf("-");
      return { model: k.slice(0, i), tf: k.slice(i + 1) };
    }
    return null;
  }

  const remembered = loadChoice();
  let initial = remembered;
  if (!byKey[`${remembered.model}-${remembered.tf}`]) initial = pickFirstAvailable();
  if (initial) { modelSelect.value = initial.model; tfSelect.value = initial.tf; }

  const keyFor = (model, tf) => `${model}-${tf}`;

  function renderTable() {
    const model = modelSelect.value;
    const tf = tfSelect.value;
    const k = keyFor(model, tf);
    const forecast = byKey[k] || {};

    const container = document.getElementById('overview-table');
    const quotes = Object.keys(forecast).sort();

    if (quotes.length === 0) {
      saveChoice();
      container.innerHTML = `<div class="muted">No forecasts for ${model} (${tf}).</div>`;
      return;
    }

    // Collect dates
    const actualDates = [...new Set(quotes.map(q => latestActual[q]?.date).filter(Boolean))];
    const forecastDates = [...new Set(quotes.map(q => forecast[q]?.date).filter(Boolean))];

    const actualLabel   = actualDates.length === 1 ? `Latest (${actualDates[0]})` : "Latest (varies)";
    const forecastLabel = forecastDates.length === 1 ? `Forecast (${forecastDates[0]})` : "Forecast (varies)";

    let html = `<table>
      <thead><tr>
        <th>Currency</th>
        <th title="Date of last observed market rate">${actualLabel}</th>
        <th title="Target date of forecast">${forecastLabel}</th>
        <th>Δ%</th>
      </tr></thead>
      <tbody>`;

    quotes.forEach(q => {
      const cur = latestActual[q]?.rate ?? null;
      const pr  = forecast[q]?.rate ?? null;
      const curDate = latestActual[q]?.date;
      const prDate  = forecast[q]?.date;

      const hasNums = Number.isFinite(cur) && Number.isFinite(pr);
      const pct = hasNums ? ((pr - cur) / cur * 100) : null;

      const zone = currencyNames[q] ? ` (${currencyNames[q]})` : ""; // NEW

      html += `<tr>
        <td>${q}${zone}</td>  <!-- NEW: code + country/zone -->
        <td title="${curDate || ''}">${Number.isFinite(cur) ? cur.toFixed(4) : '-'}</td>
        <td title="${prDate  || ''}">${Number.isFinite(pr)  ? pr .toFixed(4) : '-'}</td>
        <td class="${pct>0?'up':pct<0?'down':''}">${pct != null ? pct.toFixed(2) + '%' : '-'}</td>
      </tr>`;
    });

    html += `</tbody></table>`;
    container.innerHTML = html;
    saveChoice();
  }

  renderTable();
  modelSelect.addEventListener('change', renderTable);
  tfSelect.addEventListener('change', renderTable);
});
