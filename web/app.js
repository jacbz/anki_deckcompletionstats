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

function selectModel() {
  if (typeof pycmd !== 'undefined') {
    pycmd('statistics5000_select_model');
  }
}

// Chart.js progress chart
let statistics5000Chart;
function renderProgressChart(progress) {
  const ctx = document.getElementById('statsChart');
  if (!ctx || typeof Chart === 'undefined') return;
  const palette = ['#4facfe','#38f9d7','#ffb347','#ff6b6b','#a78bfa','#f472b6','#34d399'];
  const datasets = (progress.series || []).map((s,i) => ({
    label: s.label,
    data: s.data,
    borderColor: palette[i % palette.length],
    backgroundColor: palette[i % palette.length] + '33',
    tension: 0.25,
    pointRadius: 2,
    fill: false
  }));
  if (statistics5000Chart) {
    statistics5000Chart.data.labels = progress.labels;
    statistics5000Chart.data.datasets = datasets;
    statistics5000Chart.update();
  } else {
    statistics5000Chart = new Chart(ctx, {
      type: 'line',
      data: { labels: progress.labels, datasets },
      options: {
        animation: false,
        plugins: { legend: { labels: { color: '#e6edf3', font: { size: 10 } } } },
        scales: {
          x: { ticks: { color: '#9aa2ab', maxRotation: 60, autoSkip: true }, grid: { color: '#30363d' } },
          y: { ticks: { color: '#9aa2ab' }, grid: { color: '#30363d' } }
        }
      }
    });
  }
}

function changeGranularity(g) {
  if (typeof pycmd !== 'undefined') {
    pycmd('statistics5000_set_granularity:' + g);
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
      const sel = document.getElementById('granularitySelect');
      if (sel && sel.value !== s.granularity) sel.value = s.granularity;
    }
    if (s.progress) {
      renderProgressChart(s.progress);
    }
  } catch (e) { console.error(e); }
}

window.addEventListener('DOMContentLoaded', () => {
  // initial chart will render when state arrives
});
