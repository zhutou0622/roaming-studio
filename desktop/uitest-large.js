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

    /* ---------------- BCD / recEntity display ---------------- */
    const calling = await evalJs(`(async () => {
      const r = await api('/api/search?q=callingNumber&limit=1');
      await jumpToNode(r.hits[0].id);
      const row = document.querySelector('#mainTree .trow.sel');
      return row ? row.textContent : '';
    })()`);
    check("callingNumber is decoded as digits", /callingNumber: \d+/.test(calling), calling.trim());

    await evalJs(`(async () => {
      const ev = state.nav.children.find(c => c.kind === 'events');
      await setMainRoot(ev.items[0].id);
      return true; })()`);
    const recRow = await evalJs(`(() => {
      const row = Array.from(state.rows.entries())
        .find(([id, r]) => r.dataset.name === 'recEntityCode' || r.dataset.type === 'RecEntityCode');
      return row ? row[1].textContent : '';
    })()`);
    check("recEntityCode shows the resolved entity", /\(MSC|SMSC|GGSN|SGSN/.test(recRow), recRow.trim());

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

    /* ---------------- validation profile ---------------- */
    const prof = await evalJs(`(async () => {
      await runCommand('profile');
      const dlg = document.querySelector('#modalLayer');
      const open = dlg.classList.contains('on');
      const selectCount = dlg.querySelectorAll('select').length;
      const rows = Array.from(dlg.querySelectorAll('table tr'));
      const aud = rows.find(r => r.textContent.includes('AUD-004'));
      const sel = aud ? aud.querySelector('select') : null;
      if (sel) { sel.value = 'off'; }
      const apply = Array.from(dlg.querySelectorAll('.dlg-buttons button'))
        .find(b => b.textContent.trim() === 'Apply & Validate');
      if (apply) apply.click();
      await new Promise(r => setTimeout(r, 1500));
      const title = document.querySelector('#modalLayer .dlg-title').textContent;
      const summary = (document.querySelector('#modalLayer .dlg-body > div') || {}).textContent || '';
      const hasAud = /AUD-004/.test(document.querySelector('#modalLayer .dlg-table').innerText);
      const close = Array.from(document.querySelectorAll('#modalLayer .dlg-buttons button'))
        .find(b => b.textContent.trim() === 'Close');
      if (close) close.click();
      return { open, selects: selectCount, title, summary, hasAud };
    })()`);
    check("validation profile dialog", prof.open && prof.selects >= 30, JSON.stringify({open: prof.open, selects: prof.selects}));
    check("profile override suppresses AUD-004",
      prof.title.includes("Validations") && /profile: custom/.test(prof.summary) && !prof.hasAud,
      prof.summary.slice(0, 120));

    // reset the profile for the remaining tests
    await evalJs(`(async () => {
      await runCommand('profile');
      const reset = Array.from(document.querySelectorAll('#modalLayer .dlg-buttons button'))
        .find(b => b.textContent.trim() === 'Reset');
      if (reset) reset.click();
      return true; })()`);

    const statusBar = await evalJs("document.querySelector('#statusInfo').textContent");
    check("status bar shows records and charge separately",
      /records: 3883/.test(statusBar) && /charge: .*USD/.test(statusBar) &&
      !/records: 3883 USD/.test(statusBar), statusBar);

    /* ---------------- batch scan dialog ---------------- */
    const batchDir = path.join(os.tmpdir(), "roaming_studio_batch_" + Date.now());
    fs.mkdirSync(batchDir, { recursive: true });
    fs.copyFileSync(path.join(ROOT, "samples", "demo.tap3"), path.join(batchDir, "demo.tap3"));
    fs.writeFileSync(path.join(batchDir, "broken.bin"), Buffer.from([0x61, 0x82, 0x10, 0x00]));
    const batchCsv = path.join(batchDir, "scan.csv");
    const batchUi = await evalJs(`(async () => {
      await runCommand('batchScan');
      const dlg = document.querySelector('#modalLayer');
      const open = dlg.classList.contains('on');
      const inputs = dlg.querySelectorAll('input[type=text]');
      inputs[0].value = ${JSON.stringify(batchDir)};
      inputs[2].value = ${JSON.stringify(batchCsv)};
      Array.from(dlg.querySelectorAll('.dlg-buttons button'))
        .find(b => b.textContent.trim() === 'Scan').click();
      await new Promise(r => setTimeout(r, 1500));
      const rows = dlg.querySelectorAll('table tr').length;
      const summary = Array.from(dlg.querySelectorAll('.dlg-body div.muted'))
        .map(n => n.textContent).join(' | ');
      Array.from(dlg.querySelectorAll('.dlg-buttons button'))
        .find(b => b.textContent.trim() === 'Export CSV').click();
      await new Promise(r => setTimeout(r, 1200));
      Array.from(dlg.querySelectorAll('.dlg-buttons button'))
        .find(b => b.textContent.trim() === 'Close').click();
      return { open, rows, summary };
    })()`);
    check("batch scan dialog", batchUi.open && batchUi.rows >= 3, JSON.stringify(batchUi));
    check("batch scan reports status", /2 file\(s\)/.test(batchUi.summary), batchUi.summary);
    check("batch CSV export", fs.existsSync(batchCsv) && fs.statSync(batchCsv).size > 20,
      fs.existsSync(batchCsv) ? `size=${fs.statSync(batchCsv).size}` : "missing");
    try { fs.rmSync(batchDir, { recursive: true, force: true }); } catch (_e) { /* ignore */ }

    /* ---------------- RAP return generation ---------------- */
    const rapPath = path.join(os.tmpdir(), "roaming_studio_uitest_return.rap");
    try { fs.unlinkSync(rapPath); } catch (_e) { /* absent */ }
    const rapUi = await evalJs(`(async () => {
      await runCommand('genRap');
      const dlg = document.querySelector('#modalLayer');
      const open = dlg.classList.contains('on');
      const inp = dlg.querySelector('input[type=text]');
      inp.value = ${JSON.stringify(rapPath)};
      const inc = dlg.querySelector('input[type=checkbox]');
      if (inc) inc.checked = true;
      Array.from(dlg.querySelectorAll('.dlg-buttons button'))
        .find(b => b.textContent.trim() === 'Generate').click();
      await new Promise(r => setTimeout(r, 1800));
      const body = dlg.innerText;
      Array.from(dlg.querySelectorAll('.dlg-buttons button'))
        .find(b => b.textContent.trim() === 'Close').click();
      return { open, body };
    })()`);
    check("RAP dialog opens", rapUi.open, String(rapUi.body).slice(0, 80));
    check("RAP file written", fs.existsSync(rapPath) && fs.statSync(rapPath).size > 100,
      fs.existsSync(rapPath) ? `size=${fs.statSync(rapPath).size}` : "missing");
    const rapBack = await httpJson(base + "/api/open", "POST", { path: rapPath }, 30000);
    check("generated RAP opens as RAP1",
      rapBack.status === 200 && /RAP1/.test(rapBack.json.header.releaseLabel),
      rapBack.json && rapBack.json.header && rapBack.json.header.releaseLabel);
    try { fs.unlinkSync(rapPath); } catch (_e) { /* ignore */ }
    await httpJson(base + "/api/open", "POST", { path: FILE }, 60000);
    await evalJs("refreshAll()");

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
