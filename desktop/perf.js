"use strict";
/**
 * UI performance probe for a large TAP file:
 *   env -u ELECTRON_RUN_AS_NODE npx electron perf.js "C:\path\file"
 */
const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const { waitReady, freePort, httpJson } = require("./backend");

const ROOT = path.resolve(__dirname, "..");
const FILE = process.argv[2] || path.join("E:/Deepseek工作目录/Romaing Stadio", "CDVGBCCUSAK405097_20240320_135240_POST");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

app.whenReady().then(async () => {
  const port = await freePort();
  const base = `http://127.0.0.1:${port}`;
  const proc = spawn("python", ["-m", "tap3studio.server", "--port", String(port)], {
    cwd: ROOT, windowsHide: true, stdio: "ignore", env: { ...process.env, PYTHONPATH: ROOT },
  });
  try {
    await waitReady(base, 30000);
    const tOpen = Date.now();
    const opened = await httpJson(base + "/api/open", "POST", { path: FILE }, 60000);
    const openMs = Date.now() - tOpen;
    console.log("open response:", opened.status, Object.keys(opened.json || {}));
    if (opened.status !== 200) throw new Error(JSON.stringify(opened.json));
    console.log(`open (server)      : ${openMs} ms  events=${opened.json.stats.events}`);

    const win = new BrowserWindow({ width: 1680, height: 1004, show: false, frame: false });
    win.webContents.setBackgroundThrottling(false);
    const t0 = Date.now();
    await win.loadURL(base + "/");
    win.webContents.on("console-message", (_e, level, message) => {
      if (level >= 2 || /error/i.test(message)) console.log("[renderer]", message);
    });
    const evalJs = (code) => win.webContents.executeJavaScript(code, true);
    const waitFor = async (expr, timeout = 30000) => {
      const start = Date.now();
      while (Date.now() - start < timeout) {
        if (await evalJs(expr)) return Date.now() - start;
        await sleep(50);
      }
      return -1;
    };
    const bootMs = await waitFor("document.querySelectorAll('#mainTree .trow').length > 0");
    console.log(`UI boot to tree     : ${bootMs} ms (total ${Date.now() - t0} ms)`);
    console.log("nav rows            :", await evalJs("document.querySelectorAll('#navTree .trow').length"));
    console.log("main rows           :", await evalJs("document.querySelectorAll('#mainTree .trow').length"));
    await waitFor("document.querySelector('#dictTab').textContent !== '—'", 8000);
    console.log("dict tab            :", await evalJs("document.querySelector('#dictTab').textContent"));

    const timing = async (label, expr) => {
      const ms = await evalJs(`(async () => { const t = performance.now(); ${expr}; return Math.round(performance.now() - t); })()`);
      const rows = await evalJs("document.querySelectorAll('#mainTree .trow').length");
      console.log(`${label}: ${ms} ms  (rows=${rows})`);
      return ms;
    };

    const ids = await evalJs(`(() => {
      const ev = state.nav.children.find(c => c.kind === 'events');
      const leaf = Array.from(state.rows.entries()).find(([id, row]) => row.dataset.leaf === '1');
      return { root: state.nav.root.id, list: ev.id, firstCed: ev.items[0].id,
               leafId: leaf ? leaf[0] : null };
    })()`);

    await timing("open event list (3883)", `await setMainRoot(${ids.list})`);
    await timing("open DataInterChange    ", `await setMainRoot(${ids.root})`);
    await timing("open CED #1 (45 nodes)  ", `await setMainRoot(${ids.firstCed})`);
    await timing("select leaf + dictionary",
      `const row = state.rows.get(${ids.leafId}); if (row) await selectNode(${ids.leafId}, row)`);

    // validate latency
    const val = await evalJs(`(async () => {
      const t = performance.now();
      const r = await api('/api/validate');
      return { ms: Math.round(performance.now() - t), errors: r.errors, warnings: r.warnings };
    })()`);
    console.log(`validate (api)      : ${val.ms} ms  errors=${val.errors} warnings=${val.warnings}`);
  } catch (err) {
    console.error("perf probe failed:", err);
    process.exitCode = 1;
  } finally {
    try { proc.kill(); } catch (_e) { /* ignore */ }
    setTimeout(() => app.exit(0), 300);
  }
});
