function refreshCount() {
  if (typeof pycmd !== 'undefined') {
    pycmd('statistics5000_refresh');
  }
}

function selectDeck() {
  if (typeof pycmd !== 'undefined') {
    pycmd('statistics5000_select_deck');
  }
}

function updateCount(v) {
  const el = document.getElementById('cardCount');
  if (el) {
    el.textContent = v.toLocaleString();
  }
}

function updateDeckName(name) {
  const el = document.getElementById('currentDeck');
  if (el) {
    el.textContent = name;
  }
}

function updateModelName(name) {
  const el = document.getElementById('currentModel');
  if (el) {
    el.textContent = name;
  }
}

function setModelTemplates(templates, selected) {
  const container = document.getElementById('modelTemplates');
  if (!container) return;
  container.innerHTML = '';
  (templates || []).forEach(t => {
    const id = `tmpl_${t.ord}`;
    const wrapper = document.createElement('label');
    wrapper.style.fontSize = '.7rem';
    wrapper.style.display = 'flex';
    wrapper.style.alignItems = 'center';
    wrapper.style.gap = '.25rem';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.id = id;
    cb.value = t.ord;
    cb.checked = !selected || selected.includes(t.ord);
    cb.addEventListener('change', () => saveTemplateSelection());
    const span = document.createElement('span');
    span.textContent = t.name || `Card ${t.ord+1}`;
    wrapper.appendChild(cb);
    wrapper.appendChild(span);
    container.appendChild(wrapper);
  });
}

function getSelectedTemplateOrds() {
  return Array.from(document.querySelectorAll('#modelTemplates input[type="checkbox"]'))
    .filter(cb => cb.checked)
    .map(cb => parseInt(cb.value, 10));
}

function saveTemplateSelection() {
  const ords = getSelectedTemplateOrds();
  if (typeof pycmd !== 'undefined') {
    pycmd('statistics5000_update_templates:' + JSON.stringify(ords));
  }
}

function changeGranularity(g) { if (typeof pycmd !== 'undefined') pycmd('statistics5000_set_granularity:' + g); }
function toggleForecast(on) { if (typeof pycmd !== 'undefined') pycmd('statistics5000_set_forecast:' + (on ? '1':'0')); }

let statistics5000Chart;
function renderProgressChart(progress) {
  const ctx = document.getElementById('statsChart');
  if (!ctx || typeof Chart === 'undefined') return;
  const palette = ['#4facfe','#38f9d7','#ffb347','#ff6b6b','#a78bfa','#f472b6','#34d399'];
  const baseLabels = progress.labels || [];
  const datasets = [];
  let maxY = 0;
  const completionAnnotations = [];
  (progress.series || []).forEach((s,i) => {
    maxY = Math.max(maxY, ...(s.data||[]), ...((s.forecast||[]).filter(v=>typeof v==='number')));
    datasets.push({
      label: s.label,
      data: s.data.concat(Array(Math.max(0, baseLabels.length - s.data.length)).fill(null)),
      borderColor: palette[i % palette.length],
      backgroundColor: palette[i % palette.length] + '33',
      tension: 0.25,
      pointRadius: 2,
      spanGaps: true,
      fill: false,
      borderWidth: 2,
    });
    if (s.forecast) {
      const fcData = s.forecast.map(v => v === null ? null : v);
      datasets.push({
        label: s.label + ' (forecast)',
        data: fcData,
        borderColor: palette[i % palette.length],
        borderDash: [4,3],
        pointRadius: 0,
        spanGaps: true,
        fill: false,
        tension: 0.15,
        borderWidth: 1.5,
      });
      if (typeof s.forecastCompletionIndex === 'number' && s.forecastCompletionIndex < baseLabels.length) {
        const idx = s.forecastCompletionIndex;
        const val = fcData[idx];
        if (typeof val === 'number') {
          completionAnnotations.push({
            type: 'point',
            xValue: baseLabels[idx],
            yValue: val,
            backgroundColor: palette[i % palette.length],
            radius: 4,
            borderWidth: 0,
            label: {
              enabled: true,
              display: true,
              content: s.forecastCompletionDate || baseLabels[idx],
              position: 'top',
              backgroundColor: '#111826',
              color: '#e6edf3',
              padding: 3,
              font: { size: 10 },
            }
          });
        }
      }
    }
  });
  const ySuggestedMax = maxY + Math.ceil(maxY*0.05);
  const options = {
    animation: false,
    plugins: { legend: { labels: { color: '#e6edf3', font: { size: 10 } } }, annotation: { annotations: completionAnnotations } },
    scales: {
      x: { ticks: { color: '#9aa2ab', maxRotation: 60, autoSkip: true }, grid: { color: '#30363d' } },
      y: { ticks: { color: '#9aa2ab' }, grid: { color: '#30363d' }, suggestedMax: ySuggestedMax }
    }
  };
  if (statistics5000Chart) {
    statistics5000Chart.data.labels = baseLabels;
    statistics5000Chart.data.datasets = datasets;
    statistics5000Chart.options = options;
    statistics5000Chart.update();
  } else {
    statistics5000Chart = new Chart(ctx, { type: 'line', data: { labels: baseLabels, datasets }, options });
  }
}

// Extend state updater
function statistics5000UpdateState(data) {
  try {
    const s = JSON.parse(data);
    if (typeof s.count === 'number') updateCount(s.count);
    if (s.deckName) updateDeckName(s.deckName);
    if (s.modelName) updateModelName(s.modelName);
    if (Array.isArray(s.templates)) setModelTemplates(s.templates, s.selectedTemplates);
    if (s.granularity) {
      const radios = document.querySelectorAll('#granularityRadios input[type="radio"]');
      radios.forEach(r => { if (r.value === s.granularity) r.checked = true; });
    }
    const fcToggle = document.getElementById('forecastToggle');
    if (fcToggle && typeof s.forecastEnabled === 'boolean') fcToggle.checked = s.forecastEnabled;
    if (s.progress) renderProgressChart(s.progress);
  } catch (e) { console.error(e); }
}

window.addEventListener('DOMContentLoaded', () => {
  // initial chart will render when state arrives
});
