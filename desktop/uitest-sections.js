"use strict";
/**
 * Section-expansion regression on the large TAP file:
 *   env -u ELECTRON_RUN_AS_NODE npx electron uitest-sections.js [file]
 * Selecting a batch section (accountingInfo, networkInfo, ...) must show the
 * whole subtree expanded, while the 3,883-entry event list stays shallow.
 * Also writes ../docs/ui-section-expanded.png for review.
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
    await win.loadURL(base + "/");
    win.showInactive();
    const evalJs = (code) => win.webContents.executeJavaScript(code, true);
    const waitFor = async (expr, timeout = 20000) => {
      const start = Date.now();
      while (Date.now() - start < timeout) {
        if (await evalJs(expr)) return true;
        await sleep(40);
      }
      return false;
    };
    await waitFor("document.querySelectorAll('#mainTree .trow').length > 10");

    const openSection = async (label) => {
      const t = Date.now();
      await evalJs(`(() => {
        const r = Array.from(document.querySelectorAll('#navTree .trow'))
          .find(x => x.textContent.includes(${JSON.stringify(label)}));
        if (!r) throw new Error('nav row not found: ' + ${JSON.stringify(label)});
        r.click(); return true; })()`);
      await sleep(120);
      await waitFor("document.querySelector('#statusText').textContent !== 'Loading…'", 15000);
      return Date.now() - t;
    };
    const treeState = () => evalJs(`({
      rows: document.querySelectorAll('#mainTree .trow').length,
      text: document.querySelector('#mainTree').innerText,
      status: document.querySelector('#statusText').textContent
    })`);

    await openSection("accountingInfo");
    let st = await treeState();
    check("accountingInfo expands fully", st.rows >= 8,
      `rows=${st.rows}`);
    check("accountingInfo deep leaves visible",
      /taxCode|taxType|exchangeRateCode|numberOfDecimalPlaces/.test(st.text));
    const img = await win.webContents.capturePage();
    fs.writeFileSync(path.join(ROOT, "docs", "ui-section-expanded.png"), img.toPNG());
    console.log("wrote docs/ui-section-expanded.png");

    await openSection("networkInfo");
    st = await treeState();
    check("networkInfo expands fully", st.rows >= 6, `rows=${st.rows}`);
    check("networkInfo deep leaves visible", /recEntityType|recEntityCode|utcTimeOffsetCode/.test(st.text));

    await openSection("batchControlInfo");
    st = await treeState();
    check("batchControlInfo expands fully", st.rows >= 6, `rows=${st.rows}`);
    check("batchControlInfo deep leaves visible", /sender|fileSequenceNumber|releaseVersionNumber/.test(st.text));

    await openSection("auditControlInfo");
    st = await treeState();
    check("auditControlInfo expands fully", st.rows >= 5, `rows=${st.rows}`);
    check("auditControlInfo deep leaves visible", /totalCharge|totalTaxValue|callEventDetailsCount/.test(st.text));

    await openSection("callEventDetails");
    st = await treeState();
    check("event list stays shallow", st.rows < 6000, `rows=${st.rows}`);

    await evalJs(`(() => { const r = Array.from(document.querySelectorAll('#navTree .trow'))
        .find(x => x.textContent.includes('DataInterChange')); r.click(); return true; })()`);
    await sleep(150);
    st = await treeState();
    check("document root stays shallow", st.rows < 20, `rows=${st.rows}`);
  } catch (err) {
    console.error("uitest-sections crashed:", err);
    failed++;
  } finally {
    try { proc.kill(); } catch (_e) { /* ignore */ }
    console.log(failed ? `UITEST-SECTIONS FAILED (${failed})` : "UITEST-SECTIONS OK");
    setTimeout(() => app.exit(failed ? 1 : 0), 300);
  }
});
