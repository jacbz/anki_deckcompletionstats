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
let timeStudiedChart;
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
      plugins: {
        legend: {
          display: !singleTemplate,
          labels: { color: "#e6edf3", font: { size: 10 } },
        },
      },
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
          title:
            targetId === "learningHistoryChart"
              ? {
                  display: true,
                  text: "New Cards",
                  color: "#e6edf3",
                  font: { size: 11 },
                }
              : undefined,
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
      legend: {
        display: templateCount > 1,
        labels: { color: "#e6edf3", font: { size: 10 } },
      },
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
        title: {
          display: true,
          text: "Cards (Cumulative)",
          color: "#e6edf3",
          font: { size: 11 },
        },
      },
    },
  };
  const cfg = { type: "line", data: { labels: baseLabels, datasets }, options };
  deckcompletionstatsChart = ensureChart(deckcompletionstatsChart, ctx, cfg);
}
let timeHistCharts = {};
function renderTimeSpent(dataset) {
  const wrap = document.getElementById("timeSpentCharts");
  const tablesWrap = document.getElementById("timeSpentTables");
  if (!wrap || !tablesWrap) return;
  wrap.innerHTML = "";
  tablesWrap.innerHTML = "";
  const labels = dataset.labels || [];
  const hists = dataset.histograms || {};
  const ords = Object.keys(hists);
  if (!ords.length) {
    return;
  }
  // Compute global max count across all bins so y-axes align
  let globalMax = 0;
  ords.forEach((ord) => {
    const counts = (hists[ord] && hists[ord].counts) || [];
    counts.forEach((v) => {
      if (typeof v === "number" && v > globalMax) globalMax = v;
    });
  });
  if (globalMax < 1) globalMax = 1; // avoid 0 max
  ords.forEach((ord, idx) => {
    const item = hists[ord];
    const div = document.createElement("div");
    div.className = "time-item";
    const cv = document.createElement("canvas");
    const lab = document.createElement("div");
    lab.className = "time-label";
    lab.textContent = item.name;
    div.appendChild(cv);
    div.appendChild(lab);
    wrap.appendChild(div);
    const cfg = {
      type: "bar",
      data: {
        labels,
        datasets: [
          { data: item.counts, label: item.name, backgroundColor: "#4facfe66" },
        ],
      },
      options: {
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: (c) => `${c.parsed.y} cards` } },
        },
        scales: {
          x: {
            ticks: { color: "#9aa2ab", font: { size: 9 } },
            grid: { color: "#30363d" },
          },
          y: {
            ticks: { color: "#9aa2ab", font: { size: 9 } },
            grid: { color: "#30363d" },
            suggestedMax: globalMax,
            max: globalMax,
            title: {
              display: true,
              text: "Cards",
              color: "#e6edf3",
              font: { size: 11 },
            },
          },
        },
      },
    };
    timeHistCharts[ord] = new Chart(cv, cfg);
  });
  // tables (top time cards per template)
  const top = dataset.top || {};
  const nameMap = dataset.templateNames || {};
  const rowContainer = document.createElement("div");
  rowContainer.className = "flex-row";
  Object.keys(top).forEach((ord) => {
    const rows = top[ord];
    if (!rows || !rows.length) return;
    const col = document.createElement("div");
    col.className = "flex-col";
    const h = document.createElement("div");
    h.className = "template-head";
    h.textContent = (nameMap[ord] || "Card " + ord) + " (Top Time)";
    col.appendChild(h);
    const table = document.createElement("table");
    table.className = "data-table";
    table.innerHTML =
      "<thead><tr><th>Card</th><th>Total Time</th></tr></thead>";
    const tb = document.createElement("tbody");
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${r.front}</td><td>${r.timeSec}</td>`;
      tb.appendChild(tr);
    });
    table.appendChild(tb);
    col.appendChild(table);
    rowContainer.appendChild(col);
  });
  tablesWrap.appendChild(rowContainer);
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
  const box =
    document.getElementById("forecastSummaries") ||
    document.getElementById("summaries");
  if (!box) return;
  const lines = [];
  (progress.series || []).forEach((s) => {
    const iso = s.forecastCompletionISO;
    if (!iso) return;
    const date = isoToLocale(iso);
    const remaining =
      (s.totalCards || 0) - (s.data ? s.data[s.data.length - 1] : 0);
    lines.push(
      `<div class="summary-line"><span class="tmpl">${
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
            }"><span class="ms-count">#${h.milestone.toLocaleString()} ${
              h.projected ? " (projection)" : ""
            }</span><span class="ms-date">${h.label}</span></div>`
        )
        .join("");
      return `<div class="ms-card"><div class="ms-title">${
        group.template
      }</div>${rows || '<div class="ms-none">No milestones</div>'}</div>`;
    })
    .join("");
}
let statusCharts = {};
function renderStatusCharts(statusData) {
  const wrap = document.getElementById("statusCharts");
  const section = document.getElementById("statusSection");
  if (!wrap || !section) return;
  const byT = (statusData && statusData.byTemplate) || {};
  const ords = Object.keys(byT);
  if (!ords.length) {
    section.style.display = "none";
    wrap.innerHTML = "";
    return;
  }
  section.style.display = "block";
  wrap.innerHTML = "";
  ords.forEach((ord, idx) => {
    const item = byT[ord];
    const total = item.new + item.learning + item.review;
    const div = document.createElement("div");
    div.className = "status-item";
    const cv = document.createElement("canvas");
    const lab = document.createElement("div");
    lab.className = "status-label";
    lab.textContent = `${item.name} (${total})`;
    div.appendChild(cv);
    div.appendChild(lab);
    wrap.appendChild(div);
    const cfg = {
      type: "doughnut",
      data: {
        labels: ["New", "Learning", "Review"],
        datasets: [
          {
            data: [item.new, item.learning, item.review],
            backgroundColor: ["#4facfe", "#ffb347", "#34d399"],
            borderWidth: 0,
          },
        ],
      },
      options: {
        plugins: {
          legend: {
            position: "right",
            display: true,
            labels: { color: "#e6edf3", font: { size: 10 }, boxWidth: 10 },
          },
        },
        cutout: "55%",
        responsive: true,
        maintainAspectRatio: false,
      },
    };
    const chart = new Chart(cv, cfg);
    cv.parentElement.style.position = "relative";
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
    if (s.learningHistory)
      renderLearningHistorySummary(s.learningHistory, s.granularity || "days");
    if (s.timeSpent) renderTimeSpent(s.timeSpent); // ensure call before difficult etc.
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
    if (s.timeStudied) renderTimeStudied(s.timeStudied);
    // KPI boxes
    const compBox = document.getElementById("completionBox");
    const studiedBox = document.getElementById("studiedTimeBox");
    if (compBox && typeof s.completionPercent === "number") {
      const cp = document.getElementById("completionPercent");
      if (cp) cp.textContent = s.completionPercent.toFixed(1) + "%";
      compBox.style.display = "inline-flex";
    }
    if (studiedBox && typeof s.totalStudiedSeconds === "number") {
      const st = document.getElementById("studiedTimeHHMM");
      if (st) st.textContent = formatStudiedHoursOnly(s.totalStudiedSeconds);
      studiedBox.style.display = "inline-flex";
    }
  } catch (e) {
    console.error(e);
  }
}
function togglePill() {
  const pill = document.getElementById("floatingControls");
  if (!pill) return;
  const content = pill.querySelector(".pill-content");
  if (!content) {
    pill.classList.toggle("collapsed");
    return;
  }
  const isCollapsed = pill.classList.contains("collapsed");
  if (isCollapsed) {
    // expand
    pill.classList.remove("collapsed");
    content.style.display = "block";
    const targetHeight = content.scrollHeight + "px";
    content.style.maxHeight = "0px";
    requestAnimationFrame(() => {
      content.style.transition =
        "max-height .55s cubic-bezier(.34,1.56,.64,1), opacity .4s ease";
      content.style.maxHeight = targetHeight;
      content.style.opacity = "1";
    });
    setTimeout(() => {
      content.style.maxHeight = "";
      content.style.transition = "";
    }, 600);
  } else {
    // collapse
    const startHeight = content.scrollHeight + "px";
    content.style.maxHeight = startHeight;
    content.style.opacity = "1";
    requestAnimationFrame(() => {
      content.style.transition = "max-height .5s ease, opacity .35s ease";
      content.style.maxHeight = "0px";
      content.style.opacity = "0";
    });
    setTimeout(() => {
      pill.classList.add("collapsed");
      content.style.transition = "";
      content.style.display = "";
    }, 520);
  }
}
function animateStreak() {
  const sc = document.getElementById("streakContainer");
  if (sc) {
    sc.classList.add("animate-gradient");
  }
}
window.addEventListener("DOMContentLoaded", () => {
  animateStreak();
});
function formatHours(n) {
  return (n / 3600).toFixed(2);
}
function formatDays(n) {
  return (n / 86400).toFixed(2);
}
function secsToHHMM(secs) {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}h`;
}
function secsToHHMMTotal(secs) {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`;
}
function formatStudiedXhYm(totalSeconds) {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  return `${h}h${m}m`;
}
function formatStudiedHoursOnly(totalSeconds) {
  const h = Math.round(totalSeconds / 3600);
  return `${h}`;
}
function renderTimeStudied(ds) {
  const section = document.getElementById("timeStudiedSection");
  const canvas = document.getElementById("timeStudiedChart");
  if (!section || !canvas) return;
  const labels = ds.labels || [];
  const series = ds.series || [];
  if (!labels.length || !series.length) {
    section.style.display = "none";
    return;
  }
  section.style.display = "block";
  const ctx = canvas.getContext("2d");
  const single = series.length <= 1;
  const datasets = series.map((s, i) => ({
    label: s.label,
    data: s.data,
    backgroundColor: paletteColor(i) + "cc",
    stack: "t",
  }));
  // Determine max seconds and convert to hour step size (3600 secs). We'll show integer hours only.
  let maxSec = 0;
  datasets.forEach((d) => {
    d.data.forEach((v) => {
      if (v > maxSec) maxSec = v;
    });
  });
  const cfg = {
    type: "bar",
    data: { labels, datasets },
    options: {
      responsive: true,
      plugins: {
        legend: {
          display: !single,
          labels: { color: "#e6edf3", font: { size: 10 } },
        },
        tooltip: {
          callbacks: {
            label: (c) => {
              const h = Math.floor(c.parsed.y / 3600);
              const m = Math.floor((c.parsed.y % 3600) / 60);
              return `${c.dataset.label}: ${h}h ${m}m`;
            },
          },
        },
      },
      scales: {
        x: {
          stacked: true,
          ticks: { color: "#9aa2ab" },
          grid: { color: "#30363d" },
        },
        y: {
          stacked: true,
          min: 0,
          ticks: {
            color: "#9aa2ab",
            stepSize: 3600,
            callback: (v) => v / 3600 + "h",
          },
          grid: { color: "#30363d" },
          title: {
            display: true,
            text: "Hours",
            color: "#e6edf3",
            font: { size: 11 },
          },
        },
      },
    },
  };
  timeStudiedChart = ensureChart(timeStudiedChart, ctx, cfg);
  const summaryEl = document.getElementById("timeStudiedSummary");
  if (summaryEl) {
    summaryEl.classList.add("summaries");
    const totals = ds.totalsSeconds || {};
    const totalAll = ds.totalSecondsAll || 0;
    const lines = [];
    function fmtLine(name, sec) {
      const h = Math.floor(sec / 3600);
      const m = Math.floor((sec % 3600) / 60);
      const days = (sec / 86400).toFixed(2);
      return `<div class='summary-line'><span class='tmpl'>${name}</span>: You studied <b>${h}h ${m}m (${days} days)</b> in total.</div>`;
    }
    Object.keys(totals)
      .sort()
      .forEach((name) => {
        lines.push(fmtLine(name, totals[name]));
      });
    lines.push(fmtLine("Total", totalAll));
    summaryEl.innerHTML = lines.join("");
  }
}
function renderLearningHistorySummary(dataset, granularity) {
  const box = document.getElementById("learningHistorySummary");
  if (!box) return;
  const labels = dataset.labels || [];
  const series = dataset.series || [];
  if (!labels.length || !series.length) {
    box.style.display = "none";
    box.innerHTML = "";
    return;
  }
  const unit =
    granularity && granularity.endsWith("s")
      ? granularity.slice(0, -1)
      : granularity || "day";
  const lines = series.map((s) => {
    const total = (s.data || []).reduce((a, b) => a + (b || 0), 0);
    const periods =
      (s.data || []).filter((v) => typeof v === "number").length || 1;
    const avg = total / periods;
    return `<div class='summary-line'><span class='tmpl'>${
      s.label
    }</span>: You learned <b>${avg.toFixed(
      1
    )}</b> new cards per ${unit} on average.</div>`;
  });
  box.innerHTML = lines.join("");
  box.style.display = "block";
}
