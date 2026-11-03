"use strict";
/**
 * Capture edit/metadata behaviour for review:
 *   env -u ELECTRON_RUN_AS_NODE npx electron shot-edit.js [file]
 * 1) edit a value inside CED #1 and keep the call view (edited row highlighted)
 * 2) jump to the last call
 * Writes ../docs/ui-edit-highlight.png and ../docs/ui-last-call.png
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
      await sleep(300);
      const img = await win.webContents.capturePage();
      const out = path.join(ROOT, "docs", name);
      fs.writeFileSync(out, img.toPNG());
      console.log("wrote", out);
    };

    await evalJs(`(async () => {
      const ev = state.nav.children.find(c => c.kind === 'events');
      await setMainRoot(ev.items[0].id);
      const leaf = Array.from(state.rows.entries()).find(
        ([id, r]) => r.dataset.leaf === '1' && r.dataset.name === 'imsi');
      await selectNode(leaf[0], leaf[1]);
      await runCommand('editValue');
      const ta = document.querySelector('#modalLayer textarea');
      ta.value = '262019999999999';
      Array.from(document.querySelectorAll('#modalLayer .dlg-buttons button'))
        .find(b => b.textContent.trim() === 'OK').click();
      await new Promise(r => setTimeout(r, 1200));
      // move the selection away so the yellow "modified" row is clearly visible
      const first = document.querySelector('#mainTree .trow');
      if (first) first.click();
      return true; })()`);
    await shoot("ui-edit-highlight.png");

    await evalJs("runCommand('gotoLast')");
    await sleep(500);
    await shoot("ui-last-call.png");
  } catch (err) {
    console.error("shot-edit failed:", err);
    process.exitCode = 1;
  } finally {
    try { proc.kill(); } catch (_e) { /* ignore */ }
    setTimeout(() => app.exit(0), 200);
  }
});
