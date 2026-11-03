"use strict";
const { contextBridge, ipcRenderer, webUtils } = require("electron");

contextBridge.exposeInMainWorld("tap3desktop", {
  /** Native open dialog; resolves {ok, path} or {ok:false, canceled}. */
  openFile: (filePath) => ipcRenderer.invoke("open-file", filePath || ""),
  /** Absolute path of a dropped File object (Electron >= 29 webUtils). */
  pathForFile: (file) => {
    try {
      return webUtils.getPathForFile(file);
    } catch (_e) {
      return "";
    }
  },
  /** Shell/backend information. */
  info: () => ipcRenderer.invoke("app-info"),
  /** Last 200 backend log lines. */
  backendLog: () => ipcRenderer.invoke("backend-log"),
  /** Subscribe to live backend log lines; returns an unsubscribe function. */
  onBackendLog: (cb) => {
    const handler = (_evt, line) => cb(line);
    ipcRenderer.on("backend-log", handler);
    return () => ipcRenderer.removeListener("backend-log", handler);
  },
  quit: () => ipcRenderer.invoke("quit"),
  minimize: () => ipcRenderer.invoke("window-minimize"),
  maximize: () => ipcRenderer.invoke("window-maximize"),
  close: () => ipcRenderer.invoke("window-close"),
});
