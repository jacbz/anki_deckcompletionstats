function refreshCount() {
  if (window.pycmd) {
    pycmd("deckcompletionstats_refresh");
  }
}
function selectDeck() {
  if (window.pycmd) {
    pycmd("deckcompletionstats_select_deck");
  }
}
function selectModel() {
  if (window.pycmd) {
    pycmd("deckcompletionstats_select_model");
  }
}
function selectWordField() {
  if (window.pycmd) {
    pycmd("deckcompletionstats_select_word_field");
  }
}

function updateCount(v) {
  const dc = document.getElementById("deckCount");
  if (dc) {
    dc.textContent = `(${v.toLocaleString()} cards)`;
  }
}
function updateDeckName(name) {
  const el = document.getElementById("currentDeck");
  if (el) {
    el.textContent = name;
  }
}
function updateModelName(name) {
  const el = document.getElementById("currentModel");
  if (el) {
    el.textContent = name;
  }
}

function setModelTemplates(templates, selected) {
  const container = document.getElementById("modelTemplates");
  if (!container) return;
  container.innerHTML = "";
  (templates || []).forEach((t) => {
    const wrapper = document.createElement("label");
    wrapper.style.display = "flex";
    wrapper.style.alignItems = "center";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.value = t.ord;
    cb.checked = !selected || selected.includes(t.ord);
    cb.addEventListener("change", saveTemplateSelection);
    const span = document.createElement("span");
    span.textContent = t.name || `Card ${t.ord + 1}`;
    wrapper.appendChild(cb);
    wrapper.appendChild(span);
    container.appendChild(wrapper);
  });
}
function getSelectedTemplateOrds() {
  return Array.from(
    document.querySelectorAll('#modelTemplates input[type="checkbox"]')
  )
    .filter((cb) => cb.checked)
    .map((cb) => parseInt(cb.value, 10));
}
function saveTemplateSelection() {
  if (window.pycmd) {
    pycmd(
      "deckcompletionstats_update_templates:" +
        JSON.stringify(getSelectedTemplateOrds())
    );
  }
}
function changeGranularity(g) {
  if (window.pycmd) {
    pycmd("deckcompletionstats_set_granularity:" + g);
  }
}
function toggleForecast(on) {
  if (window.pycmd) {
    pycmd("deckcompletionstats_set_forecast:" + (on ? "1" : "0"));
  }
}

let deckcompletionstatsChart;
let learningHistoryChart;
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
function paletteColor(i) {
  const p = [
    "#4facfe",
    "#38f9d7",
    "#ffb347",
    "#ff6b6b",
    "#a78bfa",
    "#f472b6",
    "#34d399",
    "#facc15",
    "#fb7185",
  ];
  return p[i % p.length];
}
function renderStackedBarChart(targetId, dataset) {
  const ctx = document.getElementById(targetId);
  if (!ctx || typeof Chart === "undefined") return null;
  const labels = dataset.labels || [];
  const series = dataset.series || [];
  const singleTemplate = series.length <= 1;
  const dataSets = series.map((s, i) => ({
    label: s.label,
    data: s.data,
    backgroundColor: paletteColor(i) + "cc",
  }));
  const cfg = {
    type: "bar",
    data: { labels, datasets: dataSets },
    options: {
      responsive: true,
      plugins: { legend: { display: !singleTemplate, labels: { color: "#e6edf3", font: { size: 10 } } } },
      scales: {
        x: {
          stacked: targetId === "learningHistoryChart",
          ticks: { color: "#9aa2ab" },
          grid: { color: "#30363d" },
        },
        y: {
          stacked: targetId === "learningHistoryChart",
          ticks: { color: "#9aa2ab" },
          grid: { color: "#30363d" },
        },
      },
    },
  };
  if (targetId === "learningHistoryChart") {
    learningHistoryChart = ensureChart(learningHistoryChart, ctx, cfg);
    return learningHistoryChart;
  }
  if (targetId === "timeSpentChart") {
    timeSpentChart = ensureChart(timeSpentChart, ctx, cfg);
    return timeSpentChart;
  }
  return ensureChart(null, ctx, cfg);
}
function renderProgressChart(progress) {
  const ctx = document.getElementById("statsChart");
  if (!ctx || typeof Chart === "undefined") return;
  const baseLabels = progress.labels || [];
  const datasets = [];
  const globalMax = progress.yMaxTotal || 0;
  const completionAnnotations = [];
  const templateCount = (progress.series || []).length;
  (progress.series || []).forEach((s, i) => {
    datasets.push({
      label: s.label,
      data: s.data.concat(
        Array(Math.max(0, baseLabels.length - s.data.length)).fill(null)
      ),
      borderColor: paletteColor(i),
      backgroundColor: paletteColor(i) + "33",
      tension: 0.25,
      pointRadius: 2,
      spanGaps: true,
      fill: false,
      borderWidth: 2,
    });
    if (s.forecast) {
      const fcData = s.forecast.map((v) => (v === null ? null : v));
      datasets.push({
        label: s.label + " (forecast)",
        data: fcData,
        borderColor: paletteColor(i),
        borderDash: [4, 3],
        pointRadius: 0,
        spanGaps: true,
        fill: false,
        tension: 0.15,
        borderWidth: 1.5,
      });
      if (
        typeof s.forecastCompletionIndex === "number" &&
        s.forecastCompletionIndex < baseLabels.length
      ) {
        const idx = s.forecastCompletionIndex;
        const val = fcData[idx];
        if (typeof val === "number") {
          completionAnnotations.push({
            type: "point",
            xValue: baseLabels[idx],
            yValue: val,
            backgroundColor: paletteColor(i),
            radius: 4,
            borderWidth: 0,
            label: {
              enabled: true,
              display: true,
              content: s.forecastCompletionDate || baseLabels[idx],
              position: "top",
              backgroundColor: "#111826",
              color: "#e6edf3",
              padding: 3,
              font: { size: 10 },
            },
          });
        }
      }
    }
  });
  const options = {
    animation: false,
    plugins: {
      legend: { display: templateCount > 1, labels: { color: "#e6edf3", font: { size: 10 } } },
      annotation: { annotations: completionAnnotations },
    },
    scales: {
      x: {
        ticks: { color: "#9aa2ab", maxRotation: 60, autoSkip: true },
        grid: { color: "#30363d" },
      },
      y: {
        ticks: { color: "#9aa2ab" },
        grid: { color: "#30363d" },
        suggestedMax: globalMax,
        max: globalMax,
      },
    },
  };
  const cfg = { type: "line", data: { labels: baseLabels, datasets }, options };
  deckcompletionstatsChart = ensureChart(deckcompletionstatsChart, ctx, cfg);
}
function renderTimeSpent(dataset) {
  const ctx = document.getElementById("timeSpentChart");
  if (!ctx || typeof Chart === "undefined") return;
  const labels = dataset.buckets || [];
  const series = dataset.series || [];
  const singleTemplate = series.length <= 1;
  const convSeries = series.map((s) => ({
    label: s.label,
    data: (s.data || []).map((v) =>
      typeof v === "number" ? +(v / 60).toFixed(2) : v
    ),
  }));
  const ds = convSeries.map((s, i) => ({
    label: s.label,
    data: s.data,
    backgroundColor: paletteColor(i) + "cc",
  }));
  const cfg = {
    type: "bar",
    data: { labels, datasets: ds },
    options: {
      plugins: {
        legend: { display: !singleTemplate, labels: { color: "#e6edf3", font: { size: 10 } } },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y} min`,
          },
        },
      },
      scales: {
        x: { ticks: { color: "#9aa2ab" }, grid: { color: "#30363d" } },
        y: {
          ticks: { color: "#9aa2ab", callback: (v) => v + " min" },
          grid: { color: "#30363d" },
        },
      },
    },
  };
  timeSpentChart = ensureChart(timeSpentChart, ctx, cfg);
  const wrap = document.getElementById("timeSpentTables");
  if (!wrap) return;
  wrap.innerHTML = "";
  const top = dataset.top || {};
  const nameMap = dataset.templateNames || {};
  const rowContainer = document.createElement("div");
  rowContainer.className = "flex-row";
  Object.keys(top).forEach((ord) => {
    const rows = top[ord];
    if (!rows || !rows.length) return;
    const div = document.createElement("div");
    div.className = "flex-col";
    const h = document.createElement("div");
    h.className = "template-head";
    h.textContent = (nameMap[ord] || "Template " + ord) + " (Top Time)";
    div.appendChild(h);
    const table = document.createElement("table");
    table.className = "data-table";
    table.innerHTML = "<thead><tr><th>Card</th><th>Time (s)</th></tr></thead>";
    const tb = document.createElement("tbody");
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${r.front}</td><td>${r.timeSec}</td>`;
      tb.appendChild(tr);
    });
    table.appendChild(tb);
    div.appendChild(table);
    rowContainer.appendChild(div);
  });
  wrap.appendChild(rowContainer);
}
function renderDifficult(dataset) {
  const wrap = document.getElementById("difficultTables");
  if (!wrap) return;
  wrap.innerHTML = "";
  const byT = dataset.byTemplate || {};
  const nameMap = dataset.templateNames || {};
  const rowContainer = document.createElement("div");
  rowContainer.className = "flex-row";
  Object.keys(byT).forEach((ord) => {
    const rows = byT[ord];
    if (!rows || !rows.length) return;
    const div = document.createElement("div");
    div.className = "flex-col";
    const h = document.createElement("div");
    h.className = "template-head";
    h.textContent = (nameMap[ord] || "Template " + ord) + " (Failures)";
    div.appendChild(h);
    const table = document.createElement("table");
    table.className = "data-table";
    table.innerHTML = "<thead><tr><th>Card</th><th>Failures</th></tr></thead>";
    const tb = document.createElement("tbody");
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${r.front}</td><td>${r.failures}</td>`;
      tb.appendChild(tr);
    });
    table.appendChild(tb);
    div.appendChild(table);
    rowContainer.appendChild(div);
  });
  wrap.appendChild(rowContainer);
}
function isoToLocale(iso) {
  try {
    return new Date(iso).toLocaleDateString();
  } catch (e) {
    return iso;
  }
}
function renderForecastSummaries(progress) {
  const box = document.getElementById("forecastSummaries");
  if (!box) return;
  const lines = [];
  (progress.series || []).forEach((s) => {
    const iso = s.forecastCompletionISO;
    if (!iso) return;
    const date = isoToLocale(iso);
    const remaining =
      (s.totalCards || 0) - (s.data ? s.data[s.data.length - 1] : 0);
    lines.push(
      `<div class="forecast-line"><span class="tmpl">${
        s.label
      }</span>: projected to finish <strong>${
        remaining <= 0 ? "(complete)" : date
      }</strong></div>`
    );
  });
  box.innerHTML = lines.join("");
  box.style.display = lines.length ? "block" : "none";
}
function computeMilestones(progress) {
  const results = [];
  (progress.series || []).forEach((s) => {
    const studiedDates = s.studiedDates || [];
    const total = s.totalCards || 0;
    if (!total) return;
    const ms = [];
    function addMilestone(n, iso, projected) {
      if (n > total) return;
      if (!ms.find((x) => x.milestone === n))
        ms.push({
          milestone: n,
          label: isoToLocale(iso),
          projected: !!projected,
        });
    }
    const thresholds = [1, 100, 500, 1000];
    for (let v = 2000; v <= total; v += 1000) thresholds.push(v);
    thresholds.forEach((n) => {
      if (n <= studiedDates.length) {
        addMilestone(n, studiedDates[n - 1], false);
      }
    });
    if (studiedDates.length < total) {
      if (studiedDates.length >= 2) {
        const first = new Date(studiedDates[0]);
        const last = new Date(studiedDates[studiedDates.length - 1]);
        const days = Math.max(1, (last - first) / (1000 * 3600 * 24));
        const rate = studiedDates.length / days;
        const remainingActual = total - studiedDates.length;
        thresholds
          .filter((n) => n > studiedDates.length && n <= total)
          .forEach((n) => {
            const need = n - studiedDates.length;
            const daysNeeded = need / (rate || 1);
            const projDate = new Date(
              last.getTime() + Math.ceil(daysNeeded) * 86400000
            )
              .toISOString()
              .slice(0, 10);
            addMilestone(n, projDate, true);
          });
        if (!thresholds.includes(total)) thresholds.push(total);
        if (studiedDates.length < total) {
          const needTotal = total - studiedDates.length;
          const daysNeededTotal = needTotal / (rate || 1);
          const projDateTotal = new Date(
            last.getTime() + Math.ceil(daysNeededTotal) * 86400000
          )
            .toISOString()
            .slice(0, 10);
          addMilestone(total, projDateTotal, true);
        } else {
          addMilestone(total, studiedDates[total - 1], false);
        }
      } else if (studiedDates.length === 1) {
        const last = new Date(studiedDates[0]);
        thresholds
          .filter((n) => n > 1 && n <= total)
          .forEach((n) => {
            const projDate = new Date(last.getTime() + (n - 1) * 86400000)
              .toISOString()
              .slice(0, 10);
            addMilestone(n, projDate, true);
          });
        addMilestone(
          total,
          new Date(last.getTime() + (total - 1) * 86400000)
            .toISOString()
            .slice(0, 10),
          true
        );
      }
    } else {
      addMilestone(total, studiedDates[total - 1], false);
    }
    ms.sort((a, b) => a.milestone - b.milestone);
    if (ms.length) results.push({ template: s.label, hits: ms });
  });
  return results;
}
function renderMilestones(progress) {
  const section = document.getElementById("milestonesSection");
  const content = document.getElementById("milestonesContent");
  if (!section || !content) return;
  const ms = computeMilestones(progress);
  if (!ms.length) {
    section.style.display = "none";
    content.innerHTML = "";
    return;
  }
  section.style.display = "block";
  content.innerHTML = ms
    .map((group) => {
      const rows = group.hits
        .map(
          (h) =>
            `<div class="ms-row ${
              h.projected ? "proj" : ""
            }"><span class="ms-count">#${h.milestone.toLocaleString()} ${h.projected ? " (projection)" : ""}</span><span class="ms-date">${
              h.label
            }</span></div>`
        )
        .join("");
      return `<div class="ms-card"><div class="ms-title">${
        group.template
      }</div>${rows || '<div class="ms-none">No milestones</div>'}</div>`;
    })
    .join("");
}
let statusCharts = {};
function renderStatusCharts(statusData){
  const wrap = document.getElementById('statusCharts');
  const section = document.getElementById('statusSection');
  if(!wrap || !section) return;
  const byT = (statusData && statusData.byTemplate) || {};
  const ords = Object.keys(byT);
  if(!ords.length){ section.style.display='none'; wrap.innerHTML=''; return; }
  section.style.display='block';
  wrap.innerHTML='';
  ords.forEach((ord, idx)=>{
    const item = byT[ord];
    const total = item.new + item.learning + item.review;
    const div = document.createElement('div');
    div.className='status-item';
    const cv = document.createElement('canvas');
    const lab = document.createElement('div');
    lab.className='status-label';
    lab.textContent = `${item.name} (${total})`;
    div.appendChild(cv); div.appendChild(lab); wrap.appendChild(div);
    const cfg = { type:'doughnut', data:{ labels:['New','Learning','Review'], datasets:[{ data:[item.new,item.learning,item.review], backgroundColor:['#4facfe','#ffb347','#34d399'], borderWidth:0 }] }, options:{ plugins:{ legend:{ display:false } }, cutout:'55%', responsive:true } };
    statusCharts[ord] = new Chart(cv, cfg);
  });
}
function deckcompletionstatsUpdateState(data) {
  try {
    const s = JSON.parse(data);
    if (typeof s.count === "number") updateCount(s.count);
    if (s.deckName) updateDeckName(s.deckName);
    if (s.modelName) updateModelName(s.modelName);
    if (Array.isArray(s.templates))
      setModelTemplates(s.templates, s.selectedTemplates);
    if (s.granularity) {
      document
        .querySelectorAll('#granularityRadios input[type="radio"]')
        .forEach((r) => {
          if (r.value === s.granularity) r.checked = true;
        });
    }
    const fcToggle = document.getElementById("forecastToggle");
    if (fcToggle && typeof s.forecastEnabled === "boolean")
      fcToggle.checked = s.forecastEnabled;
    if (typeof s.streak === "number") {
      const sc = document.getElementById("streakContainer");
      const sd = document.getElementById("streakDays");
      if (sc && sd) {
        sd.textContent = s.streak.toString();
        sc.style.display = s.streak > 0 ? "inline-flex" : "none";
      }
    }
    if (s.progress) {
      renderProgressChart(s.progress);
      renderForecastSummaries(s.progress);
      renderMilestones(s.progress);
    }
    if (s.learningHistory)
      learningHistoryChart = renderStackedBarChart(
        "learningHistoryChart",
        s.learningHistory
      );
    if (s.timeSpent) renderTimeSpent(s.timeSpent);
    if (s.difficult) renderDifficult(s.difficult);
    if (s.fieldNames) {
      const wfl = document.getElementById("wordFieldLine");
      if (wfl) {
        const wordName =
          s.wordFieldIndex >= 0 && s.fieldNames[s.wordFieldIndex]
            ? s.fieldNames[s.wordFieldIndex]
            : "(n/a)";
        document.getElementById("wordFieldName").textContent = wordName;
        wfl.style.display = "block";
      }
    }
    if (s.status) renderStatusCharts(s.status);
  } catch (e) {
    console.error(e);
  }
}
function togglePill(){ const pill=document.getElementById('floatingControls'); if(!pill) return; const content=pill.querySelector('.pill-content'); if(!content) { pill.classList.toggle('collapsed'); return; }
  const isCollapsed = pill.classList.contains('collapsed');
  if(isCollapsed){ // expand
    pill.classList.remove('collapsed');
    content.style.display='block';
    const targetHeight = content.scrollHeight+'px';
    content.style.maxHeight = '0px';
    requestAnimationFrame(()=>{ content.style.transition='max-height .55s cubic-bezier(.34,1.56,.64,1), opacity .4s ease'; content.style.maxHeight = targetHeight; content.style.opacity='1'; });
    setTimeout(()=>{ content.style.maxHeight=''; content.style.transition=''; },600);
  } else { // collapse
    const startHeight = content.scrollHeight+'px';
    content.style.maxHeight = startHeight; content.style.opacity='1';
    requestAnimationFrame(()=>{ content.style.transition='max-height .5s ease, opacity .35s ease'; content.style.maxHeight='0px'; content.style.opacity='0'; });
    setTimeout(()=>{ pill.classList.add('collapsed'); content.style.transition=''; content.style.display=''; },520);
  }
}
function animateStreak(){ const sc=document.getElementById('streakContainer'); if(sc){ sc.classList.add('animate-gradient'); } }
window.addEventListener('DOMContentLoaded',()=>{ animateStreak(); });
