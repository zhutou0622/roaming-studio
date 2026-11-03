"use strict";
/**
 * Capture popup/dialog states for visual review (development helper):
 *   env -u ELECTRON_RUN_AS_NODE npx electron shot-dialogs.js [file]
 * Writes ../docs/ui-ctx-menu.png and ../docs/ui-find-dialog.png
 */
const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
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
  try {
    await waitReady(base, 30000);
    await httpJson(base + "/api/open", "POST", { path: FILE }, 60000);
    const win = new BrowserWindow({ width: 1680, height: 1004, show: false, frame: false });
    win.webContents.setBackgroundThrottling(false);
    await win.loadURL(base + "/");
    win.showInactive();
    await sleep(1200);
    const evalJs = (code) => win.webContents.executeJavaScript(code, true);
    const shoot = async (name) => {
      await sleep(250);
      const img = await win.webContents.capturePage();
      const out = path.join(ROOT, "docs", name);
      fs.writeFileSync(out, img.toPNG());
      console.log("wrote", out);
    };

    await evalJs(`(() => {
      const row = document.querySelector('#mainTree .trow[data-leaf="1"]');
      row.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, clientX: 620, clientY: 420 }));
      return true; })()`);
    await shoot("ui-ctx-menu.png");

    await evalJs(`(() => {
      const b = Array.from(document.querySelectorAll('#ctxLayer .mi'))
        .find(i => i.textContent.includes('Find...'));
      b.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      return true; })()`);
    await evalJs(`(() => { const i = document.querySelector('#modalLayer input');
      i.value = 'imsi'; i.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      return true; })()`);
    await sleep(600);
    await shoot("ui-find-dialog.png");

    await evalJs(`(() => { closeModal(); return true; })()`);
    await evalJs(`(async () => { await runCommand('statistics'); return true; })()`);
    await sleep(400);
    await shoot("ui-statistics.png");

    await evalJs(`(() => { closeModal(); return true; })()`);
    await evalJs(`(async () => {
      const ev = state.nav.children.find(c => c.kind === 'events');
      await setMainRoot(ev.items[0].id);
      const row = Array.from(state.rows.entries()).find(([id, r]) => r.dataset.name === 'ChargeDetail');
      await selectNode(row[0], row[1]);
      await runCommand('insertChild');
      return true; })()`);
    await sleep(500);
    await shoot("ui-insert-dialog.png");
  } catch (err) {
    console.error("shot-dialogs failed:", err);
    process.exitCode = 1;
  } finally {
    try { proc.kill(); } catch (_e) { /* ignore */ }
    setTimeout(() => app.exit(0), 200);
  }
});
