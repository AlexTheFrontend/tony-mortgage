/* Tony's View tracker: draws the stacked charts from window.TONY_DATA (site/data.js). */
(function () {
  "use strict";

  const D = window.TONY_DATA;
  if (!D || !window.echarts) {
    document.getElementById("chart").textContent =
      "Data or chart library missing. Run: uv run python -m scripts.build_data";
    return;
  }

  const GROUPS = ["float", "6m", "1y", "18m", "2y", "3y_plus", "mix", "none"];
  const GROUP_LABEL = {
    float: "Float", "6m": "6 months", "1y": "1 year", "18m": "18 months",
    "2y": "2 years", "3y_plus": "3+ years", mix: "Mix", none: "No advice",
  };
  const TERM_LABEL = { 0: "float", 6: "6m", 12: "1y", 18: "18m", 24: "2y", 36: "3y", 48: "4y", 60: "5y" };
  // Tony's lowest lender rates are drawn for these terms, in the colour of the matching mortgage line.
  const TABLE_TERMS = { 12: "m1", 24: "m2", 36: "m3" };
  // Pixel layout of the stacked charts. The chart box is 880px high (style.css).
  const GRID = [
    { top: 72, height: 270 },  // rates
    { top: 376, height: 34 },  // advice strip
    { top: 446, height: 150 }, // tone
    { top: 640, height: 170 }, // advice score
  ];
  const GRID_RIGHT = 64; // room for the end labels of the lines
  const SLIDER_TOP = 840;

  const issues = D.issues;
  const lastIssue = issues[issues.length - 1];
  const weekAfterLast = addDays(lastIssue.date, 7);
  const endDate = weekAfterLast > D.ocr_last.date ? weekAfterLast : D.ocr_last.date;
  const toneAvg = rolling(issues.map((r) => r.tone.score), 8);
  // Runs of weeks with the same advice group, so the strip has a gap only where the advice changes.
  const adviceRuns = [];
  issues.forEach((r, i) => {
    const end = i + 1 < issues.length ? issues[i + 1].date : endDate;
    const last = adviceRuns[adviceRuns.length - 1];
    if (last && last.group === r.borrower.group) last.value[1] = end;
    else adviceRuns.push({ group: r.borrower.group, value: [r.date, end, 0] });
  });
  let C = {}; // colours, read from the CSS tokens on each draw
  let chart = null;
  let pointerIssue = null; // the issue in the tooltip; a click opens it

  // ECharts reads "YYYY-MM-DD" as local midnight, so dates go back to text in local time too.
  function isoDay(ms) {
    const d = new Date(ms);
    return [d.getFullYear(), d.getMonth() + 1, d.getDate()].map((n) => String(n).padStart(2, "0")).join("-");
  }
  function addDays(day, n) {
    const [y, m, d] = day.split("-").map(Number);
    return isoDay(new Date(y, m - 1, d + n).getTime());
  }
  function pct(n) { return n.toFixed(2) + "%"; }
  function money(n) { return "$" + Math.round(n).toLocaleString("en-NZ"); }
  function signed(n, digits) { return (n > 0 ? "+" : "") + n.toFixed(digits); }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function adviceLabel(b) {
    if (b.group === "mix") return "Mix: " + b.terms_months.map((t) => TERM_LABEL[t] || t + "m").join(" + ");
    return GROUP_LABEL[b.group];
  }
  function rolling(values, n) {
    return values.map((_, i) => {
      const part = values.slice(Math.max(0, i - n + 1), i + 1);
      return part.reduce((a, b) => a + b, 0) / part.length;
    });
  }
  // The last item of a date-sorted list with a date on or before `day` (YYYY-MM-DD).
  function lastOnOrBefore(list, day, dateOf) {
    let found = null;
    for (const item of list) {
      if (dateOf(item) > day) break;
      found = item;
    }
    return found;
  }
  function readColours() {
    const style = getComputedStyle(document.documentElement);
    const names = ["fg", "muted", "axis", "grid", "panel", "ocr", "m1", "m2", "m3", "pos", "neg",
      "tony", "fix1", "float"].concat(GROUPS.map((g) => "g-" + g));
    const out = {};
    for (const n of names) out[n] = style.getPropertyValue("--" + n).trim();
    return out;
  }
  function scoreSeries(loan) {
    const k = loan / D.score.loan;
    const line = (key) => D.score.months.map((m, i) => [m + "-15", Math.round(D.score[key][i] * k)]);
    return { tony: line("tony"), fix_1y: line("fix_1y"), float: line("float") };
  }
  function tableRateText(rates) {
    return Object.entries(rates).map(([term, rate]) => `${TERM_LABEL[term] || term + "m"} ${pct(rate)}`).join(", ");
  }

  function renderAdvice(params, api) {
    const start = api.coord([api.value(0), 0]);
    const end = api.coord([api.value(1), 0]);
    const height = api.size([0, 1])[1] * 0.9;
    const rect = echarts.graphic.clipRectByRect(
      { x: start[0], y: start[1] - height / 2, width: Math.max(end[0] - start[0] - 2, 1), height },
      { x: params.coordSys.x, y: params.coordSys.y, width: params.coordSys.width, height: params.coordSys.height });
    return rect && { type: "rect", shape: rect, style: { fill: C["g-" + adviceRuns[params.dataIndex].group] } };
  }

  function endLabel(text) {
    return { show: true, formatter: text, color: C.fg, fontSize: 11, distance: 6 };
  }
  function rateLine(name, data, colour, type, label) {
    return { name, type: "line", xAxisIndex: 0, yAxisIndex: 0, showSymbol: false, sampling: "lttb", data,
      lineStyle: { width: type === "dotted" ? 1.5 : 2, type, color: colour }, itemStyle: { color: colour },
      endLabel: label ? endLabel(label) : { show: false }, labelLayout: { moveOverlap: "shiftY" } };
  }
  function scoreLine(id, name, data, colour, label) {
    return { id, name, type: "line", xAxisIndex: 3, yAxisIndex: 3, showSymbol: false, data,
      lineStyle: { width: 2, color: colour }, itemStyle: { color: colour }, endLabel: endLabel(label),
      labelLayout: { moveOverlap: "shiftY" } };
  }

  function tooltipHtml(t) {
    const day = isoDay(t);
    const rows = [`<b>${day}</b>`];
    const issue = lastOnOrBefore(issues, day, (r) => r.date);
    pointerIssue = issue;
    if (issue) {
      rows.push(`Issue ${issue.date}: <i>${esc(issue.headline)}</i>`);
      rows.push(`Advice: ${esc(adviceLabel(issue.borrower))}`);
      rows.push(`Tone: ${signed(issue.tone.score, 0)}`);
    }
    const ocr = lastOnOrBefore(D.ocr, day, (o) => o.date);
    if (ocr) rows.push(`OCR: ${pct(ocr.rate)}`);
    const mortgage = ["1y", "2y", "3y"]
      .map((k) => [k, lastOnOrBefore(D.mortgage[k], day, (p) => p[0])])
      .filter(([, p]) => p)
      .map(([k, p]) => `${k} ${pct(p[1])}`);
    if (mortgage.length) rows.push(`Mortgage (average advertised): ${mortgage.join(", ")}`);
    const s1 = lastOnOrBefore(D.swap.y1, day, (p) => p[0]);
    const s3 = lastOnOrBefore(D.swap.y3, day, (p) => p[0]);
    if (s1 && s3) rows.push(`Swap: 1y ${pct(s1[1])}, 3y ${pct(s3[1])}`);
    if (issue && issue.lender_min_rates) {
      rows.push("Tony's lowest lender rates: " + tableRateText(issue.lender_min_rates));
    }
    rows.push('<span class="hint">Click for details</span>');
    return rows.join("<br>");
  }

  function buildOption(loan) {
    const s = scoreSeries(loan);
    const timeAxis = (i) => ({
      type: "time", gridIndex: i, min: issues[0].date, max: endDate,
      axisLine: { lineStyle: { color: C.grid } }, splitLine: { show: false },
      axisTick: { show: i === 0 || i === 3 },
      axisLabel: { show: i === 0 || i === 3, color: C.muted, hideOverlap: true },
    });
    const valueAxis = (i, extra) => Object.assign({
      type: "value", gridIndex: i, axisLabel: { color: C.muted }, splitLine: { lineStyle: { color: C.grid } },
    }, extra);
    const tableRates = [];
    for (const r of issues) {
      for (const [term, rate] of Object.entries(r.lender_min_rates || {})) {
        const colour = C[TABLE_TERMS[term]];
        if (colour) tableRates.push({ value: [r.date, rate], itemStyle: { color: colour } });
      }
    }
    const titles = [
      ["Rates (% per year)", 4],
      ["If I were a borrower", GRID[1].top - 26],
      ["Economy tone, -2 to +2 (bars) and 8-week average (line)", GRID[2].top - 26],
      ["Advice score: total interest paid", GRID[3].top - 26],
    ];
    return {
      backgroundColor: "transparent",
      animation: false,
      textStyle: { color: C.fg, fontFamily: "inherit" },
      title: titles.map(([text, top]) => ({ text, left: 8, top, textStyle: { fontSize: 13, fontWeight: 600, color: C.fg } })),
      legend: [
        { type: "scroll", top: 28, left: 8, right: 8, textStyle: { color: C.muted },
          data: ["OCR", "OCR change", "Mortgage 1y", "Mortgage 2y", "Mortgage 3y", "Swap 1y", "Swap 3y", "Tony's lowest lender rates"] },
        { top: GRID[3].top - 26, right: 8, textStyle: { color: C.muted },
          data: ["Tony's advice", "Always fix 1 year", "Always float"] },
      ],
      grid: GRID.map((g) => ({ left: 52, right: GRID_RIGHT, top: g.top, height: g.height })),
      xAxis: GRID.map((_, i) => timeAxis(i)),
      yAxis: [
        valueAxis(0, { min: 0 }),
        { type: "category", gridIndex: 1, data: ["Advice"], show: false },
        valueAxis(2, { min: -2, max: 2, interval: 1 }),
        valueAxis(3, { min: 0, axisLabel: { color: C.muted, formatter: (v) => "$" + Math.round(v / 1000) + "k" } }),
      ],
      axisPointer: { link: [{ xAxisIndex: "all" }], lineStyle: { color: C.axis } },
      tooltip: {
        trigger: "axis", confine: true, axisPointer: { type: "line" },
        backgroundColor: C.panel, borderColor: C.grid, textStyle: { color: C.fg },
        formatter: (params) => tooltipHtml(params[0].axisValue),
      },
      dataZoom: [
        { type: "slider", xAxisIndex: [0, 1, 2, 3], top: SLIDER_TOP, height: 22, right: GRID_RIGHT,
          labelFormatter: (v) => isoDay(v).slice(0, 7) },
        { type: "inside", xAxisIndex: [0, 1, 2, 3], zoomOnMouseWheel: "shift" },
      ],
      series: [
        { name: "OCR", type: "line", step: "end", xAxisIndex: 0, yAxisIndex: 0, showSymbol: false,
          lineStyle: { width: 2.5, color: C.ocr }, itemStyle: { color: C.ocr }, endLabel: endLabel("OCR"),
          data: D.ocr.map((o) => [o.date, o.rate]).concat([[D.ocr_last.date, D.ocr_last.rate]]) },
        { name: "OCR change", type: "scatter", xAxisIndex: 0, yAxisIndex: 0, symbol: "triangle", symbolSize: 9,
          itemStyle: { color: C.ocr }, label: { show: true, fontSize: 10, color: C.fg },
          data: D.ocr.filter((o) => o.change !== null).map((o) => ({
            value: [o.date, o.rate], symbolRotate: o.change < 0 ? 180 : 0,
            label: { formatter: signed(o.change, 2), position: o.change < 0 ? "bottom" : "top" },
          })) },
        rateLine("Mortgage 1y", D.mortgage["1y"], C.m1, "solid", "1y"),
        rateLine("Mortgage 2y", D.mortgage["2y"], C.m2, "solid", "2y"),
        rateLine("Mortgage 3y", D.mortgage["3y"], C.m3, "solid", "3y"),
        rateLine("Swap 1y", D.swap.y1, C.m1, "dotted"),
        rateLine("Swap 3y", D.swap.y3, C.m3, "dotted"),
        // The legend icon is in ink; each diamond takes the colour of its term.
        { name: "Tony's lowest lender rates", type: "scatter", xAxisIndex: 0, yAxisIndex: 0,
          symbol: "diamond", symbolSize: 9, itemStyle: { color: C.fg }, data: tableRates },
        { name: "Advice", type: "custom", xAxisIndex: 1, yAxisIndex: 1, renderItem: renderAdvice,
          encode: { x: [0, 1], y: 2 }, data: adviceRuns.map((c) => c.value) },
        { name: "Tone", type: "bar", xAxisIndex: 2, yAxisIndex: 2, barMaxWidth: 6,
          data: issues.map((r) => ({ value: [r.date, r.tone.score],
            itemStyle: { color: r.tone.score >= 0 ? C.pos : C.neg } })) },
        { name: "Tone 8-week average", type: "line", xAxisIndex: 2, yAxisIndex: 2, showSymbol: false, smooth: true,
          lineStyle: { width: 2, color: C.fg }, itemStyle: { color: C.fg },
          data: issues.map((r, i) => [r.date, Math.round(toneAvg[i] * 100) / 100]) },
        scoreLine("tony", "Tony's advice", s.tony, C.tony, "Tony"),
        scoreLine("fix_1y", "Always fix 1 year", s.fix_1y, C.fix1, "Fix 1y"),
        scoreLine("float", "Always float", s.float, C.float, "Float"),
      ],
    };
  }

  function setQuote(el, text) { el.textContent = text || ""; el.hidden = !text; }
  function showDetails(issue) {
    const $ = (id) => document.getElementById(id);
    $("d-headline").textContent = issue.headline;
    $("d-date").textContent = issue.date;
    $("d-pdf").href = /^https:\/\//.test(issue.pdf_url) ? issue.pdf_url : "#";
    $("d-advice").textContent = adviceLabel(issue.borrower);
    setQuote($("d-advice-quote"), issue.borrower.quote);
    $("d-tone").textContent = signed(issue.tone.score, 0) + " - " + issue.tone.reason;
    setQuote($("d-tone-quote"), issue.tone.quote);
    $("details").hidden = false;
  }

  function renderSummary(loan) {
    const s = scoreSeries(loan);
    const last = (a) => a[a.length - 1][1];
    const diff = last(s.tony) - last(s.fix_1y);
    const tiles = [
      ["OCR", pct(D.ocr_last.rate), "as at " + D.ocr_last.date],
      ["Tony's latest advice", adviceLabel(lastIssue.borrower), "issue " + lastIssue.date],
      ["Latest tone", signed(lastIssue.tone.score, 0), "8-week average " + signed(toneAvg[toneAvg.length - 1], 1)],
      ["Advice score", money(Math.abs(diff)) + (diff <= 0 ? " less" : " more"),
        "interest than always fixing 1 year, on a " + money(loan) + " loan"],
    ];
    document.getElementById("summary").replaceChildren(...tiles.map(([label, value, note]) => {
      const tile = document.createElement("div");
      tile.className = "tile";
      for (const [cls, text] of [["label", label], ["value", value], ["note", note]]) {
        const span = document.createElement("span");
        span.className = cls;
        span.textContent = text;
        tile.append(span);
      }
      return tile;
    }));
  }

  function renderLegend() {
    document.getElementById("advice-legend").replaceChildren(...GROUPS.map((g) => {
      const key = document.createElement("span");
      const swatch = document.createElement("i");
      swatch.style.background = C["g-" + g];
      key.append(swatch, document.createTextNode(GROUP_LABEL[g]));
      return key;
    }));
  }

  // The table view: every issue, newest first. Text only, so it does not depend on colour.
  function renderTable() {
    const rows = issues.slice().reverse().map((r) => {
      const tr = document.createElement("tr");
      const cell = (text, cls) => {
        const td = document.createElement("td");
        td.textContent = text;
        if (cls) td.className = cls;
        tr.append(td);
        return td;
      };
      cell(r.date, "num");
      const head = cell("");
      const link = document.createElement("a");
      link.href = /^https:\/\//.test(r.pdf_url) ? r.pdf_url : "#";
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = r.headline;
      head.append(link);
      cell(adviceLabel(r.borrower));
      cell(signed(r.tone.score, 0), "num");
      const rates = r.lender_min_rates || {};
      cell(["12", "24", "36"].map((t) => (rates[t] ? pct(rates[t]) : "-")).join(" / "), "num");
      return tr;
    });
    document.getElementById("issues-table").replaceChildren(...rows);
  }

  function currentLoan() {
    const value = Number(document.getElementById("loan").value);
    return value > 0 ? value : D.score.loan;
  }

  function draw() {
    C = readColours();
    if (chart) chart.dispose();
    chart = echarts.init(document.getElementById("chart"));
    chart.setOption(buildOption(currentLoan()));
    chart.getZr().on("click", (e) => {
      // Only clicks on a chart (not the legend or slider) open the issue the tooltip shows.
      const onChart = GRID.some((_, i) => chart.containPixel({ gridIndex: i }, [e.offsetX, e.offsetY]));
      if (onChart && pointerIssue) showDetails(pointerIssue);
    });
    renderSummary(currentLoan());
    renderLegend();
  }

  document.getElementById("range").textContent =
    `${issues.length} issues, ${issues[0].date} to ${lastIssue.date}` + (D.quotes ? "" : " (quotes off)");
  document.getElementById("loan").addEventListener("change", () => {
    const s = scoreSeries(currentLoan());
    chart.setOption({ series: [{ id: "tony", data: s.tony }, { id: "fix_1y", data: s.fix_1y }, { id: "float", data: s.float }] });
    renderSummary(currentLoan());
  });
  document.getElementById("close").addEventListener("click", () => { document.getElementById("details").hidden = true; });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") document.getElementById("details").hidden = true; });
  window.addEventListener("resize", () => chart && chart.resize());
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
  renderTable();
  draw();
})();
