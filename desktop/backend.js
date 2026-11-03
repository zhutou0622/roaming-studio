"use strict";
/**
 * Backend lifecycle for the Electron shell.
 *
 * Two modes:
 *   packaged  -> resources/backend/tap3-server.exe (PyInstaller onefile)
 *   dev       -> ../dist/tap3-server.exe if present, else `python -m tap3studio.server`
 */
const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const http = require("http");
const net = require("net");
const path = require("path");

function projectRoot(appRoot) {
  // dev: <repo>/desktop -> <repo>
  return path.resolve(appRoot, "..");
}

function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

function findExecutable(explicit) {
  const candidates = [];
  if (explicit) candidates.push(explicit);
  if (process.env.TAP3SERVER_EXE) candidates.push(process.env.TAP3SERVER_EXE);
  candidates.push(path.join(process.resourcesPath || "", "backend", "onedir", "tap3-server.exe"));
  candidates.push(path.join(process.resourcesPath || "", "backend", "tap3-server.exe"));
  candidates.push(path.join(projectRoot(__dirname), "dist", "onedir", "tap3-server", "tap3-server.exe"));
  candidates.push(path.join(projectRoot(__dirname), "dist", "tap3-server.exe"));
  return candidates.find((p) => p && fs.existsSync(p)) || null;
}

function findPython() {
  const explicit = process.env.TAP3STUDIO_PYTHON;
  if (explicit && fs.existsSync(explicit)) return { cmd: explicit, args: [] };
  const local = path.join(projectRoot(__dirname), ".venv", "Scripts", "python.exe");
  if (fs.existsSync(local)) return { cmd: local, args: [] };
  return { cmd: "python", args: [] };
}

function httpJson(url, method = "GET", payload, timeout = 4000) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const body = payload === undefined ? null : Buffer.from(JSON.stringify(payload));
    const req = http.request(
      {
        hostname: u.hostname,
        port: u.port,
        path: u.pathname + u.search,
        method,
        timeout,
        headers: body
          ? { "Content-Type": "application/json", "Content-Length": body.length }
          : {},
      },
      (res) => {
        const chunks = [];
        res.on("data", (c) => chunks.push(c));
        res.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          try {
            resolve({ status: res.statusCode, json: text ? JSON.parse(text) : {} });
          } catch (e) {
            resolve({ status: res.statusCode, json: null, text });
          }
        });
      }
    );
    req.on("timeout", () => req.destroy(new Error(`timeout after ${timeout}ms`)));
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

async function waitReady(baseUrl, timeoutMs = 45000) {
  const started = Date.now();
  let lastError = null;
  while (Date.now() - started < timeoutMs) {
    try {
      const r = await httpJson(`${baseUrl}/api/state`, "GET", undefined, 2500);
      if (r.status === 200) return true;
      lastError = new Error(`HTTP ${r.status}`);
    } catch (err) {
      lastError = err;
    }
    await new Promise((res) => setTimeout(res, 250));
  }
  throw new Error(`backend did not become ready: ${lastError && lastError.message}`);
}

/**
 * Start the Python backend.
 * @param {object} opts
 * @param {string} opts.appRoot          directory of main.js
 * @param {boolean} opts.packaged        app.isPackaged
 * @param {(line:string)=>void} opts.onLog
 * @param {string=} opts.openPath        file to preload
 */
async function startBackend(opts) {
  const port = opts.port || (await freePort());
  const baseUrl = `http://127.0.0.1:${port}`;
  const exe = opts.packaged ? findExecutable() : findExecutable();
  let cmd;
  let args;
  let cwd;

  if (exe) {
    cmd = exe;
    args = ["--port", String(port)];
    cwd = path.dirname(exe);
  } else {
    const py = findPython();
    cmd = py.cmd;
    args = ["-m", "tap3studio.server", "--port", String(port)];
    cwd = projectRoot(opts.appRoot || __dirname);
  }
  if (opts.openPath) args.push("--open", opts.openPath);

  const log = opts.onLog || (() => {});
  log(`[backend] ${cmd} ${args.join(" ")}`);
  const child = spawn(cmd, args, {
    cwd,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      PYTHONPATH: [cwd, process.env.PYTHONPATH || ""].filter(Boolean).join(path.delimiter),
      PYTHONUNBUFFERED: "1",
      TAP3_PORT: String(port),
    },
  });
  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");
  child.stdout.on("data", (d) => String(d).trim().split(/\r?\n/).forEach((l) => l && log(`[py] ${l}`)));
  child.stderr.on("data", (d) => String(d).trim().split(/\r?\n/).forEach((l) => l && log(`[py!] ${l}`)));
  child.on("exit", (code, signal) => log(`[backend] exited code=${code} signal=${signal}`));

  await waitReady(baseUrl, opts.timeoutMs || 45000);
  log(`[backend] ready on ${baseUrl}`);
  return { child, port, baseUrl, mode: exe ? "exe" : "python" };
}

function stopBackend(handle) {
  if (!handle || !handle.child) return;
  const pid = handle.child.pid;
  // PyInstaller onefile runs a bootloader parent + child. Kill the whole tree
  // *while the parent is still alive* (taskkill /T walks the tree), then fall
  // back to a plain kill.
  if (pid) {
    try {
      if (process.platform === "win32") {
        spawnSync("taskkill", ["/pid", String(pid), "/t", "/f"], {
          windowsHide: true,
          timeout: 5000,
        });
      } else {
        process.kill(pid, "SIGTERM");
      }
    } catch (_e2) { /* nothing left to kill */ }
  }
  try { handle.child.kill(); } catch (_e) { /* already gone */ }
  handle.child = null;
}

module.exports = { startBackend, stopBackend, waitReady, freePort, httpJson, findExecutable, findPython, projectRoot };
