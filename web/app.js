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

function selectModel() {
  if (window.pycmd) {
    pycmd('statistics5000_select_model');
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
let learningHistoryChart;
let cumulativeFrequencyChart;
let timeSpentChart;

function ensureChart(existing, ctx, config) {
  if (existing) {
    existing.config.data = config.data;
    existing.config.options = config.options || existing.config.options;
    existing.update();
    return existing;
  }
  return new Chart(ctx, config);
}

function paletteColor(i){
  const palette = ['#4facfe','#38f9d7','#ffb347','#ff6b6b','#a78bfa','#f472b6','#34d399','#facc15','#fb7185'];
  return palette[i % palette.length];
}

function renderStackedBarChart(targetId, dataset) {
  const ctx = document.getElementById(targetId);
  if (!ctx || typeof Chart === 'undefined') return null;
  const labels = dataset.labels || [];
  const series = dataset.series || [];
  const dataSets = series.map((s,i)=>({ label: s.label, data: s.data, backgroundColor: paletteColor(i)+ 'cc' }));
  const cfg = { type: 'bar', data: { labels, datasets: dataSets }, options: { responsive: true, plugins: { legend: { labels: { color: '#e6edf3', font: { size: 10 } } } }, scales: { x: { stacked: targetId==='learningHistoryChart', ticks:{ color:'#9aa2ab' }, grid:{ color:'#30363d' } }, y: { stacked: targetId==='learningHistoryChart', ticks:{ color:'#9aa2ab' }, grid:{ color:'#30363d' } } } } };
  if (targetId === 'learningHistoryChart') {
    learningHistoryChart = ensureChart(learningHistoryChart, ctx, cfg);
    return learningHistoryChart;
  } else if (targetId === 'timeSpentChart') {
    timeSpentChart = ensureChart(timeSpentChart, ctx, cfg);
    return timeSpentChart;
  }
  return ensureChart(null, ctx, cfg);
}

function renderLineChart(targetId, dataset, percent=false) {
  const ctx = document.getElementById(targetId);
  if (!ctx || typeof Chart === 'undefined') return null;
  const labels = dataset.labels || [];
  const series = dataset.series || [];
  const ds = series.map((s,i)=>({ label: s.label, data: s.data, borderColor: paletteColor(i), backgroundColor: paletteColor(i)+'33', tension:.25, fill:false, pointRadius:2, spanGaps:true }));
  const options = { responsive:true, plugins:{ legend:{ labels:{ color:'#e6edf3', font:{ size:10 } } } }, scales:{ x:{ ticks:{ color:'#9aa2ab' }, grid:{ color:'#30363d' } }, y:{ beginAtZero: percent, ticks:{ color:'#9aa2ab' }, grid:{ color:'#30363d' }, suggestedMax: percent?100:undefined, max: percent?100:undefined } } };
  const cfg = { type:'line', data:{ labels, datasets:ds }, options };
  if (targetId==='statsChart') { statistics5000Chart = ensureChart(statistics5000Chart, ctx, cfg); return statistics5000Chart; }
  if (targetId==='cumulativeFrequencyChart') { cumulativeFrequencyChart = ensureChart(cumulativeFrequencyChart, ctx, cfg); return cumulativeFrequencyChart; }
  return ensureChart(null, ctx, cfg);
}

function renderProgressChart(progress) {
  const ctx = document.getElementById('statsChart');
  if (!ctx || typeof Chart === 'undefined') return;
  const baseLabels = progress.labels || [];
  const datasets = [];
  const globalMax = progress.yMaxTotal || 0;
  const completionAnnotations = [];
  (progress.series || []).forEach((s,i) => {
    datasets.push({
      label: s.label,
      data: s.data.concat(Array(Math.max(0, baseLabels.length - s.data.length)).fill(null)),
      borderColor: paletteColor(i),
      backgroundColor: paletteColor(i)+'33',
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
        borderColor: paletteColor(i),
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
            backgroundColor: paletteColor(i),
            radius: 4,
            borderWidth: 0,
            label: { enabled: true, display: true, content: s.forecastCompletionDate || baseLabels[idx], position: 'top', backgroundColor: '#111826', color: '#e6edf3', padding: 3, font: { size: 10 } }
          });
        }
      }
    }
  });
  const options = { animation:false, plugins:{ legend:{ labels:{ color:'#e6edf3', font:{ size:10 } } }, annotation:{ annotations: completionAnnotations } }, scales:{ x:{ ticks:{ color:'#9aa2ab', maxRotation:60, autoSkip:true }, grid:{ color:'#30363d' } }, y:{ ticks:{ color:'#9aa2ab' }, grid:{ color:'#30363d' }, suggestedMax: globalMax, max: globalMax } } };
  const cfg = { type:'line', data:{ labels: baseLabels, datasets }, options };
  statistics5000Chart = ensureChart(statistics5000Chart, ctx, cfg);
}

function renderTimeSpent(dataset){
  const ctx = document.getElementById('timeSpentChart');
  if (!ctx || typeof Chart === 'undefined') return;
  const labels = dataset.buckets || [];
  const series = dataset.series || [];
  const nameMap = (dataset.templateNames)||{};
  // Convert seconds to minutes (rounded to 2 decimals)
  const convSeries = series.map(s=>({ label: s.label, data: (s.data||[]).map(v=> (typeof v==='number'? +(v/60).toFixed(2): v)) }));
  const ds = convSeries.map((s,i)=>({ label: s.label, data: s.data, backgroundColor: paletteColor(i)+'cc' }));
  const cfg = { type:'bar', data:{ labels, datasets:ds }, options:{ plugins:{ legend:{ labels:{ color:'#e6edf3', font:{ size:10 } } }, tooltip:{ callbacks:{ label:(ctx)=> `${ctx.dataset.label}: ${ctx.parsed.y} min` } } }, scales:{ x:{ ticks:{ color:'#9aa2ab' }, grid:{ color:'#30363d' } }, y:{ ticks:{ color:'#9aa2ab', callback:(v)=> v+" min" }, grid:{ color:'#30363d' } } } } };
  timeSpentChart = ensureChart(timeSpentChart, ctx, cfg);
  const wrap = document.getElementById('timeSpentTables');
  if (!wrap) return;
  wrap.innerHTML = '';
  const top = dataset.top || {};
  const rowContainer = document.createElement('div');
  rowContainer.className='flex-row';
  Object.keys(top).forEach(ord => {
    const rows = top[ord]; if (!rows || !rows.length) return;
    const div = document.createElement('div'); div.className='flex-col';
    const h = document.createElement('div'); h.className='template-head'; h.textContent = (nameMap[ord]||('Template '+ord)) + ' (Top Time)'; div.appendChild(h);
    const table = document.createElement('table'); table.className='data-table';
    table.innerHTML = '<thead><tr><th>Card</th><th>Time (s)</th></tr></thead>';
    const tb = document.createElement('tbody');
    rows.forEach(r=>{ const tr=document.createElement('tr'); tr.innerHTML = `<td>${r.front}</td><td>${r.timeSec}</td>`; tb.appendChild(tr); });
    table.appendChild(tb); div.appendChild(table); rowContainer.appendChild(div);
  });
  wrap.appendChild(rowContainer);
}

function renderDifficult(dataset){
  const wrap = document.getElementById('difficultTables');
  if (!wrap) return;
  wrap.innerHTML='';
  const byT = dataset.byTemplate || {};
  const nameMap = dataset.templateNames || {};
  const rowContainer = document.createElement('div'); rowContainer.className='flex-row';
  Object.keys(byT).forEach(ord => {
    const rows = byT[ord]; if (!rows || !rows.length) return;
    const div = document.createElement('div'); div.className='flex-col';
    const h = document.createElement('div'); h.className='template-head'; h.textContent=(nameMap[ord]||('Template '+ord)) + ' (Failures)'; div.appendChild(h);
    const table = document.createElement('table'); table.className='data-table'; table.innerHTML='<thead><tr><th>Card</th><th>Failures</th></tr></thead>';
    const tb = document.createElement('tbody'); rows.forEach(r=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${r.front}</td><td>${r.failures}</td>`; tb.appendChild(tr); });
    table.appendChild(tb); div.appendChild(table); rowContainer.appendChild(div);
  });
  wrap.appendChild(rowContainer);
}

// Modify existing statistics5000UpdateState to hydrate new analytics
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
    if (typeof s.streak === 'number') {
      const sc = document.getElementById('streakContainer');
      const sd = document.getElementById('streakDays');
      if (sc && sd) {
        sd.textContent = s.streak.toString();
        sc.style.display = s.streak > 0 ? 'inline-flex' : 'none';
      }
    }
    const cfSection = document.getElementById('cumulativeFrequencySection');
    if (cfSection) {
      const hasData = s.cumulativeFrequency && s.cumulativeFrequency.labels && s.cumulativeFrequency.labels.length>0;
      cfSection.style.display = hasData ? '' : 'none';
    }
    if (s.progress) renderProgressChart(s.progress);
    if (s.learningHistory) learningHistoryChart = renderStackedBarChart('learningHistoryChart', s.learningHistory);
    if (s.cumulativeFrequency) cumulativeFrequencyChart = renderLineChart('cumulativeFrequencyChart', s.cumulativeFrequency, true);
    if (s.timeSpent) renderTimeSpent(s.timeSpent);
    if (s.difficult) renderDifficult(s.difficult);
    if (s.fieldNames) {
      const fi = document.getElementById('fieldInfo');
      if (fi) {
        const wordName = (s.wordFieldIndex>=0 && s.fieldNames[s.wordFieldIndex]) ? s.fieldNames[s.wordFieldIndex] : '(n/a)';
        const rawName = (s.rawFreqFieldIndex>=0 && s.fieldNames[s.rawFreqFieldIndex]) ? s.fieldNames[s.rawFreqFieldIndex] : '(disabled)';
        const corpusM = typeof s.corpusSizeMillions==='number'? s.corpusSizeMillions.toFixed(3).replace(/\.000$/,'') : '';
        document.getElementById('wordFieldName').textContent = wordName;
        document.getElementById('rawFreqFieldName').textContent = rawName;
        document.getElementById('corpusSizeMillions').textContent = corpusM;
        fi.style.display = 'block';
      }
    }
  } catch (e) { console.error(e); }
}

window.addEventListener('DOMContentLoaded', () => {
  // initial chart will render when state arrives
});
