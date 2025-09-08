/**
 * @typedef {object} AnkiState
 * @property {string} [granularity]
 * @property {string[]} [templates]
 * @property {boolean} [deckName]
 * @property {boolean} [modelName]
 * @property {number} [count]
 * @property {string[]} [selectedTemplates]
 * @property {boolean} [forecastEnabled]
 * @property {number} [streak]
 * @property {object} [progress]
 * @property {object} [learningHistory]
 * @property {object} [timeSpent]
 * @property {object} [difficult]
 * @property {object} [status]
 * @property {object} [timeStudied]
 * @property {number} [completionPercent]
 * @property {number} [totalStudiedSeconds]
 */

const app = {
  // Chart instances
  charts: {
    deckcompletionstats: null,
    learningHistory: null,
    timeSpent: null,
    timeStudied: null,
    timeHist: {},
    status: {},
  },

  // State
  state: {
    currentGranularity: "days",
    deckPromptShown: false,
  },

  // DOM element selectors
  el: {
    deckCount: "#deckCount",
    currentDeck: "#currentDeck",
    currentModel: "#currentModel",
    modelTemplates: "#modelTemplates",
    granularityRadios: '#granularityRadios input[type="radio"]',
    forecastToggle: "#forecastToggle",
    startDate: "#startDate",
    endDate: "#endDate",
    clearStartDate: "#clearStartDate",
    clearEndDate: "#clearEndDate",
    applyDateFilter: "#applyDateFilter",
    streakContainer: "#streakContainer",
    streakDays: "#streakDays",
    statsChart: "#statsChart",
    forecastSummaries: "#forecastSummaries",
    summaries: "#summaries",
    milestonesSection: "#milestonesSection",
    milestonesContent: "#milestonesContent",
    learningHistoryChart: "#learningHistoryChart",
    learningHistorySummary: "#learningHistorySummary",
    timeSpentCharts: "#timeSpentCharts",
    timeSpentTables: "#timeSpentTables",
    difficultCharts: "#difficultCharts",
    difficultTables: "#difficultTables",
    statusCharts: "#statusCharts",
    statusSection: "#statusSection",
    floatingControls: "#floatingControls",
    timeStudiedSection: "#timeStudiedSection",
    timeStudiedChart: "#timeStudiedChart",
    timeStudiedSummary: "#timeStudiedSummary",
    completionBox: "#completionBox",
    completionPercent: "#completionPercent",
    studiedTimeBox: "#studiedTimeBox",
    studiedTimeHHMM: "#studiedTimeHHMM",
    floatingControls: "#floatingControls",
  },

  /**
   * Initializes the application, sets up event listeners.
   */
  init() {
    window.addEventListener("DOMContentLoaded", () => {
      this.ui.animateStreak();

      const pillHeader = document.querySelector(
        `${this.el.floatingControls} .pill-header`
      );
      if (pillHeader) {
        pillHeader.addEventListener("click", () => {
          this.ui.togglePill();
        });
      }

      document
        .querySelectorAll(this.el.granularityRadios)
        .forEach((radio) => {
          radio.addEventListener("change", (e) => {
            this.anki.setGranularity(e.target.value);
          });
        });

      const forecastToggle = document.querySelector(this.el.forecastToggle);
      if (forecastToggle) {
        forecastToggle.addEventListener("change", (e) => {
          this.anki.setForecast(e.target.checked);
        });
      }

      const currentDeck = document.querySelector(this.el.currentDeck);
      if (currentDeck) {
        currentDeck.addEventListener("click", () => this.anki.selectDeck());
      }

      const currentModel = document.querySelector(this.el.currentModel);
      if (currentModel) {
        currentModel.addEventListener("click", () => this.anki.selectModel());
      }

      // Date filter event listeners - only apply when Apply button is clicked
      const applyDateFilter = document.querySelector(this.el.applyDateFilter);
      if (applyDateFilter) {
        applyDateFilter.addEventListener("click", () => {
          const startDateInput = document.querySelector(this.el.startDate);
          const endDateInput = document.querySelector(this.el.endDate);
          
          const startValue = startDateInput ? startDateInput.value || null : null;
          const endValue = endDateInput ? endDateInput.value || null : null;
          
          // Parse flexible dates
          const parsedStartValue = startValue ? this.utils.parseFlexibleDate(startValue, true) : null;
          const parsedEndValue = endValue ? this.utils.parseFlexibleDate(endValue, false) : null;
          
          // Update the input fields with parsed values
          if (startDateInput && parsedStartValue && parsedStartValue !== startValue) {
            startDateInput.value = parsedStartValue;
          }
          if (endDateInput && parsedEndValue && parsedEndValue !== endValue) {
            endDateInput.value = parsedEndValue;
          }
          
          this.anki.setDateFilters(parsedStartValue, parsedEndValue);
        });
      }

      // Clear button event listeners
      const clearStartDate = document.querySelector(this.el.clearStartDate);
      if (clearStartDate) {
        clearStartDate.addEventListener("click", () => {
          const startDateInput = document.querySelector(this.el.startDate);
          if (startDateInput) {
            startDateInput.value = "";
          }
        });
      }

      const clearEndDate = document.querySelector(this.el.clearEndDate);
      if (clearEndDate) {
        clearEndDate.addEventListener("click", () => {
          const endDateInput = document.querySelector(this.el.endDate);
          if (endDateInput) {
            endDateInput.value = "";
          }
        });
      }

      // Enter key support for date inputs
      const startDate = document.querySelector(this.el.startDate);
      if (startDate) {
        startDate.addEventListener("keydown", (e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            applyDateFilter && applyDateFilter.click();
          }
        });
      }

      const endDate = document.querySelector(this.el.endDate);
      if (endDate) {
        endDate.addEventListener("keydown", (e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            applyDateFilter && applyDateFilter.click();
          }
        });
      }
    });
  },

  /**
   * Communication with Anki backend.
   */
  anki: {
    /**
     * Sends a command to the Anki backend.
     * @param {string} commandString The command to send.
     */
    pycmd(commandString) {
      if (window.pycmd) {
        window.pycmd(commandString);
      }
    },

    refresh() {
      this.pycmd("deckcompletionstats_refresh");
    },

    selectDeck() {
      this.pycmd("deckcompletionstats_select_deck");
    },

    selectModel() {
      this.pycmd("deckcompletionstats_select_model");
    },

    /**
     * @param {number[]} templateOrds
     */
    updateTemplates(templateOrds) {
      this.pycmd(
        "deckcompletionstats_update_templates:" + JSON.stringify(templateOrds)
      );
    },

    /**
     * @param {string} granularity
     */
    setGranularity(granularity) {
      this.pycmd("deckcompletionstats_set_granularity:" + granularity);
    },

    /**
     * @param {boolean} enabled
     */
    setForecast(enabled) {
      this.pycmd("deckcompletionstats_set_forecast:" + (enabled ? "1" : "0"));
    },

    /**
     * @param {string|null} startDate
     * @param {string|null} endDate
     */
    setDateFilters(startDate, endDate) {
      this.pycmd(
        "deckcompletionstats_set_date_filters:" + JSON.stringify({
          start: startDate,
          end: endDate
        })
      );
    },
  },

  /**
   * UI update and interaction logic.
   */
  ui: {
    /**
     * @param {number} count
     */
    updateCount(count) {
      const el = document.querySelector(app.el.deckCount);
      if (el) {
        el.textContent = `(${count.toLocaleString()} cards)`;
      }
    },

    /**
     * @param {string} name
     */
    updateDeckName(name) {
      const el = document.querySelector(app.el.currentDeck);
      if (el) {
        el.textContent = name;
      }
    },

    /**
     * @param {string} name
     */
    updateModelName(name) {
      const el = document.querySelector(app.el.currentModel);
      if (el) {
        el.textContent = name;
      }
    },

    /**
     * @param {{ord: number, name: string}[]} templates
     * @param {number[]} selected
     * @param {string} modelName
     */
    setModelTemplates(templates, selected, modelName) {
      const container = document.querySelector(app.el.modelTemplates);
      if (!container) return;
      
      // Check if we're in "Any Model" mode
      const isAnyModel = modelName === "(Any Model)";
      
      // Find the templates group (Card Types section) and hide it in "Any Model" mode
      try {
        const templatesGroup = container.closest('.templates-group');
        if (templatesGroup) {
          templatesGroup.style.display = isAnyModel ? 'none' : '';
        }
      } catch (e) {
        console.warn('Could not find templates-group:', e);
      }
      
      // If in "Any Model" mode, don't populate the templates
      if (isAnyModel) {
        container.innerHTML = "";
        return;
      }
      
      container.innerHTML = "";
      (templates || []).forEach((t) => {
        const wrapper = document.createElement("label");
        wrapper.style.display = "flex";
        wrapper.style.alignItems = "center";
        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.value = t.ord;
        cb.checked = !selected || selected.includes(t.ord);
        cb.addEventListener("change", () =>
          app.anki.updateTemplates(this.getSelectedTemplateOrds())
        );
        const span = document.createElement("span");
        span.textContent = t.name || `Card ${t.ord + 1}`;
        wrapper.appendChild(cb);
        wrapper.appendChild(span);
        container.appendChild(wrapper);
      });
    },

    /**
     * @returns {number[]}
     */
    getSelectedTemplateOrds() {
      return Array.from(
        document.querySelectorAll(
          '#modelTemplates input[type="checkbox"]'
        )
      )
        .filter((cb) => cb.checked)
        .map((cb) => parseInt(cb.value, 10));
    },

    /**
     * @param {string} startDate
     * @param {string} endDate
     */
    updateDateFilters(startDate, endDate) {
      const startEl = document.querySelector(app.el.startDate);
      if (startEl) {
        startEl.value = startDate || "";
      }
      
      const endEl = document.querySelector(app.el.endDate);
      if (endEl) {
        endEl.value = endDate || "";
      }
    },

    togglePill() {
      const pill = document.querySelector(app.el.floatingControls);
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
    },

    animateStreak() {
      const sc = document.querySelector(app.el.streakContainer);
      if (sc) {
        sc.classList.add("animate-gradient");
      }
    },
  },

  /**
   * Chart rendering functions.
   */
  charts_impl: {
    /**
     * @param {Chart} existing
     * @param {HTMLCanvasElement} ctx
     * @param {import("chart.js").ChartConfiguration} config
     * @returns {Chart}
     */
    ensureChart(existing, ctx, config) {
      if (existing) {
        existing.config.data = config.data;
        existing.config.options = config.options || existing.config.options;
        existing.update();
        return existing;
      }
      return new Chart(ctx, config);
    },

    /**
     * @param {number} i
     * @returns {string}
     */
    paletteColor(i) {
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
    },

    /**
     * @param {string} targetId
     * @param {object} dataset
     * @returns {Chart | null}
     */
    renderStackedBarChart(targetId, dataset) {
      const ctx = document.getElementById(targetId);
      if (!ctx || typeof Chart === "undefined") return null;
      const labels = dataset.labels || [];
      const series = dataset.series || [];
      const singleTemplate = series.length <= 1;
      const dataSets = series.map((s, i) => ({
        label: s.label,
        data: s.data,
        backgroundColor: this.paletteColor(i) + "cc",
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
            tooltip: {
              callbacks: {
                title: (items) => {
                  if (!items.length) return "";
                  const l = items[0].label;
                  if (app.state.currentGranularity === "weeks")
                    return app.utils.weekRangeFromLabel(l);
                  return l;
                },
              },
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
        app.charts.learningHistory = this.ensureChart(
          app.charts.learningHistory,
          ctx,
          cfg
        );
        return app.charts.learningHistory;
      }
      if (targetId === "timeSpentChart") {
        app.charts.timeSpent = this.ensureChart(
          app.charts.timeSpent,
          ctx,
          cfg
        );
        return app.charts.timeSpent;
      }
      return this.ensureChart(null, ctx, cfg);
    },

    /**
     * @param {object} progress
     */
    renderProgressChart(progress) {
      const ctx = document.querySelector(app.el.statsChart);
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
          borderColor: this.paletteColor(i),
          backgroundColor: this.paletteColor(i) + "33",
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
            borderColor: this.paletteColor(i),
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
                backgroundColor: this.paletteColor(i),
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
          tooltip: {
            callbacks: {
              title: (items) => {
                if (!items.length) return "";
                const l = items[0].label;
                return app.state.currentGranularity === "weeks"
                  ? app.utils.weekRangeFromLabel(l)
                  : l;
              },
            },
          },
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
      const cfg = {
        type: "line",
        data: { labels: baseLabels, datasets },
        options,
      };
      app.charts.deckcompletionstats = this.ensureChart(
        app.charts.deckcompletionstats,
        ctx,
        cfg
      );
    },

    /**
     * @param {object} dataset
     */
    renderTimeSpent(dataset) {
      const wrap = document.querySelector(app.el.timeSpentCharts);
      const tablesWrap = document.querySelector(app.el.timeSpentTables);
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
      ords.forEach((ord) => {
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
              {
                data: item.counts,
                label: item.name,
                backgroundColor: "#4facfe66",
              },
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
          plugins: [{
            afterDatasetsDraw: function(chart, args, options) {
              const ctx = chart.ctx;
              const meta = chart.getDatasetMeta(0);
              meta.data.forEach((bar, index) => {
                const value = chart.data.datasets[0].data[index];
                if (value > 0) {
                  ctx.save();
                  ctx.fillStyle = '#e6edf3';
                  ctx.font = '8px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
                  ctx.textAlign = 'center';
                  const x = bar.x;
                  const y = bar.y - 5;
                  ctx.fillText(value, x, y);
                  ctx.restore();
                }
              });
            }
          }],
        };
        app.charts.timeHist[ord] = new Chart(cv, cfg);
      });
      // tables (top time cards per template)
      const top = dataset.top || {};
      const histograms = dataset.histograms || {};
      const rowContainer = document.createElement("div");
      rowContainer.className = "flex-row";
      Object.keys(top).forEach((ord) => {
        const rows = top[ord];
        if (!rows || !rows.length) return;
        const col = document.createElement("div");
        col.className = "flex-col";
        const h = document.createElement("div");
        h.className = "template-head";
        // Get template name from histograms data instead of templateNames
        const templateName = histograms[ord] ? histograms[ord].name : `Template ${ord}`;
        h.textContent = templateName;
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
    },

    /**
     * @param {object} dataset
     */
    renderDifficult(dataset) {
      const wrapCharts = document.querySelector(app.el.difficultCharts);
      const wrapTables = document.querySelector(app.el.difficultTables);
      if (!wrapCharts || !wrapTables) return;
      wrapCharts.innerHTML = "";
      wrapTables.innerHTML = "";
      const byT = dataset.byTemplate || {};
      const nameMap = dataset.templateNames || {};
      const ords = Object.keys(byT);
      if (!ords.length) {
        return;
      }
      // Build histogram per template of failure counts (x=failure count, y=number of cards)
      ords.forEach((ord) => {
        const rows = byT[ord] || [];
        // Determine max failures in this template
        let maxFail = 0;
        rows.forEach((r) => {
          if (r.failures > maxFail) maxFail = r.failures;
        });
        const counts = new Array(maxFail + 1).fill(0);
        rows.forEach((r) => {
          counts[r.failures] = (counts[r.failures] || 0) + 1;
        });
        // Create chart container similar to time histograms
        const div = document.createElement("div");
        div.className = "time-item";
        const cv = document.createElement("canvas");
        const lab = document.createElement("div");
        lab.className = "time-label";
        lab.textContent = nameMap[ord] || "Template " + ord;
        div.appendChild(cv);
        div.appendChild(lab);
        wrapCharts.appendChild(div);
        const labels = counts.map((_, i) => i.toString());
        const cfg = {
          type: "bar",
          data: {
            labels,
            datasets: [
              {
                data: counts,
                backgroundColor: "#ff6b6b66",
                label: "Failures",
              },
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
                title: {
                  display: true,
                  text: "Number of failures",
                  color: "#e6edf3",
                  font: { size: 11 },
                },
              },
              y: {
                ticks: { color: "#9aa2ab", font: { size: 9 } },
                grid: { color: "#30363d" },
                title: {
                  display: true,
                  text: "Cards",
                  color: "#e6edf3",
                  font: { size: 11 },
                },
              },
            },
          },
          plugins: [{
            afterDatasetsDraw: function(chart, args, options) {
              const ctx = chart.ctx;
              const meta = chart.getDatasetMeta(0);
              meta.data.forEach((bar, index) => {
                const value = chart.data.datasets[0].data[index];
                if (value > 0) {
                  ctx.save();
                  ctx.fillStyle = '#e6edf3';
                  ctx.font = '8px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
                  ctx.textAlign = 'center';
                  const x = bar.x;
                  const y = bar.y - 5;
                  ctx.fillText(value, x, y);
                  ctx.restore();
                }
              });
            }
          }],
        };
        new Chart(cv, cfg);
      });
      // Tables limited to top 10 per template
      const rowContainer = document.createElement("div");
      rowContainer.className = "flex-row";
      ords.forEach((ord) => {
        const rows = byT[ord];
        if (!rows || !rows.length) return;
        const top = rows.slice(0, 10);
        const col = document.createElement("div");
        col.className = "flex-col";
        const h = document.createElement("div");
        h.className = "template-head";
        h.textContent = nameMap[ord] || "Template " + ord;
        col.appendChild(h);
        const table = document.createElement("table");
        table.className = "data-table";
        table.innerHTML =
          "<thead><tr><th>Card</th><th>Failures</th></tr></thead>";
        const tb = document.createElement("tbody");
        top.forEach((r) => {
          const tr = document.createElement("tr");
          tr.innerHTML = `<td>${r.front}</td><td>${r.failures}</td>`;
          tb.appendChild(tr);
        });
        table.appendChild(tb);
        col.appendChild(table);
        rowContainer.appendChild(col);
      });
      wrapTables.appendChild(rowContainer);
    },

    /**
     * @param {object} progress
     */
    renderForecastSummaries(progress) {
      const box =
        document.querySelector(app.el.forecastSummaries) ||
        document.querySelector(app.el.summaries);
      if (!box) return;
      const lines = [];
      (progress.series || []).forEach((s) => {
        const iso = s.forecastCompletionISO;
        if (!iso) return;
        const date = app.utils.isoToLocale(iso);
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
    },

    /**
     * @param {object} progress
     */
    renderMilestones(progress) {
      const section = document.querySelector(app.el.milestonesSection);
      const content = document.querySelector(app.el.milestonesContent);
      if (!section || !content) return;
      const ms = this.computeMilestones(progress);
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
                `<div class="milestone-row ${
                  h.projected ? "proj" : ""
                }"><span class="milestone-count">#${h.milestone.toLocaleString()} ${
                  h.projected ? " (projection)" : ""
                }</span><span class="milestone-date">${h.label}</span></div>`
            )
            .join("");
          return `<div class="milestone-card"><div class="milestone-title">${
            group.template
          }</div>${rows || '<div class="milestone-none">No milestones</div>'}</div>`;
        })
        .join("");
    },

    /**
     * @param {object} progress
     * @returns {any[]}
     */
    computeMilestones(progress) {
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
              label: app.utils.isoToLocale(iso),
              projected: !!projected,
            });
        }
        const thresholds = [1, 100, 500];
        for (let v = 1000; v <= total; v += 500) thresholds.push(v);
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
    },

    /**
     * @param {object} statusData
     */
    renderStatusCharts(statusData) {
      const wrap = document.querySelector(app.el.statusCharts);
      const section = document.querySelector(app.el.statusSection);
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
      ords.forEach((ord) => {
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
                labels: {
                  color: "#e6edf3",
                  font: { size: 10 },
                  boxWidth: 10,
                },
              },
            },
            cutout: "55%",
            responsive: true,
            maintainAspectRatio: false,
          },
        };
        app.charts.status[ord] = new Chart(cv, cfg);
        cv.parentElement.style.position = "relative";
      });
    },

    /**
     * @param {object} ds
     * @param {string} granularity
     */
    renderTimeStudied(ds, granularity) {
      const section = document.querySelector(app.el.timeStudiedSection);
      const canvas = document.querySelector(app.el.timeStudiedChart);
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
        backgroundColor: this.paletteColor(i) + "cc",
        stack: "t",
      }));
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
                title: (items) => {
                  if (!items.length) return "";
                  const l = items[0].label;
                  return app.state.currentGranularity === "weeks"
                    ? app.utils.weekRangeFromLabel(l)
                    : l;
                },
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
      app.charts.timeStudied = this.ensureChart(
        app.charts.timeStudied,
        ctx,
        cfg
      );
      const summaryEl = document.querySelector(app.el.timeStudiedSummary);
      if (summaryEl) {
        summaryEl.classList.add("summaries");
        const totals = ds.totalsSeconds || {};
        const totalAll = ds.totalSecondsAll || 0;
        const lines = [];
        const periodCount = labels.length || 1;
        const unit =
          granularity && granularity.endsWith("s")
            ? granularity.slice(0, -1)
            : granularity || "day";
        function fmtLine(name, sec) {
          const h = Math.floor(sec / 3600);
          const m = Math.floor((sec % 3600) / 60);
          const days = (sec / 86400).toFixed(2);
          const avgMin = Math.round(sec / periodCount / 60) || 0;
          return `<div class='summary-line'><span class='tmpl'>${name}</span>: You studied <b>${h}h ${m}m (${days} days)</b> in total. That's ${avgMin}m per ${unit}.</div>`;
        }
        Object.keys(totals)
          .sort()
          .forEach((name) => {
            lines.push(fmtLine(name, totals[name]));
          });
        lines.push(fmtLine("Total", totalAll));
        summaryEl.innerHTML = lines.join("");
      }
    },

    /**
     * @param {object} dataset
     * @param {string} granularity
     */
    renderLearningHistorySummary(dataset, granularity) {
      const box = document.querySelector(app.el.learningHistorySummary);
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
    },
  },

  /**
   * Utility functions.
   */
  utils: {
    /**
     * Parse flexible date input and return ISO format date.
     * @param {string} dateStr - Input date string
     * @param {boolean} defaultToStart - Whether to default to start (true) or end (false) of period
     * @returns {string|null} ISO format date or null
     */
    parseFlexibleDate(dateStr, defaultToStart = true) {
      if (!dateStr) return null;
      
      dateStr = dateStr.trim();
      
      // If already in ISO format, return as-is
      if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
        return dateStr;
      }
      
      // Handle different formats
      if (/^\d{4}$/.test(dateStr)) {  // Just year: "2024"
        const year = dateStr;
        if (defaultToStart) {
          return `${year}-01-01`;
        } else {
          return `${year}-12-31`;
        }
      } else if (/^\d{1,2}\.\d{4}$/.test(dateStr)) {  // Month.Year: "01.2024"
        const parts = dateStr.split('.');
        const month = parts[0].padStart(2, '0');
        const year = parts[1];
        if (defaultToStart) {
          return `${year}-${month}-01`;
        } else {
          // Get last day of month
          const lastDay = new Date(parseInt(year), parseInt(month), 0).getDate();
          return `${year}-${month}-${lastDay.toString().padStart(2, '0')}`;
        }
      } else if (/^\d{1,2}\.\d{1,2}\.\d{4}$/.test(dateStr)) {  // DD.MM.YYYY: "01.01.2024"
        const parts = dateStr.split('.');
        const day = parts[0].padStart(2, '0');
        const month = parts[1].padStart(2, '0');
        const year = parts[2];
        return `${year}-${month}-${day}`;
      }
      
      // If no pattern matches, try to parse as-is
      try {
        const date = new Date(dateStr);
        if (!isNaN(date.getTime())) {
          return date.toISOString().split('T')[0];
        }
      } catch (e) {
        // Ignore parsing errors
      }
      
      return null;
    },

    /**
     * @param {string} iso
     * @returns {string}
     */
    isoToLocale(iso) {
      try {
        return new Date(iso).toLocaleDateString();
      } catch (e) {
        return iso;
      }
    },

    /**
     * @param {string} label
     * @returns {string}
     */
    weekRangeFromLabel(label) {
      if (!/^\d{4}-W\d{2}$/.test(label)) return label;
      try {
        const [yPart, wPart] = label.split("-W");
        const year = parseInt(yPart, 10);
        const week = parseInt(wPart, 10);
        if (!(year > 0 && week > 0)) return label;
        // ISO week 1: week containing Jan 4. Compute Monday of week 1 then offset.
        const jan4 = new Date(Date.UTC(year, 0, 4));
        const jan4Day = jan4.getUTCDay() || 7; // 1..7
        const week1Mon = new Date(jan4);
        week1Mon.setUTCDate(jan4.getUTCDate() - (jan4Day - 1));
        const start = new Date(week1Mon);
        start.setUTCDate(week1Mon.getUTCDate() + (week - 1) * 7);
        const end = new Date(start);
        end.setUTCDate(start.getUTCDate() + 6);
        const fmt = (d) => d.toISOString().slice(0, 10);
        return `${fmt(start)} - ${fmt(end)}`;
      } catch (e) {
        return label;
      }
    },

    /**
     * @param {number} totalSeconds
     * @returns {string}
     */
    formatStudiedHoursOnly(totalSeconds) {
      const h = Math.round(totalSeconds / 3600);
      return `${h}`;
    },
  },

  /**
   * Main state update function, called from Anki.
   * @param {AnkiState} s
   */
  updateState(s) {
    if (s.granularity) app.state.currentGranularity = s.granularity;

    if (typeof s.count === "number") this.ui.updateCount(s.count);
    if (s.deckName) this.ui.updateDeckName(s.deckName);
    if (s.modelName) this.ui.updateModelName(s.modelName);
    if (Array.isArray(s.templates))
      this.ui.setModelTemplates(s.templates, s.selectedTemplates, s.modelName || "");

    if (s.granularity) {
      document
        .querySelectorAll(this.el.granularityRadios)
        .forEach((r) => {
          if (r.value === s.granularity) r.checked = true;
        });
    }

    const fcToggle = document.querySelector(this.el.forecastToggle);
    if (fcToggle && typeof s.forecastEnabled === "boolean")
      fcToggle.checked = s.forecastEnabled;

    // Update date filters
    this.ui.updateDateFilters(s.dateFilterStart, s.dateFilterEnd);

    if (typeof s.streak === "number") {
      const sc = document.querySelector(this.el.streakContainer);
      const sd = document.querySelector(this.el.streakDays);
      if (sc && sd) {
        sd.textContent = s.streak.toString();
        sc.style.display = s.streak > 0 ? "inline-flex" : "none";
      }
    }

    if (s.progress) {
      this.charts_impl.renderProgressChart(s.progress);
      this.charts_impl.renderForecastSummaries(s.progress);
      this.charts_impl.renderMilestones(s.progress);
    }
    if (s.learningHistory) {
      this.charts_impl.renderStackedBarChart(
        "learningHistoryChart",
        s.learningHistory
      );
      this.charts_impl.renderLearningHistorySummary(
        s.learningHistory,
        s.granularity || "days"
      );
    }
    if (s.timeSpent) this.charts_impl.renderTimeSpent(s.timeSpent);
    if (s.difficult) this.charts_impl.renderDifficult(s.difficult);
    if (s.status) this.charts_impl.renderStatusCharts(s.status);
    if (s.timeStudied)
      this.charts_impl.renderTimeStudied(s.timeStudied, s.granularity || "days");

    const compBox = document.querySelector(this.el.completionBox);
    const studiedBox = document.querySelector(this.el.studiedTimeBox);
    if (compBox && typeof s.completionPercent === "number") {
      const cp = document.querySelector(this.el.completionPercent);
      if (cp) cp.textContent = s.completionPercent.toFixed(1) + "%";
      compBox.style.display = "inline-flex";
    }
    if (studiedBox && typeof s.totalStudiedSeconds === "number") {
      const st = document.querySelector(this.el.studiedTimeHHMM);
      if (st)
        st.textContent = this.utils.formatStudiedHoursOnly(
          s.totalStudiedSeconds
        );
      studiedBox.style.display = "inline-flex";
    }
  },
};

app.init();

/**
 * Entry point for updates from Anki.
 * @param {string} data JSON string from Anki
 */
function deckcompletionstatsUpdateState(data) {
  try {
    const s = JSON.parse(data);
    app.updateState(s);
  } catch (e) {
    console.error("Error parsing data from Anki:", e);
  }
}
