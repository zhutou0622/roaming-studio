"use strict";
/**
 * UI functional test without a visible window:
 *   env -u ELECTRON_RUN_AS_NODE npx electron uitest.js
 * Exercises the menu commands / dialogs against the real backend.
 */
const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const { waitReady, freePort, httpJson } = require("./backend");

const ROOT = path.resolve(__dirname, "..");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

app.whenReady().then(async () => {
  const port = await freePort();
  const base = `http://127.0.0.1:${port}`;
  const proc = spawn("python", ["-m", "tap3studio.server", "--port", String(port)], {
    cwd: ROOT, windowsHide: true, stdio: "ignore",
    env: { ...process.env, PYTHONPATH: ROOT },
  });
  let failed = 0;
  const check = (name, ok, extra = "") => {
    console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? "  " + extra : ""}`);
    if (!ok) failed++;
  };
  try {
    await waitReady(base, 30000);
    await httpJson(base + "/api/open", "POST",
      { path: path.join(ROOT, "samples", "demo.tap3") }, 15000);
    const win = new BrowserWindow({ width: 1500, height: 940, show: false, frame: false });
    win.webContents.setBackgroundThrottling(false);
    await win.loadURL(base + "/");
    await sleep(1200);

    const evalJs = (code) => win.webContents.executeJavaScript(code, true);

    const base0 = await evalJs(`(() => ({
      nav: document.querySelectorAll('#navTree .trow').length,
      main: document.querySelectorAll('#mainTree .trow').length,
      dict: document.querySelectorAll('#dictBody .dict-links a').length,
      tab: document.querySelector('#dictTab').textContent,
      sel: document.querySelectorAll('#mainTree .trow.sel').length
    }))()`);
    check("navigation tree rendered", base0.nav > 10, `rows=${base0.nav}`);
    check("main tree rendered", base0.main > 20, `rows=${base0.main}`);
    check("dictionary loaded", base0.dict === 3, `links=${base0.dict} tab=${base0.tab}`);
    check("one selected node", base0.sel === 1, `sel=${base0.sel}`);

    // menu definitions reachable
    const menuCount = await evalJs("document.querySelectorAll('#menubar .menu-top').length");
    check("menu bar has 7 menus", menuCount === 7, `menus=${menuCount}`);

    // open the File menu and inspect items
    const fileItems = await evalJs(`(() => {
      document.querySelectorAll('#menubar .menu-top')[0].dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
      const items = Array.from(document.querySelectorAll('#menuLayer .mi')).map(n => n.textContent.trim());
      closeMenus();
      return items;
    })()`);
    const hasItem = (prefix) => fileItems.some((t) => t.startsWith(prefix));
    check("File menu items", hasItem("Open...") && hasItem("Save As..."),
      `items=${fileItems.join(" | ")}`);

    // validation dialog
    const val = await evalJs(`(async () => {
      await runCommand('validate');
      const rows = document.querySelectorAll('#modalLayer .dlg-table tr').length;
      const title = document.querySelector('#modalLayer .dlg-title').textContent;
      const summary = (document.querySelector('#modalLayer .dlg-body > div')||{}).textContent || '';
      closeModal();
      return { rows, title, summary };
    })()`);
    check("validation dialog opens",
      val.title.includes("Validations") && /record\(s\)/.test(val.summary),
      `rows=${val.rows} summary=${val.summary.trim()}`);

    // dictionary content for the selected field
    const dict = await evalJs(`(() => ({
      values: document.querySelectorAll('#dictBody pre.values').length,
      asn1: (document.querySelector('#dictBody pre.asn1')||{}).textContent || "",
      table: document.querySelectorAll('#dictBody table.vtab tr').length
    }))()`);
    check("dictionary values table", dict.values === 1 && dict.table === 5,
      `values=${dict.values} tableRows=${dict.table}`);
    check("dictionary ASN.1 shows BasicServiceCode", dict.asn1.includes("BasicServiceCode"));

    // find dialog + jump
    const found = await evalJs(`(async () => {
      const r = await api('/api/search?q=imsi&limit=1');
      await jumpToNode(r.hits[0].id);
      return document.querySelector('#mainTree .trow.sel') ? document.querySelector('#mainTree .trow.sel').textContent : '';
    })()`);
    check("jump to node selects it", found.includes("imsi"), `sel=${found.trim()}`);

    // edit value on in-memory document
    const edited = await evalJs(`(async () => {
      const r = await api('/api/search?q=imsi&limit=1');
      await jumpToNode(r.hits[0].id);
      const before = state.selected.value;
      await api('/api/value', 'POST', { id: state.selected.id, value: '262019999999999', mode: 'auto' });
      await refreshAll();
      const r2 = await api('/api/search?q=imsi&limit=1');
      const n = await api('/api/node/' + r2.hits[0].id);
      return { before, after: n.value };
    })()`);
    check("edit value round-trip", edited.after === "262019999999999",
      `${edited.before} -> ${edited.after}`);

    // hex + rules dialogs
    const dialogs = await evalJs(`(async () => {
      await runCommand('hex');
      const hex = (document.querySelector('#modalLayer pre')||{}).textContent?.length || 0;
      closeModal();
      await runCommand('rules');
      const rules = document.querySelectorAll('#modalLayer .dlg-table tr').length;
      closeModal();
      return { hex, rules };
    })()`);
    check("hex dialog", dialogs.hex > 100, `chars=${dialogs.hex}`);
    check("validation rules dialog", dialogs.rules === 8, `rows=${dialogs.rules}`);

    // error path: opening a non-existent file must surface a dialog, not a crash
    const errPath = await evalJs(`(async () => {
      try { await api('/api/open', 'POST', { path: 'Z:/nope.tap3' }); return 'no-error'; }
      catch (e) { return 'error-handled'; }
    })()`);
    check("api errors surface as exceptions", errPath === "error-handled");
  } catch (err) {
    console.error("uitest crashed:", err);
    failed++;
  } finally {
    try { proc.kill(); } catch (_e) { /* ignore */ }
    console.log(failed ? `UITEST FAILED (${failed})` : "UITEST OK");
    setTimeout(() => app.exit(failed ? 1 : 0), 300);
  }
});
