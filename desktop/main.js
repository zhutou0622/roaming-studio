"use strict";
const { app, BrowserWindow, Menu, dialog, ipcMain, shell } = require("electron");
const fs = require("fs");
const path = require("path");
const { startBackend, stopBackend, httpJson, findExecutable } = require("./backend");

const APP_ROOT = __dirname;
const state = {
  win: null,
  backend: null,
  baseUrl: "",
  logFile: "",
  logLines: [],
  lastOpenPath: "",
  startupError: null,
};

function log(line) {
  const stamped = `${new Date().toISOString()} ${line}`;
  if (process.env.TAP3_DEBUG === "1" || process.env.TAP3_SMOKE === "1") {
    process.stdout.write(stamped + "\n");
  }
  state.logLines.push(stamped);
  if (state.logLines.length > 500) state.logLines.shift();
  if (state.win && !state.win.isDestroyed()) {
    state.win.webContents.send("backend-log", stamped);
  }
  try {
    if (state.logFile) fs.appendFileSync(state.logFile, stamped + "\n");
  } catch (_e) { /* logging must never break the app */ }
}

function createWindow() {
  state.win = new BrowserWindow({
    width: 1500,
    height: 940,
    minWidth: 1100,
    minHeight: 700,
    show: false,
    frame: false,
    backgroundColor: "#f0f0f0",
    title: "Roaming Studio",
    autoHideMenuBar: true,
    icon: path.join(APP_ROOT, "assets", "icon.png"),
    webPreferences: {
      preload: path.join(APP_ROOT, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      spellcheck: false,
    },
  });

  const smoke = process.env.TAP3_SMOKE === "1";
  state.win.once("ready-to-show", () => {
    if (!smoke || process.env.TAP3_SHOT) state.win.show();
  });
  if (smoke || process.env.TAP3_SHOT) {
    state.win.webContents.once("did-finish-load", () => {
      log("[smoke] renderer loaded");
      state.win.webContents.executeJavaScript("Object.keys(window.tap3desktop||{}).join(',')")
        .then((keys) => log("[smoke] desktop api: " + keys))
        .catch((err) => log("[smoke] desktop api error: " + err.message));
      const shotPath = process.env.TAP3_SHOT;
      setTimeout(async () => {
        if (shotPath) {
          try {
            const img = await state.win.webContents.capturePage();
            fs.writeFileSync(shotPath, img.toPNG());
            log("[shot] wrote " + shotPath);
          } catch (err) {
            log("[shot] failed: " + err.message);
          }
        }
        log("[smoke] quitting");
        app.quit();
      }, shotPath ? 1500 : 800);
    });
  }
  state.win.on("closed", () => {
    state.win = null;
  });
  state.win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  state.win.loadURL(state.baseUrl + "/");
}

async function openFileFlow(filePath) {
  if (!filePath) {
    const res = await dialog.showOpenDialog(state.win, {
      title: "打开 TAP3 / RAP / NRTRDE 文件",
      properties: ["openFile"],
      filters: [
        { name: "TAP3 / RAP / NRTRDE", extensions: ["tap3", "tap", "dat", "rap", "nrtde", "nrtrde"] },
        { name: "所有文件", extensions: ["*"] },
      ],
    });
    if (res.canceled || !res.filePaths.length) return { ok: false, canceled: true };
    filePath = res.filePaths[0];
  }
  try {
    const r = await httpJson(`${state.baseUrl}/api/open`, "POST", { path: filePath }, 30000);
    if (r.status !== 200) {
      const detail = (r.json && r.json.detail) || `HTTP ${r.status}`;
      dialog.showErrorBox("无法打开文件", `${filePath}\n\n${detail}`);
      return { ok: false, error: detail };
    }
    state.lastOpenPath = filePath;
    if (state.win) {
      state.win.setTitle(`Roaming Studio - [${filePath}]`);
      state.win.webContents.reload();
    }
    log(`[ui] opened ${filePath}`);
    return { ok: true, path: filePath, header: r.json.header };
  } catch (err) {
    dialog.showErrorBox("无法打开文件", `${filePath}\n\n${err.message}`);
    return { ok: false, error: err.message };
  }
}

function buildMenu() {
  const template = [
    {
      label: "文件",
      submenu: [
        { label: "打开 TAP3 文件…", accelerator: "CmdOrCtrl+O", click: () => openFileFlow() },
        {
          label: "打开示例文件",
          click: () => {
            const sample = path.join(process.resourcesPath || "", "samples", "demo.tap3");
            const devSample = path.join(APP_ROOT, "..", "samples", "demo.tap3");
            openFileFlow(fs.existsSync(sample) ? sample : devSample);
          },
        },
        { type: "separator" },
        {
          label: "保存到…",
          accelerator: "CmdOrCtrl+S",
          click: async () => {
            const res = await dialog.showSaveDialog(state.win, {
              title: "保存 TAP3 文件",
              defaultPath: state.lastOpenPath || "output.tap3",
              filters: [{ name: "TAP3", extensions: ["tap3"] }],
            });
            if (res.canceled || !res.filePath) return;
            try {
              const r = await httpJson(`${state.baseUrl}/api/save`, "POST", { path: res.filePath }, 60000);
              if (r.status === 200) {
                dialog.showMessageBox(state.win, {
                  type: "info", message: "已保存", detail: r.json.path,
                  buttons: ["确定"],
                });
              } else {
                dialog.showErrorBox("保存失败", JSON.stringify(r.json));
              }
            } catch (err) {
              dialog.showErrorBox("保存失败", err.message);
            }
          },
        },
        { type: "separator" },
        { role: "quit", label: "退出" },
      ],
    },
    {
      label: "编辑",
      submenu: [
        { role: "undo" }, { role: "redo" }, { type: "separator" },
        { role: "cut" }, { role: "copy" }, { role: "paste" }, { role: "selectAll" },
      ],
    },
    {
      label: "视图",
      submenu: [
        { role: "reload", label: "重新加载" },
        { role: "forceReload", label: "强制重新加载" },
        { role: "toggleDevTools", label: "开发者工具" },
        { type: "separator" },
        { role: "resetZoom" }, { role: "zoomIn" }, { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" },
      ],
    },
    {
      label: "帮助",
      submenu: [
        {
          label: "后台日志…",
          click: () => {
            const body = state.logLines.slice(-200).join("\n");
            dialog.showMessageBox(state.win, {
              type: "info",
              title: "后台日志",
              message: `后端模式：${state.backend ? state.backend.mode : "未启动"}  ${state.baseUrl}`,
              detail: body || "(no output)",
              buttons: ["确定", "打开日志文件"],
              defaultId: 0,
              cancelId: 0,
            }).then((r) => {
              if (r.response === 1 && state.logFile) shell.openPath(state.logFile);
            });
          },
        },
        { type: "separator" },
        {
          label: "关于 TAP3 Studio",
          click: () => {
            const exe = findExecutable();
            dialog.showMessageBox(state.win, {
              type: "info",
              title: "关于",
              message: `TAP3 Studio ${app.getVersion()}`,
              detail:
                "TAP3 / RAP / NRTRDE 查看器 · 编辑器 · 校验器\n" +
                "Electron " + process.versions.electron + " / Chromium " + process.versions.chrome + "\n" +
                "后端：" + (state.backend ? state.backend.mode : "未启动") +
                (exe ? `\n${exe}` : "\n(python -m tap3studio.server)"),
              buttons: ["确定"],
            });
          },
        },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

async function boot() {
  state.logFile = path.join(app.getPath("userData"), "backend.log");
  log(`[app] starting Roaming Studio ${app.getVersion()} packaged=${app.isPackaged}`);
  try {
    state.backend = await startBackend({
      appRoot: APP_ROOT,
      packaged: app.isPackaged,
      onLog: log,
      openPath: process.env.TAP3_SHOT_FILE || "",
    });
    state.baseUrl = state.backend.baseUrl;
  } catch (err) {
    state.startupError = err;
    log(`[fatal] ${err.stack || err.message}`);
    const exeMissing = !findExecutable();
    dialog.showErrorBox(
      "TAP3 Studio 后端启动失败",
      `${err.message}\n\n` +
        (exeMissing
          ? "未找到内置后端。开发模式请先运行：\n  python -m PyInstaller ... server_entry.py\n" +
            "或确保本机 Python 已安装依赖：\n  pip install -r requirements.txt\n\n"
          : "") +
        `日志：${state.logFile}`
    );
    app.quit();
    return;
  }
  buildMenu();
  createWindow();
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", (_e, argv) => {
    if (state.win) {
      if (state.win.isMinimized()) state.win.restore();
      state.win.focus();
    }
    const fileArg = argv.slice(1).find((a) => /\.(tap3|tap|dat|rap|nrtde|nrtrde)$/i.test(a));
    if (fileArg) openFileFlow(fileArg);
  });

  app.whenReady().then(boot);

  app.on("window-all-closed", () => app.quit());

  let shuttingDown = false;
  const shutdown = () => {
    if (shuttingDown) return;
    shuttingDown = true;
    stopBackend(state.backend);
    state.backend = null;
    // Guarantee the shell never hangs on a stuck child during shutdown.
    setTimeout(() => app.exit(0), 1500).unref?.();
  };
  app.on("before-quit", shutdown);
  app.on("will-quit", shutdown);
}

ipcMain.handle("open-file", async (_evt, filePath) => openFileFlow(filePath));
ipcMain.handle("window-minimize", () => { if (state.win) state.win.minimize(); });
ipcMain.handle("window-maximize", () => {
  if (!state.win) return;
  if (state.win.isMaximized()) state.win.unmaximize();
  else state.win.maximize();
});
ipcMain.handle("window-close", () => app.quit());
ipcMain.handle("pick-file", async (_evt, opts) => {
  const res = await dialog.showOpenDialog(state.win, {
    title: (opts && opts.title) || "Select a file",
    properties: ["openFile"],
    filters: (opts && opts.filters) || [{ name: "All files", extensions: ["*"] }],
  });
  if (res.canceled || !res.filePaths.length) return "";
  return res.filePaths[0];
});
ipcMain.handle("pick-directory", async () => {
  const res = await dialog.showOpenDialog(state.win, {
    title: "Select a folder with TAP files",
    properties: ["openDirectory"],
  });
  if (res.canceled || !res.filePaths.length) return "";
  return res.filePaths[0];
});
ipcMain.handle("app-info", () => ({
  version: app.getVersion(),
  baseUrl: state.baseUrl,
  backendMode: state.backend ? state.backend.mode : null,
  backendExe: findExecutable(),
  packaged: app.isPackaged,
  logFile: state.logFile,
}));
ipcMain.handle("backend-log", () => state.logLines.slice(-200).join("\n"));
ipcMain.handle("quit", () => app.quit());
