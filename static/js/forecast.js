// Read JSON passed by the template
const payload = JSON.parse(document.getElementById('chart-data').textContent); // { EUR:{actual:[..], forecast:{model:[..]}}, ... }
const freqCode = JSON.parse(document.getElementById('freq-code').textContent);

const ctx = document.getElementById('fxForecast');
const labels = [];         // union of all dates (actuals + forecast heads)
const datasets = [];

// Build actual traces per quote
for (const [q, obj] of Object.entries(payload || {})) {
  const actual = obj.actual || [];
  actual.forEach(p => { if (!labels.includes(p.date)) labels.push(p.date); });

  datasets.push({
    label: `${q} (actual)`,
    data: labels.map(d => {
      const hit = actual.find(x => x.date === d);
      return hit ? hit.rate : null;
    }),
    borderWidth: 2,
    tension: 0.15
  });

  // Add each model's forward path, prepending last actual for visual continuity
  const forecasts = obj.forecast || {};
  for (const [model, seqRaw] of Object.entries(forecasts)) {
    const lastA = actual.length ? actual[actual.length - 1] : null;
    const seq = lastA ? [lastA, ...seqRaw] : seqRaw;

    const modelLabels = seq.map(p => p.date);
    datasets.push({
      label: `${q} – ${model}`,
      data: modelLabels.map(d => {
        const hit = seq.find(x => x.date === d);
        return hit ? hit.rate : null;
      }),
      borderWidth: 1,
      borderDash: [4, 3],
      spanGaps: true
    });

    modelLabels.forEach(d => { if (!labels.includes(d)) labels.push(d); });
  }
}

// Keep dates ordered
labels.sort();

new Chart(ctx, {
  type: 'line',
  data: { labels, datasets },
  options: {
    responsive: true,
    plugins: { legend: { position: 'bottom' } },
    scales: { x: { ticks: { maxRotation: 0 } } }
  }
});
