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

// Exposed update from Python
function statistics5000UpdateState(data) {
  try {
    const s = JSON.parse(data);
    if (typeof s.count === 'number') updateCount(s.count);
    if (s.deckName) updateDeckName(s.deckName);
    if (s.modelName) updateModelName(s.modelName);
    if (Array.isArray(s.templates)) setModelTemplates(s.templates, s.selectedTemplates);
  } catch (e) { console.error(e); }
}

// Chart.js dummy line chart
let statistics5000Chart;
function initChart() {
  const ctx = document.getElementById('statsChart');
  if (!ctx || typeof Chart === 'undefined') { return; }
  if (statistics5000Chart) { return; }
  const labels = Array.from({length: 14}, (_, i) => `Day ${i+1}`);
  const data = labels.map(() => Math.floor(Math.random()*100));
  statistics5000Chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Dummy Cards Reviewed',
        data,
        tension: 0.35,
        borderColor: '#4facfe',
        backgroundColor: 'rgba(79,172,254,0.15)',
        pointRadius: 3,
        fill: true,
      }]
    },
    options: {
      plugins: { legend: { labels: { color: '#e6edf3' } } },
      scales: {
        x: { ticks: { color: '#9aa2ab' }, grid: { color: '#30363d' } },
        y: { ticks: { color: '#9aa2ab' }, grid: { color: '#30363d' } }
      }
    }
  });
}

window.addEventListener('DOMContentLoaded', initChart);
