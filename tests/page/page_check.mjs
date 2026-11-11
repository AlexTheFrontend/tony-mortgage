// The page checks: drive a headless browser over the DevTools protocol and check the page.
// Run them with tests/page/run.mjs, which starts the browser.
import { writeFileSync } from "node:fs";

export const XSS_HEADLINE = '<b>Test</b> & "quotes"'; // the first headline on the escaping page (check 10)

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const DAY_MS = 86400000;

// Returns one line per check: "PASS <name> - <info>" or "FAIL <name> - <info>".
export async function checkPage({ port, pageUrl, xssUrl, outDir, tz }) {
  let target;
  for (let i = 0; i < 40 && !target; i++) {
    try { target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" })).json(); }
    catch { await sleep(250); }
  }
  if (!target) throw new Error(`no DevTools target on port ${port}`);
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  let id = 0;
  const pending = new Map();
  const errors = [];
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); return; }
    if (m.method === "Runtime.exceptionThrown") errors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
    if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") errors.push(m.params.args.map((a) => a.value ?? a.description).join(" "));
    if (m.method === "Log.entryAdded" && m.params.entry.level === "error") errors.push(m.params.entry.text);
  };
  const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
  const ev = async (expression) => {
    const r = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    const fail = r.result.exceptionDetails;
    if (fail) throw new Error((fail.exception?.description || fail.text).split("\n")[0]);
    return r.result.result.value;
  };
  const shot = async (name) => {
    const r = await send("Page.captureScreenshot", { format: "png" });
    writeFileSync(`${outDir}/${name}.png`, Buffer.from(r.result.data, "base64"));
  };
  const results = [];
  const check = (name, ok, info = "") => results.push(`${ok ? "PASS" : "FAIL"} ${name}${info ? " - " + info : ""}`);
  const CHART = "echarts.getInstanceByDom(document.getElementById('chart'))";
  const pointFor = (day, value, grid = 0) => ev(`(() => { const p = ${CHART}.convertToPixel({gridIndex: ${grid}}, ['${day}', ${value}]);
    const r = document.getElementById('chart').getBoundingClientRect(); return [p[0] + r.left, p[1] + r.top]; })()`);
  const mouse = async (type, [x, y]) => send("Input.dispatchMouseEvent", { type, x, y, button: "left", clickCount: 1 });
  const key = async (k, code) => {
    await send("Input.dispatchKeyEvent", { type: "keyDown", key: k, code: k, windowsVirtualKeyCode: code });
    await send("Input.dispatchKeyEvent", { type: "keyUp", key: k, code: k, windowsVirtualKeyCode: code });
  };
  const tooltip = () => ev(`(() => { const t = [...document.querySelectorAll('#chart div')].find((d) => d.innerHTML.includes('Click for details'));
    return t ? { text: t.innerText, html: t.innerHTML, visible: getComputedStyle(t).display !== 'none' && t.style.opacity !== '0' } : null; })()`);

  // A broken page can stop the checks early; that is a FAIL with the page errors, not a crash.
  try {
    await send("Runtime.enable"); await send("Log.enable"); await send("Page.enable");
    await send("Emulation.setDeviceMetricsOverride", { width: 1400, height: 1300, deviceScaleFactor: 1, mobile: false });
    await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }] });
    if (tz) await send("Emulation.setTimezoneOverride", { timezoneId: tz });
    await send("Page.navigate", { url: pageUrl });
    await sleep(2500);

    const tiles = await ev(`[...document.querySelectorAll('#summary .tile')].map((t) => t.innerText.replace(/\\n/g, ' / '))`);
    check("1 summary has 4 tiles", tiles.length === 4, tiles.join(" || "));
    const series = await ev(`${CHART}.getOption().series.map((s) => s.name + ':' + (s.data ? s.data.length : 0))`);
    check("2 rates chart series", ["OCR", "OCR change", "Mortgage 1y", "Mortgage 2y", "Mortgage 3y", "Swap 1y", "Swap 3y", "Tony's lowest lender rates"].every((n) => series.some((s) => s.startsWith(n + ":"))), series.join(", "));
    const legend = await ev(`[...document.querySelectorAll('#advice-legend span')].map((s) => s.textContent + '=' + s.firstChild.style.background)`);
    check("3 advice legend has 8 groups with colours", legend.length === 8 && legend.every((l) => /rgb/.test(l)), legend.join(", "));

    const p = await pointFor("2024-06-21", 4);
    await mouse("mouseMoved", p); await sleep(700);
    const tip = await tooltip();
    check("4 hover tooltip", tip && tip.visible && /Issue 2024-06-20/.test(tip.text) && /OCR: /.test(tip.text) && /Swap: /.test(tip.text), tip ? tip.text.replace(/\n/g, " / ") : "no tooltip");
    await shot("hover");

    await mouse("mousePressed", p); await mouse("mouseReleased", p); await sleep(300);
    const det = await ev(`({ hidden: document.getElementById('details').hidden, date: document.getElementById('d-date').textContent,
      head: document.getElementById('d-headline').textContent, pdf: document.getElementById('d-pdf').href,
      advice: document.getElementById('d-advice').textContent, quote: document.getElementById('d-advice-quote').textContent.slice(0, 60),
      quoteHidden: document.getElementById('d-advice-quote').hidden, quotesOn: window.TONY_DATA.quotes,
      tone: document.getElementById('d-tone').textContent.slice(0, 60) })`);
    // With quotes off (the public build) the quote box must be empty and hidden.
    const quoteOk = det.quotesOn ? !!det.quote && !det.quoteHidden : det.quote === "" && det.quoteHidden;
    check("5 click opens details", !det.hidden && det.date === "2024-06-20" && det.pdf.startsWith("https://") && det.head && quoteOk, JSON.stringify(det));
    await shot("details");
    await key("Escape", 27); await sleep(200);
    check("5 Escape closes details", await ev(`document.getElementById('details').hidden`));

    // The four x-axes can differ by a few pixels (at most 3 days); an axis that is not linked differs by years.
    const ext = await ev(`(() => { const c = ${CHART}; c.dispatchAction({ type: 'dataZoom', dataZoomIndex: 0, start: 50, end: 100 });
      return [0, 1, 2, 3].map((i) => c.getModel().getComponent('xAxis', i).axis.scale.getExtent()); })()`);
    const spread = (k) => Math.max(...ext.map((e) => e[k])) - Math.min(...ext.map((e) => e[k]));
    const isoDay = (v) => new Date(v).toISOString().slice(0, 10);
    check("6 zoom moves all four charts", spread(0) <= 3 * DAY_MS && spread(1) <= 3 * DAY_MS && !isoDay(ext[0][0]).startsWith("2022"),
      ext.map((e) => e.map(isoDay).join("..")).join(" / "));
    await shot("zoomed");
    await ev(`${CHART}.dispatchAction({ type: 'dataZoom', dataZoomIndex: 0, start: 0, end: 100 })`);

    const lastTony = `(() => { const s = ${CHART}.getOption().series.find((s) => s.id === 'tony'); return s.data[s.data.length - 1][1]; })()`;
    const before = { tile: await ev(`document.querySelectorAll('#summary .tile')[3].innerText`), tony: await ev(lastTony) };
    await ev(`(() => { const i = document.getElementById('loan'); i.value = '1000000'; i.dispatchEvent(new Event('change')); })()`);
    await sleep(300);
    const after = { tile: await ev(`document.querySelectorAll('#summary .tile')[3].innerText`), tony: await ev(lastTony) };
    check("7 loan change updates score", /\$1,000,000/.test(after.tile) && Math.abs(after.tony - 2 * before.tony) <= 2, `${before.tony} -> ${after.tony}; ${after.tile.replace(/\n/g, " / ")}`);

    await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "dark" }] });
    await sleep(1000);
    const dark = await ev(`({ bg: getComputedStyle(document.body).backgroundColor, title: ${CHART}.getOption().title[0].textStyle.color,
      loanKept: ${CHART}.getOption().series.find((s) => s.id === 'tony').data.slice(-1)[0][1] })`);
    check("8 dark mode redraws", dark.bg === "rgb(26, 26, 25)" && dark.title === "#ffffff" && dark.loanKept === after.tony, JSON.stringify(dark));
    await shot("dark");

    const rows = await ev(`document.querySelectorAll('#issues-table tr').length`);
    const issues = await ev(`window.TONY_DATA.issues.length`);
    check("extra: table view has one row per issue", rows === issues, `${rows} rows, ${issues} issues`);

    // Date checks: the hover and the click must use the day under the pointer, in local time.
    const sample = await ev(`window.TONY_DATA.issues.filter((r, i, a) => i % 15 === 0 || i === a.length - 1).map((r) => r.date)`);
    const hoverBad = [], clickBad = [];
    for (const day of sample) {
      const pt = await pointFor(day, 0, 2);
      await mouse("mouseMoved", pt); await sleep(250);
      const t = await tooltip();
      const lines = t ? t.text.split("\n") : [];
      if (!(lines[0] === day && (lines[1] || "").startsWith(`Issue ${day}:`))) hoverBad.push(`${day}->${lines.slice(0, 2).join(" | ")}`);
      await mouse("mousePressed", pt); await mouse("mouseReleased", pt); await sleep(150);
      const opened = await ev(`document.getElementById('details').hidden ? null : document.getElementById('d-date').textContent`);
      if (opened !== day) clickBad.push(`${day}->${opened}`);
      await key("Escape", 27); await sleep(100);
    }
    check("11 hover on an issue bar shows that issue", hoverBad.length === 0, `${sample.length - hoverBad.length}/${sample.length} ok; ${hoverBad.slice(0, 3).join("; ")}`);
    check("12 click on an issue bar opens that issue", clickBad.length === 0, `${sample.length - clickBad.length}/${sample.length} ok; ${clickBad.slice(0, 3).join("; ")}`);
    const changes = await ev(`window.TONY_DATA.ocr.filter((o) => o.change !== null)`);
    const ocrBad = [];
    for (const o of changes) {
      await mouse("mouseMoved", await pointFor(o.date, o.rate, 0)); await sleep(250);
      const t = await tooltip();
      if (!t || !t.text.includes(`OCR: ${o.rate.toFixed(2)}%`)) ocrBad.push(`${o.date}->${t ? (t.text.match(/OCR: [0-9.]+%/) || ["none"])[0] : "no tooltip"}`);
    }
    check("13 hover on an OCR change day shows the new OCR", ocrBad.length === 0, `${changes.length - ocrBad.length}/${changes.length} ok; ${ocrBad.slice(0, 3).join("; ")}`);

    // The advice strip (grid 1): hover and click inside a week must show that week's issue and a real date.
    const stripBad = [], stripClickBad = [];
    for (const day of sample) {
      const inside = await ev(`(() => { const d = new Date('${day}T12:00'); d.setDate(d.getDate() + 2); return d.getTime(); })()`);
      const pt = await ev(`(() => { const p = ${CHART}.convertToPixel({gridIndex: 1}, [${inside}, 0]);
        const r = document.getElementById('chart').getBoundingClientRect(); return [p[0] + r.left, p[1] + r.top]; })()`);
      await mouse("mouseMoved", pt); await sleep(250);
      const t = await tooltip();
      const lines = t ? t.text.split("\n") : [];
      if (!(/^\d{4}-\d{2}-\d{2}$/.test(lines[0] || "") && (lines[1] || "").startsWith(`Issue ${day}:`))) stripBad.push(`${day}->${lines.slice(0, 2).join(" | ")}`);
      await mouse("mousePressed", pt); await mouse("mouseReleased", pt); await sleep(150);
      const opened = await ev(`document.getElementById('details').hidden ? null : document.getElementById('d-date').textContent`);
      if (opened !== day) stripClickBad.push(`${day}->${opened}`);
      await key("Escape", 27); await sleep(100);
    }
    check("14 hover on the advice strip shows a date and that week's issue", stripBad.length === 0, `${sample.length - stripBad.length}/${sample.length} ok; ${stripBad.slice(0, 3).join("; ")}`);
    check("15 click on the advice strip opens that week's issue", stripClickBad.length === 0, `${sample.length - stripClickBad.length}/${sample.length} ok; ${stripClickBad.slice(0, 3).join("; ")}`);

    // Table of totals by start month (at the bottom). The loan is 1,000,000 here (check 7), so values must be scaled.
    const bs = await ev(`(() => {
      const D = window.TONY_DATA, rows = [...document.querySelectorAll('#by-start-table tr')];
      const loan = Number(document.getElementById('loan').value), r = D.by_start ? D.by_start[0] : null;
      const money = (v) => '$' + Math.round(v).toLocaleString('en-NZ');
      return { n: rows.length, want: D.by_start ? D.by_start.length : -1,
        cells: rows[0] ? [...rows[0].cells].map((c) => c.textContent) : [],
        start: r && r.start, fix1y: r && money(r.totals['1y'] * loan / D.score.loan),
        note: (document.getElementById('by-start-note') || {}).textContent || '', loanText: money(loan) }; })()`);
    check("16 table of totals by start month",
      bs.want > 0 && bs.n === bs.want && bs.cells[0] === bs.start && /^(Fix|Always|Tony)/.test(bs.cells[1] || "")
        && (bs.cells[2] || "").startsWith(bs.fix1y) && bs.note.includes(bs.loanText),
      `${bs.n}/${bs.want} rows; first row: ${bs.cells.join(" | ")}; want 1y ${bs.fix1y}; note: ${bs.note.slice(0, 90)}`);

    // Green tick next to Tony's advice when it cost less than both "Fix 1 year" and "Always float".
    const ticks = await ev(`(() => {
      const D = window.TONY_DATA, k = Number(document.getElementById('loan').value) / D.score.loan;
      const rows = [...document.querySelectorAll('#by-start-table tr')];
      const bad = [];
      let want = 0;
      D.by_start.forEach((r, i) => {
        const t = (key) => Math.round(r.totals[key] * k);
        const expected = t('tony') < Math.min(t('1y'), t('float'));
        if (expected) want++;
        const has = !!(rows[i] && rows[i].cells[3] && rows[i].cells[3].querySelector('.tick'));
        if (has !== expected) bad.push(r.start + (expected ? ' missing' : ' extra'));
      });
      const key = document.getElementById('by-start-key');
      return { want, bad, key: key ? key.textContent : '' }; })()`);
    check("17 green tick when Tony beat fix 1 year and float", ticks.bad.length === 0 && ticks.want > 0 && ticks.key.includes("✓"),
      `${ticks.want} rows want a tick; wrong: ${ticks.bad.slice(0, 4).join(", ") || "none"}; key: ${ticks.key}`);

    // Plain verdict in the last column: Good / OK / Not good, against "Fix 1 year" and "Always float".
    const verdicts = await ev(`(() => {
      const D = window.TONY_DATA, k = Number(document.getElementById('loan').value) / D.score.loan;
      const rows = [...document.querySelectorAll('#by-start-table tr')];
      const bad = [], count = { good: 0, ok: 0, bad: 0 };
      const word = { good: 'Good', ok: 'OK', bad: 'Not good' };
      D.by_start.forEach((r, i) => {
        const t = (key) => Math.round(r.totals[key] * k);
        const lo = Math.min(t('1y'), t('float')), hi = Math.max(t('1y'), t('float'));
        const want = t('tony') < lo ? 'good' : t('tony') > hi ? 'bad' : 'ok';
        count[want]++;
        const cell = rows[i] && rows[i].cells[5];
        const label = cell && cell.querySelector('.verdict-word');
        if (!label || label.textContent !== word[want] || cell.dataset.verdict !== want) bad.push(r.start + ' want ' + want);
      });
      const sum = document.getElementById('by-start-summary');
      return { bad, count, total: D.by_start.length, sum: sum ? sum.textContent : '' }; })()`);
    check("21 plain verdict for Tony's advice in each row, with a summary",
      verdicts.bad.length === 0 && verdicts.sum.includes(`good in ${verdicts.count.good} of ${verdicts.total}`)
        && verdicts.sum.includes(`not good in ${verdicts.count.bad}`),
      `${JSON.stringify(verdicts.count)}; wrong: ${verdicts.bad.slice(0, 4).join(", ") || "none"}; summary: ${verdicts.sum}`);

    // Quarterly table: Tony's advice at the start, the best fixed way afterwards, and the difference.
    const quarters = await ev(`(() => {
      const D = window.TONY_DATA, k = Number(document.getElementById('loan').value) / D.score.loan;
      const money = (v) => '$' + Math.round(v).toLocaleString('en-NZ');
      const rows = [...document.querySelectorAll('#by-quarter-table tr')];
      const want = D.by_start.filter((r) => Number(r.start.slice(5)) % 3 === 1);
      const steps = [0, 6, 12, 18, 24, 36], termOf = { float: 0, '6m': 6, '1y': 12, '18m': 18, '2y': 24, '3y': 36 };
      const bad = [];
      want.forEach((r, i) => {
        const fixed = Object.keys(termOf).map((key) => [key, Math.round(r.totals[key] * k)]);
        const best = fixed.reduce((a, b) => (b[1] < a[1] ? b : a));
        let terms = [12];
        for (const issue of D.issues) {
          if (issue.date.slice(0, 7) > r.start) break;
          const b = issue.borrower;
          if (b.group === 'none') continue;
          terms = b.group === 'float' ? [0] : b.group === '3y_plus' ? [36]
            : b.group === 'mix' ? b.terms_months.map((t) => Math.min(t, 36)) : [Math.min(b.terms_months[0], 36)];
        }
        const bestStep = steps.indexOf(termOf[best[0]]);
        const gap = Math.min(...terms.map((t) => Math.abs(steps.indexOf(t) - bestStep)));
        const right = terms.length === 1 && gap === 0 ? 'Yes' : gap <= 1 ? 'Close' : 'No';
        const c = rows[i] ? [...rows[i].cells].map((x) => x.textContent) : [];
        const extra = Math.round(r.totals.tony * k) - best[1];
        if (c[0] !== r.start || !(c[2] || '').includes(money(best[1])) || !(c[3] || '').includes(money(Math.abs(extra)))
          || (c[4] || '').replace(/^[✓✗]/, '') !== right) bad.push(r.start + ': ' + c.join(' | '));
      });
      return { n: rows.length, want: want.length, bad }; })()`);
    check("22 quarterly table of best decisions", quarters.want > 0 && quarters.n === quarters.want && quarters.bad.length === 0,
      `${quarters.n}/${quarters.want} rows; wrong: ${quarters.bad.slice(0, 2).join("; ") || "none"}`);

    const pageErrors = errors.splice(0);
    check("9 no console errors on the main page", pageErrors.length === 0, pageErrors.join(" | "));

    await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: "light" }] });
    await send("Page.navigate", { url: xssUrl });
    await sleep(2500);
    const first = await ev(`window.TONY_DATA.issues[0].date`);
    const p1 = await pointFor(first, 4);
    await mouse("mouseMoved", [p1[0] + 3, p1[1]]); await sleep(700);
    const xtip = await tooltip();
    await mouse("mousePressed", [p1[0] + 3, p1[1]]); await mouse("mouseReleased", [p1[0] + 3, p1[1]]); await sleep(300);
    const xdet = await ev(`({ head: document.getElementById('d-headline').textContent, bold: document.querySelectorAll('#details b, #chart b').length,
      table: [...document.querySelectorAll('#issues-table a')].pop().textContent })`);
    check("10 markup in a headline shows as plain text",
      xtip && xtip.html.includes("&lt;b&gt;Test&lt;/b&gt;") && xdet.head === XSS_HEADLINE && xdet.table === XSS_HEADLINE,
      `tooltip: ${xtip ? xtip.text.split("\n")[1] : "none"}; details: ${xdet.head}; table: ${xdet.table}; tooltip has escaped markup: ${xtip && xtip.html.includes("&lt;b&gt;")}`);
    check("9 no console errors on the escaping page", errors.length === 0, errors.join(" | "));

  } catch (err) {
    check("the checks stopped early", false, `${err.message}; page errors: ${errors.join(" | ") || "none"}`);
  }
  ws.close();
  return results;
}
