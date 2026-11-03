"use strict";
/**
 * UI screenshot helper (development only):
 *   env -u ELECTRON_RUN_AS_NODE npx electron shot.js [out.png] [width] [height]
 *
 * Starts the current source backend with Python, opens samples/demo.tap3,
 * renders the UI and writes a PNG so the layout can be reviewed.
 */
const { app, BrowserWindow } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const { waitReady, freePort, httpJson } = require("./backend");

const ROOT = path.resolve(__dirname, "..");
const OUT = process.argv[2] || path.join(ROOT, "docs", "ui-dev.png");
const W = parseInt(process.argv[3] || "1680", 10);
const H = parseInt(process.argv[4] || "1004", 10);
const FILE = process.argv[5] || process.env.TAP3_SHOT_FILE ||
  path.join(ROOT, "samples", "demo.tap3");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

app.commandLine.appendSwitch("force-device-scale-factor", "1");

app.whenReady().then(async () => {
  const port = await freePort();
  const base = `http://127.0.0.1:${port}`;
  const proc = spawn("python", ["-m", "tap3studio.server", "--port", String(port)], {
    cwd: ROOT, windowsHide: true, stdio: "ignore",
    env: { ...process.env, PYTHONPATH: ROOT },
  });
  try {
    await waitReady(base, 30000);
    await httpJson(base + "/api/open", "POST", { path: FILE }, 60000);
    const win = new BrowserWindow({
      width: W, height: H, show: false, frame: false, backgroundColor: "#f0f0f0",
      webPreferences: { offscreen: false, contextIsolation: true },
    });
    win.webContents.on("console-message", (_e, level, message, line, source) => {
      console.log(`[console:${level}] ${message} (${source}:${line})`);
    });
    win.webContents.on("render-process-gone", (_e, d) => console.log("renderer gone", d));
    win.webContents.setBackgroundThrottling(false);
    await win.loadURL(base + "/");
    win.showInactive();
    await sleep(1500);
    const info = await win.webContents.executeJavaScript(`(() => ({
      nav: (document.querySelector('#navTree')||{}).innerHTML?.length || 0,
      navText: (document.querySelector('#navTree')||{}).innerText?.slice(0,120) || "",
      main: (document.querySelector('#mainTree')||{}).children?.length || 0,
      mainText: (document.querySelector('#mainTree')||{}).innerText?.slice(0,120) || "",
      dict: (document.querySelector('#dictBody')||{}).innerHTML?.length || 0,
      status: (document.querySelector('#statusText')||{}).textContent || "",
      err: window.__lastError || null
    }))()`);
    console.log("DOM:", JSON.stringify(info));
    await sleep(500);
    const image = await win.webContents.capturePage();
    fs.writeFileSync(OUT, image.toPNG());
    console.log("wrote", OUT, image.getSize());
    win.destroy();
  } catch (err) {
    console.error("shot failed:", err);
    process.exitCode = 1;
  } finally {
    try { proc.kill(); } catch (_e) { /* ignore */ }
    setTimeout(() => app.quit(), 200);
  }
});
