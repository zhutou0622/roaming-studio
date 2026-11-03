"use strict";
/**
 * Headless plumbing test (no Electron window needed):
 *   node selftest.js
 * Starts the backend exactly like the app does, checks /api/state and
 * /api/validate, prints the mode, then stops the process.
 */
const { startBackend, stopBackend, httpJson, findExecutable } = require("./backend");

(async () => {
  const t0 = Date.now();
  const backend = await startBackend({
    appRoot: __dirname,
    packaged: false,
    onLog: (l) => console.log(l),
  });
  console.log(`mode=${backend.mode} url=${backend.baseUrl} exe=${findExecutable() || "(python)"}`);
  const state = await httpJson(`${backend.baseUrl}/api/state`, "GET", undefined, 5000);
  console.log("state:", JSON.stringify(state.json).slice(0, 160));
  const gen = await httpJson(`${backend.baseUrl}/api/open`, "POST", { events: 12, seed: 3 }, 20000);
  console.log("generate:", gen.status, gen.json && gen.json.header && gen.json.header.releaseLabel,
    gen.json && gen.json.stats && gen.json.stats.events, "events");
  const val = await httpJson(`${backend.baseUrl}/api/validate`, "GET", undefined, 20000);
  console.log("validate:", val.status, val.json && val.json.errors, "errors",
    val.json && val.json.warnings, "warnings");
  const html = await new Promise((resolve, reject) => {
    require("http").get(`${backend.baseUrl}/`, (res) => {
      res.resume();
      resolve(res.statusCode);
    }).on("error", reject);
  });
  console.log("ui:", html);
  stopBackend(backend);
  console.log(`selftest ok in ${Date.now() - t0} ms`);
  setTimeout(() => process.exit(0), 300);
})().catch((err) => {
  console.error("selftest failed:", err);
  process.exit(1);
});
