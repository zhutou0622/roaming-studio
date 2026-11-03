"use strict";
/**
 * Full UI regression on the large TAP file:
 *   env -u ELECTRON_RUN_AS_NODE npx electron uitest-large.js [file]
 * Covers context-menu dismissal, dialog closing, find/jump, edit+save, dialogs.
 */
const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const os = require("os");
const { waitReady, freePort, httpJson } = require("./backend");

const ROOT = path.resolve(__dirname, "..");
const FILE = process.argv[2] ||
  path.join("E:/Deepseek工作目录/Romaing Stadio", "CDVGBCCUSAK405097_20240320_135240_POST");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

app.whenReady().then(async () => {
  const port = await freePort();
  const base = `http://127.0.0.1:${port}`;
  const proc = spawn("python", ["-m", "tap3studio.server", "--port", String(port)], {
    cwd: ROOT, windowsHide: true, stdio: "ignore", env: { ...process.env, PYTHONPATH: ROOT },
  });
  let failed = 0;
  const check = (name, ok, extra = "") => {
    console.log(`${ok ? "PASS" : "FAIL"}  ${name}${extra ? "  " + extra : ""}`);
    if (!ok) failed++;
  };
  try {
    await waitReady(base, 30000);
    await httpJson(base + "/api/open", "POST", { path: FILE }, 60000);
    const win = new BrowserWindow({ width: 1680, height: 1004, show: false, frame: false });
    win.webContents.setBackgroundThrottling(false);
    const errors = [];
    win.webContents.on("console-message", (_e, level, message) => {
      // Electron's CSP warning is emitted at warning level; only collect real errors
      if (level >= 2 && !/Security Warning|Content-Security-Policy/i.test(message)) {
        errors.push(message);
      }
    });
    await win.loadURL(base + "/");
    const evalJs = (code) => win.webContents.executeJavaScript(code, true);
    const waitFor = async (expr, timeout = 20000) => {
      const start = Date.now();
      while (Date.now() - start < timeout) {
        if (await evalJs(expr)) return true;
        await sleep(50);
      }
      return false;
    };

    check("tree rendered", await waitFor("document.querySelectorAll('#mainTree .trow').length > 10"));
    const stats = await evalJs(`({nav: document.querySelectorAll('#navTree .trow').length,
       main: document.querySelectorAll('#mainTree .trow').length,
       tab: document.querySelector('#dictTab').textContent})`);
    check("large file loaded", stats.main > 20 && stats.nav >= 400, JSON.stringify(stats));

    /* ---------------- context menu ---------------- */
    await evalJs(`(() => {
      const row = document.querySelector('#mainTree .trow[data-leaf="1"]');
      row.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, clientX: 380, clientY: 320 }));
      return true;
    })()`);
    check("context menu opens", await evalJs("document.querySelector('#ctxLayer').classList.contains('on')"));
    await evalJs(`document.querySelector('#mainTree').dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))`);
    check("context menu closes on outside click",
      !(await evalJs("document.querySelector('#ctxLayer').classList.contains('on')")));

    await evalJs(`(() => {
      document.querySelector('#mainTree .trow').dispatchEvent(
        new MouseEvent('contextmenu', { bubbles: true, clientX: 380, clientY: 320 }));
      return true;
    })()`);
    await evalJs(`document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))`);
    check("context menu closes on Escape",
      !(await evalJs("document.querySelector('#ctxLayer').classList.contains('on')")));

    await evalJs(`(() => {
      document.querySelector('#mainTree .trow[data-leaf="1"]').dispatchEvent(
        new MouseEvent('contextmenu', { bubbles: true, clientX: 380, clientY: 320 }));
      return true;
    })()`);
    await evalJs(`(() => {
      const items = Array.from(document.querySelectorAll('#ctxLayer .mi'));
      const find = items.find(i => i.textContent.includes('Find...'));
      find.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      return true;
    })()`);
    check("context item opens Find dialog",
      await evalJs("document.querySelector('#modalLayer').classList.contains('on') && !document.querySelector('#ctxLayer').classList.contains('on')"));

    /* ---------------- dialogs ---------------- */
    const closeByText = async (text) => evalJs(`(() => {
      const b = Array.from(document.querySelectorAll('#modalLayer .dlg-buttons button'))
        .find(x => x.textContent.trim() === ${JSON.stringify(text)});
      if (!b) return false; b.click(); return true; })()`);
    check("Find Close button works", await closeByText("Close")
      && !(await evalJs("document.querySelector('#modalLayer').classList.contains('on')")));

    await evalJs("runCommand('find')");
    await evalJs(`(() => { const i = document.querySelector('#modalLayer input');
      i.value = 'imsi'; i.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); return true; })()`);
    const found = await waitFor("document.querySelectorAll('#modalLayer .dlg-table tr').length > 1");
    check("Find returns results", found,
      `rows=${await evalJs("document.querySelectorAll('#modalLayer .dlg-table tr').length")}`);
    await evalJs(`(() => { const tr = document.querySelectorAll('#modalLayer .dlg-table tr')[1];
      tr.dispatchEvent(new MouseEvent('click', { bubbles: true })); return true; })()`);
    check("Find result closes dialog and jumps",
      await waitFor("!document.querySelector('#modalLayer').classList.contains('on')"));
    await waitFor("document.querySelector('#dictTab').textContent !== '—'");
    check("jump selects a node", await evalJs("document.querySelectorAll('#mainTree .trow.sel').length === 1"));

    const validate = await evalJs(`(async () => {
      await runCommand('validate');
      const on = document.querySelector('#modalLayer').classList.contains('on');
      const rows = document.querySelectorAll('#modalLayer .dlg-table tr').length;
      return { on, rows };
    })()`);
    check("validation dialog opens", validate.on && validate.rows > 1, `rows=${validate.rows}`);
    check("validation dialog closes", await closeByText("Close")
      && !(await evalJs("document.querySelector('#modalLayer').classList.contains('on')")));

    await evalJs("runCommand('hex')");
    check("hex dialog opens", await evalJs("document.querySelector('#modalLayer').classList.contains('on')"));
    check("hex dialog closes", await closeByText("Close")
      && !(await evalJs("document.querySelector('#modalLayer').classList.contains('on')")));

    await evalJs("runCommand('prefs')");
    check("preferences dialog opens", await evalJs("document.querySelector('#modalLayer').classList.contains('on')"));
    check("preferences closes", await closeByText("Cancel")
      && !(await evalJs("document.querySelector('#modalLayer').classList.contains('on')")));

    /* ---------------- edit + save ---------------- */
    const edit = await evalJs(`(async () => {
      const ev = state.nav.children.find(c => c.kind === 'events');
      await setMainRoot(ev.items[0].id);                 // show a real call record
      const leaf = Array.from(state.rows.entries()).find(
        ([id, r]) => r.dataset.leaf === '1' && r.dataset.name === 'imsi') ||
        Array.from(state.rows.entries()).find(([id, r]) => r.dataset.leaf === '1');
      await selectNode(leaf[0], leaf[1]);
      const before = state.selected.value;
      const rootBefore = state.rootId;
      await runCommand('editValue');
      const ta = document.querySelector('#modalLayer textarea');
      ta.value = '424242';
      const ok = Array.from(document.querySelectorAll('#modalLayer .dlg-buttons button'))
        .find(b => b.textContent.trim() === 'OK');
      ok.click();
      await new Promise(r => setTimeout(r, 1200));
      return { before, after: state.selected.value, rootBefore, rootAfter: state.rootId,
               dialogOpen: document.querySelector('#modalLayer').classList.contains('on') };
    })()`);
    check("edit dialog closes after OK", !edit.dialogOpen, JSON.stringify(edit));
    check("edit applied in memory", await evalJs(`(async () => {
      const n = await api('/api/node/' + state.selected.id); return n.value; })()`) === "424242");

    const afterEdit = await evalJs(`({
      rootStillCed: state.eventIds.has(state.rootId),
      rows: document.querySelectorAll('#mainTree .trow').length,
      modified: document.querySelectorAll('#mainTree .trow.modified').length,
      status: document.querySelector('#statusText').textContent })`);
    check("view stays on the same call",
      afterEdit.rootStillCed && afterEdit.rows > 20 && edit.rootBefore === edit.rootAfter,
      JSON.stringify({ ...afterEdit, rootBefore: edit.rootBefore, rootAfter: edit.rootAfter }));
    check("edited field is highlighted", afterEdit.modified >= 1, `modified=${afterEdit.modified}`);

    /* ---------------- last call jump + clear marks ---------------- */
    const last = await evalJs(`(async () => {
      const ev = state.nav.children.find(c => c.kind === 'events');
      const lastItem = ev.items[ev.items.length - 1];
      await runCommand('gotoLast');
      return { rootId: state.rootId, lastId: lastItem.id,
               navRows: state.navRows.size, rows: document.querySelectorAll('#mainTree .trow').length,
               selectedNav: document.querySelector('#navTree .trow.sel')?.textContent || '',
               status: document.querySelector('#statusText').textContent };
    })()`);
    check("go to last call selects the last CED",
      last.rootId === last.lastId && last.selectedNav.includes('[3883]'), JSON.stringify(last));

    const cleared = await evalJs(`(async () => {
      await runCommand('clearMarks');
      return { modified: document.querySelectorAll('#mainTree .trow.modified').length,
               api: (await api('/api/modified')).count }; })()`);
    check("clear marks removes highlighting", cleared.modified === 0 && cleared.api === 0,
      JSON.stringify(cleared));

    /* ---------------- save naming + statistics ---------------- */
    const noExt = path.join(os.tmpdir(), "roaming_studio_no_extension");
    fs.copyFileSync(FILE, noExt);
    const openedNoExt = await httpJson(base + "/api/open", "POST", { path: noExt }, 60000);
    const savedNoExt = await httpJson(base + "/api/save", "POST", { path: noExt }, 60000);
    check("save keeps the original (extensionless) name",
      openedNoExt.status === 200 && savedNoExt.status === 200 &&
      fs.existsSync(noExt) && !fs.existsSync(noExt + ".tap3"),
      JSON.stringify({ saved: savedNoExt.json && savedNoExt.json.path,
                       extFile: fs.existsSync(noExt + ".tap3") }));
    fs.unlinkSync(noExt);
    await httpJson(base + "/api/open", "POST", { path: FILE }, 60000);
    await evalJs("refreshAll()");

    const stat = await evalJs(`(async () => {
      await runCommand('statistics');
      const title = document.querySelector('#modalLayer .dlg-title').textContent;
      const text = document.querySelector('#modalLayer .dlg-body').innerText;
      const rows = document.querySelectorAll('#modalLayer .dlg-table tr').length;
      const close = Array.from(document.querySelectorAll('#modalLayer .dlg-buttons button'))
        .find(b => b.textContent.trim() === 'Close');
      close.click();
      return { title, text, rows, closed: !document.querySelector('#modalLayer').classList.contains('on') };
    })()`);
    check("file statistics dialog", stat.title.includes("File Statistics") && stat.rows >= 4 && stat.closed,
      `rows=${stat.rows}`);
    check("statistics separates records and charge",
      /records: 3883/.test(stat.text) && /USD/.test(stat.text) &&
      /152\.49912 USD|152\.49912/.test(stat.text),
      stat.text.split("\n").slice(0, 3).join(" | "));

    const statusBar = await evalJs("document.querySelector('#statusInfo').textContent");
    check("status bar shows records and charge separately",
      /records: 3883/.test(statusBar) && /charge: .*USD/.test(statusBar) &&
      !/records: 3883 USD/.test(statusBar), statusBar);

    /* ---------------- schema-driven insertion ---------------- */
    const ins = await evalJs(`(async () => {
      const ev = state.nav.children.find(c => c.kind === 'events');
      await setMainRoot(ev.items[0].id);
      const row = Array.from(state.rows.entries()).find(([id, r]) => r.dataset.name === 'ChargeDetail');
      await selectNode(row[0], row[1]);
      await runCommand('insertChild');
      const dlg = document.querySelector('#modalLayer');
      const open = dlg.classList.contains('on');
      const sel = dlg.querySelector('select');
      const options = Array.from(sel.options);
      const usable = options.filter(o => !o.disabled);
      let inserted = null;
      if (usable.length) {
        sel.value = usable[0].value;
        sel.onchange();
        const val = dlg.querySelector('input[type=text]');
        if (!val.disabled) val.value = '20240101120000';
        Array.from(dlg.querySelectorAll('.dlg-buttons button'))
          .find(b => b.textContent.trim() === 'Insert').click();
        await new Promise(r => setTimeout(r, 1500));
        inserted = { modified: document.querySelectorAll('#mainTree .trow.modified').length,
                     modal: document.querySelector('#modalLayer').classList.contains('on'),
                     status: document.querySelector('#statusText').textContent };
      } else {
        Array.from(dlg.querySelectorAll('.dlg-buttons button'))
          .find(b => b.textContent.trim() === 'Cancel').click();
      }
      return { open, options: options.length, usable: usable.length, inserted };
    })()`);
    check("insert dialog lists schema fields", ins.open && ins.options >= 4,
      JSON.stringify({ open: ins.open, options: ins.options }));
    check("insert child works and is highlighted",
      !ins.inserted || (ins.inserted.modified >= 1 && !ins.inserted.modal),
      JSON.stringify(ins.inserted || {}));

    const tmp = path.join(os.tmpdir(), "roaming_studio_uitest_large.tap3");
    const save = await evalJs(`(async () => {
      const r = await api('/api/save', 'POST', { path: ${JSON.stringify(tmp)} });
      return r; })()`);
    check("save writes file", fs.existsSync(tmp) && save.size > 1000000, `size=${save.size}`);
    const reopened = await httpJson(base + "/api/open", "POST", { path: tmp }, 60000);
    check("saved file reopens", reopened.status === 200 &&
      reopened.json.stats.events === 3883 && reopened.json.header.release === 12);
    fs.unlinkSync(tmp);

    await httpJson(base + "/api/open", "POST", { path: FILE }, 60000);
    check("no renderer errors", errors.length === 0, errors.slice(0, 3).join(" | "));
  } catch (err) {
    console.error("uitest-large crashed:", err);
    failed++;
  } finally {
    try { proc.kill(); } catch (_e) { /* ignore */ }
    console.log(failed ? `UITEST-LARGE FAILED (${failed})` : "UITEST-LARGE OK");
    setTimeout(() => app.exit(failed ? 1 : 0), 300);
  }
});
