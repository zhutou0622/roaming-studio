"use strict";
/* Roaming Studio — UI controller (classic Win32 layout, TD.57 data dictionary) */

const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

/* ------------------------------------------------------------------ icons */
const svg = (body) => "data:image/svg+xml;charset=utf-8," + encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">${body}</svg>`);
const ICONS = {
  root: svg('<rect x="1" y="3" width="14" height="11" fill="#fff" stroke="#7a5a1a"/><rect x="1" y="3" width="14" height="3" fill="#c9a24a"/><rect x="3" y="7" width="10" height="1" fill="#9aa"/><rect x="3" y="9" width="10" height="1" fill="#9aa"/>'),
  folder: svg('<path d="M1 4h6l1 2h7v8H1z" fill="#f0c65c" stroke="#8a6a1a"/><path d="M1 6h14v1H1z" fill="#fff2c0"/>'),
  folderOpen: svg('<path d="M1 4h6l1 2h7v2H4L1 14z" fill="#f0c65c" stroke="#8a6a1a"/><path d="M4 6h11l-3 8H1z" fill="#ffe9a8" stroke="#8a6a1a"/>'),
  doc: svg('<path d="M3 1h7l3 3v11H3z" fill="#fff" stroke="#7a7a7a"/><path d="M10 1v3h3" fill="#e8e8e8" stroke="#7a7a7a"/><rect x="5" y="6" width="6" height="1" fill="#7a8fa8"/><rect x="5" y="8" width="6" height="1" fill="#7a8fa8"/><rect x="5" y="10" width="4" height="1" fill="#7a8fa8"/>'),
  leaf: svg('<rect x="3" y="2" width="10" height="12" fill="#fff" stroke="#7a7a7a"/><rect x="5" y="5" width="6" height="1" fill="#8aa"/><rect x="5" y="7" width="6" height="1" fill="#8aa"/><rect x="5" y="9" width="4" height="1" fill="#8aa"/>'),
  neu: svg('<path d="M3 1h7l3 3v11H3z" fill="#fff" stroke="#555"/><path d="M10 1v3h3" stroke="#555" fill="none"/><path d="M8 5v6M5 8h6" stroke="#2a7a2a" stroke-width="1.5"/>'),
  open: svg('<path d="M1 4h6l1 2h7v2H4L1 14z" fill="#f0c65c" stroke="#8a6a1a"/><path d="M4 6h11l-3 8H1z" fill="#ffe9a8" stroke="#8a6a1a"/>'),
  save: svg('<rect x="1" y="1" width="14" height="14" fill="#c9d6e8" stroke="#33507a"/><rect x="4" y="1" width="8" height="5" fill="#fff" stroke="#33507a"/><rect x="3" y="9" width="10" height="6" fill="#fff" stroke="#33507a"/><rect x="5" y="10" width="6" height="1" fill="#889"/>'),
  validate: svg('<path d="M2 8l4 4 8-9" fill="none" stroke="#1a7a1a" stroke-width="2"/>'),
  find: svg('<circle cx="6.5" cy="6.5" r="4.5" fill="none" stroke="#33507a" stroke-width="1.6"/><path d="M10 10l4 4" stroke="#33507a" stroke-width="2"/>'),
  last: svg('<path d="M2 3l6 5-6 5zM9 3l6 5-6 5z" fill="#7a2a8a"/><rect x="15" y="3" width="1" height="10" fill="#7a2a8a"/>'),
  goto: svg('<path d="M3 13L13 3M13 3H7M13 3v6" fill="none" stroke="#7a2a8a" stroke-width="1.6"/>'),
  expand: svg('<rect x="1" y="2" width="14" height="12" fill="#fff" stroke="#666"/><path d="M8 5v6M5 8h6" stroke="#333"/>'),
  collapse: svg('<rect x="1" y="2" width="14" height="12" fill="#fff" stroke="#666"/><path d="M5 8h6" stroke="#333"/>'),
  print: svg('<rect x="3" y="1" width="10" height="4" fill="#fff" stroke="#555"/><rect x="1" y="5" width="14" height="6" fill="#d8d8d8" stroke="#555"/><rect x="4" y="9" width="8" height="6" fill="#fff" stroke="#555"/>'),
  cut: svg('<path d="M4 2l8 9M12 2L4 11" stroke="#666" stroke-width="1.2"/><circle cx="4" cy="13" r="2" fill="none" stroke="#666"/><circle cx="12" cy="13" r="2" fill="none" stroke="#666"/>'),
  copy: svg('<rect x="2" y="2" width="8" height="10" fill="#fff" stroke="#555"/><rect x="6" y="5" width="8" height="10" fill="#fff" stroke="#555"/>'),
  paste: svg('<rect x="3" y="2" width="10" height="12" fill="#f0e2c0" stroke="#666"/><rect x="5" y="1" width="6" height="3" fill="#c9a24a" stroke="#666"/><rect x="5" y="6" width="6" height="1" fill="#8a7a5a"/><rect x="5" y="8" width="6" height="1" fill="#8a7a5a"/>'),
  undo: svg('<path d="M6 4L2 8l4 4" fill="none" stroke="#33507a" stroke-width="1.6"/><path d="M2 8h8a4 4 0 010 8H8" fill="none" stroke="#33507a" stroke-width="1.6"/>'),
  redo: svg('<path d="M10 4l4 4-4 4" fill="none" stroke="#33507a" stroke-width="1.6"/><path d="M14 8H6a4 4 0 000 8h2" fill="none" stroke="#33507a" stroke-width="1.6"/>'),
  dict: svg('<path d="M2 2h12v12H2z" fill="#fdf6e3" stroke="#8a6a1a"/><rect x="2" y="2" width="12" height="3" fill="#e6c68a"/><rect x="4" y="6" width="8" height="1" fill="#8a7a5a"/><rect x="4" y="8" width="8" height="1" fill="#8a7a5a"/><rect x="4" y="10" width="5" height="1" fill="#8a7a5a"/>'),
};

/* ------------------------------------------------------------------- api */
async function api(path, method = "GET", body) {
  const opt = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opt.body = JSON.stringify(body);
  const res = await fetch(path, opt);
  let data = {};
  try { data = await res.json(); } catch (_e) { /* empty body */ }
  if (!res.ok) {
    const d = data && data.detail !== undefined ? data.detail : res.statusText;
    throw new Error(typeof d === "string" ? d : JSON.stringify(d));
  }
  return data;
}

/* ----------------------------------------------------------------- state */
const state = {
  open: false,
  path: "",
  header: null,
  stats: null,
  nav: null,
  selected: null,
  rootId: null,
  rows: new Map(),
  dict: null,
  prefs: Object.assign({ showScale: true, showTags: false }, JSON.parse(localStorage.getItem("rs.prefs") || "{}")),
  profile: JSON.parse(localStorage.getItem("rs.profile") || "null"),
  panels: { nav: true, dict: true },
};

const AMOUNT_TYPES = new Set(["Charge", "AbsoluteAmount", "TaxValue", "TaxableAmount", "TotalCharge",
  "TotalTaxValue", "TotalDiscountValue", "Commission", "AdvisedCharge", "DiscountValue",
  "DiscountableAmount", "TotalChargeRefund", "TotalTaxRefund", "TotalDiscountRefund",
  "TotalAdvisedCharge", "TotalCommission", "CamelInvocationFee", "FixedDiscountValue", "Discount"]);

function status(msg) { $("#statusText").textContent = msg || "Ready"; }
function statusInfo() {
  if (!state.open || !state.header) { $("#statusInfo").textContent = ""; return; }
  const h = state.header, s = state.stats || {};
  const cur = h.tapCurrency || h.localCurrency || "";
  const dp = h.tapDecimalPlaces;
  const parts = [h.releaseLabel, `records: ${s.events != null ? s.events : 0}`];
  if (s.chargeSum != null && dp != null) {
    parts.push(`charge: ${(s.chargeSum / Math.pow(10, dp)).toFixed(dp)} ${cur}`.trim());
  }
  if (state.modifiedCount) parts.push(`modified: ${state.modifiedCount}`);
  if (s.auditCount != null && s.auditCount !== s.events) parts.push("audit mismatch");
  $("#statusInfo").textContent = parts.join("   ");
}
function setTitle() {
  const name = state.path || (state.header ? state.header.file : "");
  $("#appTitle").textContent = `Roaming Studio - [${name || "no file"}]`;
  document.title = `Roaming Studio - [${name || "no file"}]`;
}
function fmtAmount(raw, type) {
  if (!state.prefs.showScale || raw === "" || raw == null) return null;
  if (!AMOUNT_TYPES.has(type)) return null;
  const dp = state.header && state.header.tapDecimalPlaces;
  if (dp == null) return null;
  const v = Number(raw);
  if (!isFinite(v)) return null;
  const cur = state.header.tapCurrency || state.header.localCurrency || "";
  return `(${(v / Math.pow(10, dp)).toFixed(dp)} ${cur})`;
}

/* ------------------------------------------------------------------ menus */
const MENUS = [
  { label: "File", items: [
    { label: "New", accel: "Ctrl+N", cmd: "new" },
    { label: "Open...", accel: "Ctrl+O", cmd: "open" },
    { label: "Close", cmd: "close" },
    { sep: true },
    { label: "Save", accel: "Ctrl+S", cmd: "save" },
    { label: "Save As...", cmd: "saveAs" },
    { label: "Import Listing...", cmd: "importListing" },
    { label: "Batch Scan Folder...", cmd: "batchScan" },
    { label: "Export", submenu: [
      { label: "Records as CSV...", cmd: "export:csv" },
      { label: "Structure as JSON...", cmd: "export:json" },
      { label: "Tap3Info XML...", cmd: "export:xml" },
      { label: "Listing...", cmd: "export:listing" },
      { label: "Statistics report...", cmd: "export:stat" },
    ] },
    { sep: true },
    { label: "Exit", cmd: "exit" },
  ] },
  { label: "Edit", items: [
    { label: "Edit Value...", accel: "F2", cmd: "editValue" },
    { label: "Clone Node", cmd: "clone" },
    { label: "Delete Node", accel: "Del", cmd: "delete" },
    { sep: true },
    { label: "Insert Child...", cmd: "insertChild" },
    { label: "Insert Sibling...", cmd: "insertSibling" },
    { sep: true },
    { label: "Copy Path", cmd: "copyPath" },
    { sep: true },
    { label: "Find...", accel: "Ctrl+F", cmd: "find" },
    { label: "Replace...", accel: "Ctrl+H", cmd: "replace" },
    { label: "Go to Call...", accel: "Ctrl+G", cmd: "gotoCall" },
    { label: "Go to First Call", accel: "Ctrl+Home", cmd: "gotoFirst" },
    { label: "Go to Last Call", accel: "Ctrl+End", cmd: "gotoLast" },
  ] },
  { label: "View", items: [
    { label: "Expand All", cmd: "expandAll" },
    { label: "Collapse All", cmd: "collapseAll" },
    { sep: true },
    { label: "Navigation Pane", check: "nav", cmd: "toggleNav" },
    { label: "Data Dictionary", check: "dict", cmd: "toggleDict" },
    { sep: true },
    { label: "Hex View...", cmd: "hex" },
    { label: "Clear Modification Marks", cmd: "clearMarks" },
    { label: "Refresh", accel: "Ctrl+R", cmd: "refresh" },
  ] },
  { label: "Validations", items: [
    { label: "Validate All", accel: "F5", cmd: "validate" },
    { label: "Validate Current Node", cmd: "validateNode" },
    { label: "File Statistics...", cmd: "statistics" },
    { label: "Generate RAP Return File...", cmd: "genRap" },
    { sep: true },
    { label: "Validation Rules...", cmd: "rules" },
  ] },
  { label: "Configure", items: [
    { label: "Validation Profile...", cmd: "profile" },
    { label: "Preferences...", cmd: "prefs" },
  ] },
  { label: "Windows", items: [
    { label: "Navigation", check: "nav", cmd: "toggleNav" },
    { label: "Data Dictionary", check: "dict", cmd: "toggleDict" },
    { sep: true },
    { label: "Close All Documents", cmd: "close" },
  ] },
  { label: "Help", items: [
    { label: "About Roaming Studio", cmd: "about" },
    { label: "Data Dictionary Source (TD.57)", cmd: "aboutDict" },
  ] },
];

function buildMenubar() {
  const bar = $("#menubar");
  bar.innerHTML = "";
  MENUS.forEach((m, idx) => {
    const b = document.createElement("div");
    b.className = "menu-top";
    b.textContent = m.label;
    b.dataset.idx = idx;
    b.addEventListener("mousedown", (e) => { e.preventDefault(); openMenu(idx, b); });
    b.addEventListener("mouseenter", () => { if ($(".dropdown")) openMenu(idx, b); });
    bar.appendChild(b);
  });
}

function closeMenus() {
  $("#menuLayer").innerHTML = "";
  $$(".menu-top.open").forEach((n) => n.classList.remove("open"));
}

function openMenu(idx, anchor) {
  closeMenus();
  anchor.classList.add("open");
  const menu = MENUS[idx];
  const dd = document.createElement("div");
  dd.className = "dropdown";
  menu.items.forEach((it) => dd.appendChild(menuItem(it)));
  $("#menuLayer").appendChild(dd);
  const r = anchor.getBoundingClientRect();
  dd.style.left = r.left + "px";
  dd.style.top = r.bottom + "px";
}

function menuItem(it) {
  if (it.sep) { const d = document.createElement("div"); d.className = "sep"; return d; }
  const d = document.createElement("div");
  d.className = "mi";
  if (it.check) {
    const c = document.createElement("span");
    c.className = "chk";
    c.textContent = state.panels[it.check] ? "✓" : "";
    d.appendChild(c);
  }
  d.appendChild(document.createTextNode(it.label));
  if (it.accel) {
    const s = document.createElement("span");
    s.className = "sc"; s.textContent = it.accel; d.appendChild(s);
  }
  if (it.submenu) {
    const a = document.createElement("span");
    a.className = "arrow"; a.textContent = "▸"; d.appendChild(a);
    let sub = null;
    d.addEventListener("mouseenter", () => {
      if (sub) return;
      sub = document.createElement("div");
      sub.className = "dropdown";
      it.submenu.forEach((s2) => sub.appendChild(menuItem(s2)));
      $("#menuLayer").appendChild(sub);
      const r = d.getBoundingClientRect();
      sub.style.left = (r.right - 4) + "px";
      sub.style.top = (r.top - 2) + "px";
    });
    d.addEventListener("mouseleave", (e) => {
      if (sub && !sub.contains(e.relatedTarget)) { sub.remove(); sub = null; }
    });
  } else {
    d.addEventListener("click", () => { closeMenus(); closeCtx(); runCommand(it.cmd); });
  }
  return d;
}

document.addEventListener("mousedown", (e) => {
  if (!e.target.closest("#menuLayer") && !e.target.closest(".menu-top")) closeMenus();
  if (!e.target.closest("#ctxLayer .dropdown")) closeCtx();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { closeMenus(); closeCtx(); closeTopModal(); }
});

/* ---------------------------------------------------------------- toolbar */
function buildToolbar() {
  const tb = $("#toolbar");
  tb.innerHTML = "";
  const add = (icon, title, cmd, label) => {
    const b = document.createElement("button");
    b.className = "tbtn"; b.title = title;
    const img = document.createElement("img"); img.src = icon; img.alt = "";
    b.appendChild(img);
    if (label) { const s = document.createElement("span"); s.className = "lbl"; s.textContent = label; b.appendChild(s); }
    b.addEventListener("click", () => runCommand(cmd));
    tb.appendChild(b);
    return b;
  };
  add(ICONS.neu, "New file", "new");
  add(ICONS.open, "Open TAP3 file", "open");
  add(ICONS.save, "Save", "save");
  const sep2 = () => { const d = document.createElement("div"); d.className = "tbsep"; tb.appendChild(d); };
  sep2();
  const dis = (icon, title) => {
    const b = add(icon, title, null);
    b.disabled = true; b.style.opacity = "0.45"; b.style.cursor = "default";
    b.onclick = null;
  };
  dis(ICONS.print, "Print (not available)");
  dis(ICONS.cut, "Cut");
  dis(ICONS.copy, "Copy");
  dis(ICONS.paste, "Paste");
  dis(ICONS.undo, "Undo");
  dis(ICONS.redo, "Redo");
  sep2();
  add(ICONS.validate, "Validate file (F5)", "validate");
  const sep = sep2;
  const find = document.createElement("input");
  find.className = "findbox"; find.placeholder = "Find";
  find.addEventListener("keydown", (e) => { if (e.key === "Enter") doFind(find.value); });
  tb.appendChild(find);
  add(ICONS.goto, "Go to call", "gotoCall", "Go to call");
  add(ICONS.last, "Go to last call (Ctrl+End)", "gotoLast", "Last");
  sep();
  add(ICONS.expand, "Expand all", "expandAll");
  add(ICONS.collapse, "Collapse all", "collapseAll");
  const sp = document.createElement("div"); sp.className = "spacer"; tb.appendChild(sp);
  add(ICONS.dict, "Data Dictionary", "toggleDict");
}

/* ------------------------------------------------------------- navigation */
async function loadNav() {
  state.nav = await api("/api/nav");
  try {
    state.modifiedCount = (await api("/api/modified")).count;
  } catch (_e) { state.modifiedCount = 0; }
  state.header = state.nav.header;
  state.stats = state.nav.stats;
  state.eventIds = new Set();
  state.sectionIds = new Set();
  (state.nav.children || []).forEach((c) => {
    if (c.kind === "events") (c.items || []).forEach((it) => state.eventIds.add(it.id));
    else if (c.kind === "section") state.sectionIds.add(c.id);
  });
  renderNav();
  statusInfo(); setTitle();
}

function navRow(label, icon, depth, opts = {}) {
  const wrap = document.createElement("div");
  wrap.className = "tnode";
  const row = document.createElement("div");
  row.className = "trow";
  row.style.paddingLeft = (2 + depth * 14) + "px";
  if (opts.id) row.dataset.id = opts.id;

  const ex = document.createElement("span");
  ex.className = "expander box";
  ex.textContent = opts.expanded ? "−" : "+";
  if (!opts.expandable) ex.style.visibility = "hidden";
  row.appendChild(ex);

  const img = document.createElement("img");
  img.className = "ico"; img.src = icon;
  row.appendChild(img);

  const name = document.createElement("span");
  name.className = "fname"; name.textContent = label; name.title = label;
  row.appendChild(name);

  wrap.appendChild(row);
  const kids = document.createElement("div");
  kids.className = "tkids" + (opts.expanded ? "" : " hidden");
  wrap.appendChild(kids);

  ex.addEventListener("click", (e) => {
    e.stopPropagation();
    const hidden = kids.classList.toggle("hidden");
    ex.textContent = hidden ? "+" : "−";
    img.src = hidden ? ICONS.folder : ICONS.folderOpen;
    if (!hidden && opts.onExpand) opts.onExpand(kids);
  });
  if (opts.onClick) row.addEventListener("click", opts.onClick);
  return { wrap, row, kids, ex, img };
}

function renderNav() {
  const host = $("#navTree");
  host.innerHTML = "";
  const nav = state.nav;
  state.navRows = new Map();
  state.navEnsureAll = null;
  if (!nav) return;

  const root = navRow("DataInterChange", ICONS.root, 0, {
    expanded: true, expandable: true,
    onClick: () => { setMainRoot(nav.root.id); markNav(nav.root.id); },
  });
  host.appendChild(root.wrap);

  const batch = navRow("transferBatch", ICONS.folderOpen, 1,
    { expanded: true, expandable: true, onClick: () => setMainRoot(nav.root.id) });
  root.kids.appendChild(batch.wrap);

  (nav.children || []).forEach((c) => {
    if (c.kind === "section") {
      const r = navRow(c.name, ICONS.doc, 2, {
        onClick: () => setMainRoot(c.id),
      });
      batch.kids.appendChild(r.wrap);
    } else if (c.kind === "events") {
      const r = navRow(c.name, ICONS.folder, 2, {
        expanded: true, expandable: true, onClick: () => setMainRoot(c.id),
      });
      batch.kids.appendChild(r.wrap);
      const items = c.items || [];
      const CHUNK = 400;
      let shown = 0;
      state.navItems = items;
      state.navEnsureAll = () => { while (shown < items.length) addChunk(); };
      const more = document.createElement("div");
      r.kids.appendChild(more);
      const addChunk = () => {
        const next = items.slice(shown, shown + CHUNK);
        next.forEach((ev) => {
          const rr = navRow(ev.label, ICONS.leaf, 3, {
            id: ev.id,
            onClick: () => { setMainRoot(ev.id); markNav(ev.id); },
          });
          state.navRows.set(ev.id, rr.row);
          r.kids.insertBefore(rr.wrap, more);
        });
        shown += next.length;
        if (shown < items.length) {
          more.className = "trow nav-more";
          more.style.paddingLeft = (2 + 3 * 14) + "px";
          more.textContent = `Show next ${Math.min(CHUNK, items.length - shown)} of ${items.length}…`;
        } else if (more.parentNode) {
          more.remove();
        }
      };
      more.addEventListener("click", addChunk);
      addChunk();
      // load the next chunk automatically when the sentinel scrolls into view
      if (typeof IntersectionObserver === "function") {
        const io = new IntersectionObserver((entries) => {
          if (entries.some((e) => e.isIntersecting) && shown < items.length) addChunk();
          if (shown >= items.length) io.disconnect();
        }, { root: $("#navTree"), rootMargin: "120px" });
        io.observe(more);
      }
    }
  });
}

function markNav(id) {
  if (state.navSelected && state.navSelected !== id) {
    const prev = document.querySelector(`#navTree .trow[data-id="${state.navSelected}"]`);
    if (prev) prev.classList.remove("sel");
  }
  const row = document.querySelector(`#navTree .trow[data-id="${id}"]`);
  if (row) row.classList.add("sel");
  state.navSelected = id;
}

/* -------------------------------------------------------------- main tree */
async function setMainRoot(id) {
  state.rootId = id;
  const isEvent = state.eventIds && state.eventIds.has(id);
  const isSection = state.sectionIds && state.sectionIds.has(id);
  // events and batch sections open fully; the 3,883-entry event list and the
  // document root stay shallow so the pane never explodes
  const depth = isEvent ? 7 : (isSection ? 9 : 1);
  state.renderBudget = { n: 0, max: 8000 };
  status("Loading…");
  const res = await api("/api/tree", "POST", { id, depth });
  const host = $("#mainTree");
  host.innerHTML = "";
  state.rows.clear();
  host.appendChild(buildNode(res.node, 0, depth));
  markNav(id);
  if (res.truncated) {
    status(`Tree limited to ${res.nodes} nodes — expand the remaining groups on demand`);
  }
  autoSelectLeaf();
}

function autoSelectLeaf() {
  const preferred = ["teleServiceCode", "charge", "imsi", "callingNumber", "msisdn"];
  let target = null;
  for (const name of preferred) {
    for (const [id, row] of state.rows) {
      if (row.dataset.name === name) { target = id; break; }
    }
    if (target) break;
  }
  if (!target) {
    for (const [id, row] of state.rows) {
      if (row.dataset.leaf === "1") { target = id; break; }
    }
  }
  if (target) {
    const row = state.rows.get(target);
    row.scrollIntoView({ block: "center" });
    selectNode(target, row);
  }
}

function nodeLabelText(node) {
  let text = node.name || "";
  let scale = null;
  if (state.eventIds && state.eventIds.has(node.id)) {
    return { text: `CED(${node.type || ""})`, scale: null };
  }
  if (node.repeated) text = `[${(node.index || 0) + 1}] ${text}`;
  if (node.value !== "" && node.value != null && !node.constructed) {
    text += ": " + node.value;
    scale = fmtAmount(node.value, node.type);
  }
  return { text, scale };
}

function buildNode(node, depth, expandDepth) {
  if (node.field && node.name && node.field !== node.name) {
    // ASN.1 CHOICE: the wire carries only the alternative, the reference UI
    // shows the field group plus the chosen alternative below it.
    const outer = document.createElement("div");
    outer.className = "tnode";
    const grow = document.createElement("div");
    grow.className = "trow";
    grow.style.paddingLeft = (2 + depth * 13) + "px";
    const gex = document.createElement("span");
    gex.className = "expander box"; gex.textContent = "−";
    grow.appendChild(gex);
    const gimg = document.createElement("img");
    gimg.className = "ico"; gimg.src = ICONS.folderOpen;
    grow.appendChild(gimg);
    const gname = document.createElement("span");
    gname.className = "fname"; gname.textContent = node.field;
    grow.appendChild(gname);
    outer.appendChild(grow);
    const gkids = document.createElement("div");
    gkids.className = "tkids";
    outer.appendChild(gkids);
    gkids.appendChild(buildNode(Object.assign({}, node, { field: "" }), depth + 1, expandDepth - 1));

    gex.addEventListener("click", (e) => {
      e.stopPropagation();
      const hidden = gkids.classList.toggle("hidden");
      gex.textContent = hidden ? "+" : "−";
      gimg.src = hidden ? ICONS.folder : ICONS.folderOpen;
    });
    grow.addEventListener("click", () => selectNode(node.id, grow));
    grow.addEventListener("contextmenu", (e) => {
      e.preventDefault(); selectNode(node.id, grow); openCtx(e.clientX, e.clientY);
    });
    return outer;
  }
  const wrap = document.createElement("div");
  wrap.className = "tnode";
  const row = document.createElement("div");
  row.className = "trow";
  row.dataset.id = node.id;
  if (node.name) row.dataset.name = node.name;
  row.dataset.leaf = node.constructed ? "0" : "1";
  if (node.modified) row.classList.add("modified");
  row.style.paddingLeft = (2 + depth * 13) + "px";

  const ex = document.createElement("span");
  ex.className = "expander box";
  ex.textContent = "+";
  if (!node.childCount) ex.style.visibility = "hidden";
  row.appendChild(ex);

  const img = document.createElement("img");
  img.className = "ico";
  img.src = node.constructed ? ICONS.folder : ICONS.doc;
  row.appendChild(img);

  const label = nodeLabelText(node);
  const span = document.createElement("span");
  span.className = "fname";
  span.textContent = label.text;
  row.appendChild(span);
  if (label.scale) {
    const s = document.createElement("span");
    s.className = "fvalue";
    s.textContent = " " + label.scale;
    row.appendChild(s);
  }
  if (state.prefs.showTags) {
    const t = document.createElement("span");
    t.className = "hint"; t.textContent = node.tag; row.appendChild(t);
  }

  wrap.appendChild(row);
  const kids = document.createElement("div");
  kids.className = "tkids hidden";
  wrap.appendChild(kids);
  state.rows.set(node.id, row);

  ex.addEventListener("click", async (e) => {
    e.stopPropagation();
    const hidden = kids.classList.toggle("hidden");
    ex.textContent = hidden ? "+" : "−";
    img.src = hidden ? ICONS.folder : ICONS.folderOpen;
    if (hidden) return;
    if (!kids.dataset.loaded) {
      const res = await api("/api/tree", "POST", { id: node.id, depth: 1 });
      kids.innerHTML = "";
      (res.node.children || []).forEach((c) => kids.appendChild(buildNode(c, depth + 1, 2)));
      kids.dataset.loaded = "1";
    }
  });
  row.addEventListener("click", () => selectNode(node.id, row));
  row.addEventListener("dblclick", () => { selectNode(node.id, row); runCommand("editValue"); });
  row.addEventListener("contextmenu", (e) => { e.preventDefault(); selectNode(node.id, row); openCtx(e.clientX, e.clientY); });

  const budget = state.renderBudget || { n: 0, max: Infinity };
  budget.n += 1;
  if (expandDepth > 0 && node.children && node.children.length && budget.n < budget.max) {
    kids.classList.remove("hidden");
    ex.textContent = "−";
    img.src = ICONS.folderOpen;
    kids.dataset.loaded = "1";
    node.children.forEach((c) => kids.appendChild(buildNode(c, depth + 1, expandDepth - 1)));
  }
  return wrap;
}

async function selectNode(id, row) {
  $$("#mainTree .trow.sel").forEach((n) => n.classList.remove("sel"));
  if (row) row.classList.add("sel");
  try {
    const n = await api(`/api/node/${id}`);
    state.selected = n;
    status(n.path);
    loadDictionary(n.type, n.name);
  } catch (err) {
    status("select failed: " + err.message);
  }
}

/* ------------------------------------------------------------ dictionary */
async function loadDictionary(type, field) {
  const body = $("#dictBody");
  if (!type) {
    body.innerHTML = '<div class="empty">Select a field to see its data dictionary entry.</div>';
    $("#dictTab").textContent = "—";
    return;
  }
  let d;
  try {
    d = await api(`/api/dictionary?type=${encodeURIComponent(type)}&field=${encodeURIComponent(field || "")}`);
  } catch (err) {
    body.innerHTML = `<div class="empty">No dictionary entry for ${escapeHtml(type)}.</div>`;
    return;
  }
  state.dict = d;
  $("#dictTab").textContent = d.type;
  body.innerHTML = "";
  body.appendChild(el("h2", "dh", d.field || d.type));

  const links = el("div", "dict-links");
  ["Validation", "ASN.1", "Parent Types"].forEach((t) => {
    const a = el("a", "lnk", t);
    a.href = "#";
    a.onclick = (e) => { e.preventDefault(); scrollDict(t); };
    links.appendChild(a);
  });
  body.appendChild(links);

  (d.description || []).forEach((p) => body.appendChild(el("p", "", p)));
  if (d.derivation) {
    const p = el("p");
    p.appendChild(el("span", "", "Derivation: "));
    p.appendChild(el("span", "deriv mono", d.derivation));
    body.appendChild(p);
  }
  if (d.conditionality) {
    const p = el("p");
    p.appendChild(el("span", "", "Conditionality: "));
    p.appendChild(document.createTextNode(d.conditionality));
    body.appendChild(p);
  }
  if (d.values && d.values.length) {
    body.appendChild(el("div", "sect plain", "Values:"));
    const pre = el("pre", "values");
    pre.textContent = d.values.map((v) => `${v.code} ${v.text}`).join("\n");
    body.appendChild(pre);
  }
  if (d.validations && d.validations.length) {
    const h = el("div", "sect", "Validations");
    h.id = "dict-validations";
    body.appendChild(h);
    const t = el("table", "vtab");
    const tr = el("tr");
    ["Error Code", "Context", "Severity Level", "Validation Description"]
      .forEach((h2) => tr.appendChild(el("th", "", h2)));
    t.appendChild(tr);
    d.validations.forEach((v) => {
      const r = el("tr");
      r.appendChild(el("td", "", v.code));
      r.appendChild(el("td", "", v.context));
      r.appendChild(el("td", "", v.severity));
      r.appendChild(el("td", "", v.description));
      t.appendChild(r);
    });
    body.appendChild(t);
  }
  const ah = el("div", "sect", d.asn1Title || "ASN.1 Definition");
  ah.id = "dict-asn1";
  body.appendChild(ah);
  const pre = el("pre", "asn1");
  pre.textContent = (d.asn1 || []).join("\n");
  body.appendChild(pre);
  if (d.parents && d.parents.length) {
    const ph = el("div", "sect", "Parent Types");
    ph.id = "dict-parents";
    body.appendChild(ph);
    d.parents.forEach((p) => {
      const a = el("a", "lnk", p);
      a.href = "#";
      a.onclick = (e) => { e.preventDefault(); loadDictionary(p, ""); };
      body.appendChild(a);
      body.appendChild(document.createElement("br"));
    });
  }
  body.appendChild(el("div", "foot", d.footer || "Text extracted from GSM TD57 standard"));
  body.scrollTop = 0;
}

function scrollDict(which) {
  const map = { "Validation": "dict-validations", "ASN.1": "dict-asn1", "Parent Types": "dict-parents" };
  const n = document.getElementById(map[which]);
  if (n) n.scrollIntoView({ block: "start" });
}

/* ---------------------------------------------------------------- helpers */
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
}
function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

/* --------------------------------------------------------------- dialogs */
function dialog(opts) {
  closeMenus();
  closeCtx();
  const layer = $("#modalLayer");
  layer.classList.add("on");
  layer.innerHTML = "";
  const dlg = el("div", "dlg");
  dlg.style.width = (opts.width || 380) + "px";
  const title = el("div", "dlg-title");
  title.appendChild(document.createTextNode(opts.title || ""));
  const x = el("div", "x", "✕");
  title.appendChild(x);
  dlg.appendChild(title);
  const body = el("div", "dlg-body");
  if (typeof opts.content === "string") body.innerHTML = opts.content;
  else if (opts.content) body.appendChild(opts.content);
  dlg.appendChild(body);
  const btns = el("div", "dlg-buttons");
  (opts.buttons || [{ label: "Close" }]).forEach((b) => {
    const btn = el("button", b.primary ? "primary" : "", b.label);
    btn.onclick = () => {
      if (b.onClick && b.onClick(dlg) === false) return;
      if (b.keepOpen) return;
      closeModal();
    };
    btns.appendChild(btn);
  });
  dlg.appendChild(btns);
  layer.appendChild(dlg);
  dlg.style.left = Math.max(20, (window.innerWidth - dlg.offsetWidth) / 2) + "px";
  dlg.style.top = Math.max(40, (window.innerHeight - dlg.offsetHeight) / 2) + "px";
  x.onclick = closeModal;
  return { dlg, body, close: closeModal };
}
function closeModal() {
  const layer = $("#modalLayer");
  layer.classList.remove("on");
  layer.innerHTML = "";
}
function closeTopModal() { if ($("#modalLayer").classList.contains("on")) closeModal(); }

function promptDialog(title, label, value, onOk, opts = {}) {
  const box = el("div");
  const row = el("div", "row");
  row.appendChild(el("label", "", label));
  const input = el("input");
  input.type = "text";
  input.value = value || "";
  row.appendChild(input);
  box.appendChild(row);
  if (opts.hint) box.appendChild(el("div", "muted", opts.hint));
  dialog({
    title, content: box, width: opts.width || 460,
    buttons: [{ label: "OK", primary: true, onClick: () => onOk(input.value) },
              { label: "Cancel" }],
  });
  setTimeout(() => input.focus(), 30);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); if (onOk(input.value) !== false) closeModal(); }
  });
}

function alertBox(title, text, width) {
  dialog({ title, width: width || 460, content: `<div style="white-space:pre-wrap">${escapeHtml(text)}</div>` });
}

/* -------------------------------------------------------------- commands */
async function runCommand(cmd) {
  if (!cmd) return;
  try {
    switch (cmd) {
      case "new": return await cmdNew();
      case "open": return await cmdOpen();
      case "close": return cmdClose();
      case "save": return await cmdSave(false);
      case "saveAs": return await cmdSave(true);
      case "exit": return window.tap3desktop ? window.tap3desktop.quit() : window.close();
      case "refresh": return await refreshAll();
      case "editValue": return await cmdEditValue();
      case "clone": return await cmdClone();
      case "insertChild": return await cmdInsert("child");
      case "insertSibling": return await cmdInsert("sibling");
      case "delete": return await cmdDelete();
      case "copyPath": return cmdCopyPath();
      case "find": return cmdFind();
      case "replace": return cmdReplace();
      case "gotoCall": return cmdGotoCall();
      case "gotoFirst": return await cmdGotoEdge("first");
      case "gotoLast": return await cmdGotoEdge("last");
      case "clearMarks": return await cmdClearMarks();
      case "expandAll": return cmdExpand(true);
      case "collapseAll": return cmdExpand(false);
      case "toggleNav": return togglePane("nav");
      case "toggleDict": return togglePane("dict");
      case "hex": return await cmdHex();
      case "validate": return await cmdValidate("all");
      case "statistics": return await cmdStatistics();
      case "validateNode": return await cmdValidate("node");
      case "rules": return cmdRules();
      case "profile": return await cmdProfileEditor();
      case "genRap": return await cmdGenerateRap();
      case "batchScan": return await cmdBatchScan();
      case "importListing": return await cmdImportListing();
      case "prefs": return cmdPrefs();
      case "about": return cmdAbout();
      case "aboutDict": return alertBox("Data Dictionary Source",
        "All dictionary text, code lists and validation tables are extracted from the\n" +
        "GSM Association TD.57 (TAP3) standard.  Where TD.57 does not define an\n" +
        "operator specific code list the entry refers to the roaming agreement.", 520);
      default:
        if (cmd.startsWith("export:")) return await cmdExport(cmd.split(":")[1]);
    }
  } catch (err) {
    alertBox("Roaming Studio", String(err.message || err));
  }
}

async function cmdNew() {
  const s = await api("/api/open", "POST", { events: 50, seed: Math.floor(Math.random() * 9999) });
  applyState(s);
  await loadNav();
  const ev = (state.nav.children || []).find((c) => c.kind === "events");
  const startId = ev && ev.items.length ? ev.items[0].id : s.root.id;
  await setMainRoot(startId);
  status("New TAP3 file created in memory — use Save As to store it");
}

async function cmdOpen() {
  if (window.tap3desktop) {
    const r = await window.tap3desktop.openFile("");
    if (r && r.ok) { await refreshAll(); status("Opened " + r.path); }
    return;
  }
  promptDialog("Open TAP3 file", "File name:", state.path || "", async (p) => {
    if (!p) return false;
    const s = await api("/api/open", "POST", { path: p });
    applyState(s);
    await loadNav();
    const ev = (state.nav.children || []).find((c) => c.kind === "events");
    const startId = ev && ev.items.length ? ev.items[0].id : s.root.id;
    await setMainRoot(startId);
    status("Opened " + p);
  }, { hint: "TAP3 / RAP / NRTRDE files (*.tap3, *.tap, *.dat, *.rap)" });
}

function cmdClose() {
  state.open = false; state.header = null; state.nav = null; state.selected = null;
  $("#navTree").innerHTML = ""; $("#mainTree").innerHTML = "";
  $("#dictBody").innerHTML = ""; $("#dictTab").textContent = "—";
  setTitle(); status("Ready");
  statusInfo();
}

async function cmdSave(forceAs) {
  if (!state.open) { alertBox("Save", "No document is open."); return; }
  const path = state.path;
  const doSave = async (p) => {
    if (!p) return false;
    const r = await api("/api/save", "POST", { path: p });
    state.path = r.path; setTitle();
    status(`Saved ${r.path} (${r.size} bytes)`);
  };
  // default: overwrite the file that was opened, keeping its exact name
  if (!forceAs && path) { await doSave(path); return; }
  const suggested = path || (state.header && state.header.file) || "output";
  promptDialog("Save As", "File name:", suggested, async (p) => {
    if (!p) return false;
    await doSave(p);
    await refreshAll();
  }, { hint: "The name is used exactly as typed — no extension is added." });
}

async function refreshAll() {
  const s = await api("/api/state");
  if (!s.open) { cmdClose(); return; }
  applyState(s);
  await loadNav();
  const keep = state.rootId || (state.selected && state.selected.id) || s.root.id;
  await setMainRoot(keep);
}

function applyState(s) {
  state.open = !!s.open;
  state.path = s.path || "";
  state.header = s.header || null;
  state.stats = s.stats || null;
  setTitle(); statusInfo();
}

async function cmdEditValue() {
  if (!state.selected) { alertBox("Edit Value", "Select a leaf node first."); return; }
  const n = state.selected;
  if (n.constructed) { alertBox("Edit Value", "Constructed groups cannot be edited directly."); return; }
  const box = el("div", "flexcol");
  const row = el("div", "row");
  row.appendChild(el("label", "", "Value:"));
  const ta = el("textarea");
  ta.rows = 3; ta.value = n.value || "";
  row.appendChild(ta);
  box.appendChild(row);
  box.appendChild(el("div", "muted",
    `${n.name}  (${n.type || "?"})   offset ${n.offset}   ${n.len} byte(s)`));
  dialog({
    title: "Edit Value", width: 520, content: box,
    buttons: [
      { label: "OK", primary: true, onClick: async () => {
          const editedPath = n.path;
          await api("/api/value", "POST", { id: n.id, value: ta.value, mode: "auto" });
          await refreshAll();
          await revealPath(editedPath);
          status("Value updated — the edited field is highlighted (not saved)");
        } },
      { label: "Cancel" },
    ],
  });
  setTimeout(() => { ta.focus(); ta.select(); }, 30);
}

async function cmdClone() {
  if (!state.selected) { alertBox("Clone Node", "Select a node first."); return; }
  await api("/api/clone", "POST", { id: state.selected.id });
  await refreshAll();
  status("Node cloned (not saved)");
}

async function cmdInsert(mode) {
  if (!state.selected) { alertBox("Insert", "Select an element first."); return; }
  const targetId = state.selected.id;          // freeze the target while the dialog is open
  const r = await api(`/api/insert/options?id=${targetId}`);
  const group = r[mode] || { options: [] };
  if (!group.options.length) {
    alertBox("Insert", mode === "child"
      ? `${r.node.type || r.node.name} has no schema children that can be inserted.`
      : "No sibling fields are available for this element.");
    return;
  }
  const box = el("div", "flexcol");
  box.appendChild(el("div", "muted",
    `${r.node.type || r.node.name}${r.node.name ? " · " + r.node.name : ""} — ` +
    (mode === "child" ? "insert into the selected element" : "insert next to the selected element")));
  const row = el("div", "row");
  row.appendChild(el("label", "", "Field:"));
  const sel = el("select");
  group.options.forEach((o, i) => {
    const opt = el("option", "", o.label + (o.present ? "   (already present)" : ""));
    opt.value = String(i);
    if (o.present && !o.repeatable) opt.disabled = true;
    sel.appendChild(opt);
  });
  row.appendChild(sel);
  box.appendChild(row);
  const vrow = el("div", "row");
  vrow.appendChild(el("label", "", "Value:"));
  const val = el("input");
  val.type = "text";
  vrow.appendChild(val);
  box.appendChild(vrow);
  const hint = el("div", "muted", "");
  box.appendChild(hint);
  const update = () => {
    const o = group.options[parseInt(sel.value, 10)] || group.options[0];
    val.disabled = !o.leaf;
    val.placeholder = o.leaf ? "empty = schema default" : "sequence/list is created empty";
    hint.textContent = o.leaf
      ? `Type: ${o.type}${o.alt ? " (alternative " + o.alt + ")" : ""}`
      : `Type: ${o.type} — insert its children afterwards.`;
  };
  sel.onchange = update;
  update();
  dialog({
    title: mode === "child" ? "Insert Child Element" : "Insert Sibling Element",
    width: 600, content: box,
    buttons: [
      { label: "Insert", primary: true, onClick: async () => {
          const o = group.options[parseInt(sel.value, 10)];
          if (!o) return false;
          try {
            const res = await api("/api/insert", "POST",
              { target_id: targetId, mode, field: o.field, alt: o.alt, value: val.value });
            await refreshAll();
            await revealPath(res.node.path);
            status(`Inserted ${res.node.name || res.node.type} — highlighted (not saved)`);
          } catch (err) {
            alertBox("Insert", String(err.message || err));
          }
        } },
      { label: "Cancel" },
    ],
  });
}

async function cmdDelete() {
  if (!state.selected) { alertBox("Delete Node", "Select a node first."); return; }
  await api("/api/delete", "POST", { id: state.selected.id });
  state.selected = null;
  await refreshAll();
  status("Node deleted (not saved)");
}

function cmdCopyPath() {
  if (!state.selected) return;
  navigator.clipboard.writeText(state.selected.path || "").then(
    () => status("Path copied: " + state.selected.path),
    () => alertBox("Copy Path", state.selected.path));
}

function cmdFind() {
  const box = el("div", "flexcol");
  const row = el("div", "row");
  row.appendChild(el("label", "", "Find:"));
  const inp = el("input");
  inp.type = "text"; inp.value = "";
  row.appendChild(inp);
  box.appendChild(row);
  const res = el("div", "dlg-table");
  box.appendChild(res);
  const search = async () => {
    res.innerHTML = "";
    const q = inp.value.trim();
    if (!q) return;
    const r = await api(`/api/search?q=${encodeURIComponent(q)}&limit=200`);
    const t = el("table");
    const head = el("tr");
    ["Path", "Type", "Value"].forEach((h) => head.appendChild(el("th", "", h)));
    t.appendChild(head);
    r.hits.forEach((h) => {
      const tr = el("tr");
      tr.appendChild(el("td", "", h.path));
      tr.appendChild(el("td", "", h.type));
      tr.appendChild(el("td", "", h.value));
      tr.onclick = async () => { closeModal(); await jumpToNode(h.id); };
      t.appendChild(tr);
    });
    res.appendChild(t);
    status(`${r.count} hit(s)`);
  };
  inp.addEventListener("keydown", (e) => { if (e.key === "Enter") search(); });
  dialog({
    title: "Find", width: 720, content: box,
    buttons: [{ label: "Find", primary: true, onClick: search, keepOpen: true }, { label: "Close" }],
  });
  setTimeout(() => inp.focus(), 30);
}

function doFind(q) {
  if (!q) return;
  api(`/api/search?q=${encodeURIComponent(q)}&limit=1`).then(async (r) => {
    if (r.hits.length) { await jumpToNode(r.hits[0].id); status(r.hits[0].path); }
    else status(`No match for '${q}'`);
  });
}

function cmdReplace() {
  const box = el("div", "flexcol");
  const mk = (label) => {
    const row = el("div", "row");
    row.appendChild(el("label", "", label));
    const i = el("input"); i.type = "text";
    row.appendChild(i); box.appendChild(row);
    return i;
  };
  const pat = mk("Find what:");
  const rep = mk("Replace with:");
  const path = mk("Path filter:");
  const log = el("div", "muted", "");
  box.appendChild(log);
  dialog({
    title: "Replace in values", width: 520, content: box,
    buttons: [
      { label: "Replace All", primary: true, onClick: async () => {
          const r = await api("/api/replace", "POST",
            { pattern: pat.value, repl: rep.value, path: path.value, limit: 0 });
          log.textContent = `${r.count} replacement(s) applied.`;
          await refreshAll();
          status(`${r.count} replacement(s) applied — highlighted (not saved)`);
        }, keepOpen: true },
      { label: "Close" },
    ],
  });
}

async function cmdGotoCall() {
  const nav = state.nav;
  if (!nav) { alertBox("Go to call", "Open a TAP3 file first."); return; }
  const events = (nav.children || []).find((c) => c.kind === "events");
  const count = events ? events.items.length : 0;
  promptDialog("Go to call", `Call event (1..${count}):`, "1", async (v) => {
    const idx = parseInt(v, 10);
    if (!events || !isFinite(idx) || idx < 1 || idx > count) {
      alertBox("Go to call", `Enter a number between 1 and ${count}.`);
      return false;
    }
    const item = events.items[idx - 1];
    await setMainRoot(item.id);
    markNav(item.id);
    const row = state.rows.get(item.id);
    if (row) selectNode(item.id, row);
    status(item.label);
  });
}

async function cmdGotoEdge(which) {
  const nav = state.nav;
  const ev = nav && (nav.children || []).find((c) => c.kind === "events");
  if (!ev || !ev.items.length) { alertBox("Go to call", "Open a TAP3 file first."); return; }
  const item = which === "last" ? ev.items[ev.items.length - 1] : ev.items[0];
  if (state.navEnsureAll) state.navEnsureAll();
  await setMainRoot(item.id);
  markNav(item.id);
  const row = state.navRows && state.navRows.get(item.id);
  if (row) row.scrollIntoView({ block: "center" });
  status(`${which === "last" ? "Last" : "First"} call: ${item.label}`);
}

async function cmdClearMarks() {
  await api("/api/clear-marks", "POST", {});
  state.modifiedCount = 0;
  await refreshAll();
  status("Modification highlights cleared");
}

function cmdExpand(all) {
  const host = $("#mainTree");
  const walk = async (container) => {
    const wraps = Array.from(container.children).filter((c) => c.classList.contains("tnode"));
    for (const w of wraps) {
      const row = w.querySelector(".trow");
      const kids = w.querySelector(".tkids");
      const ex = w.querySelector(".expander.box");
      if (!row) continue;
      if (all) {
        if (kids && kids.classList.contains("hidden") && row.dataset.id) ex.click();
        if (kids) await walk(kids);
      } else if (kids) {
        kids.classList.add("hidden");
        if (ex) ex.textContent = "+";
      }
    }
  };
  walk(host).then(() => status(all ? "Expanded" : "Collapsed"));
}

function togglePane(which) {
  const pane = which === "nav" ? $("#leftPane") : $("#rightPane");
  const split = which === "nav" ? $("#splitLeft") : $("#splitRight");
  state.panels[which] = !state.panels[which];
  pane.style.display = state.panels[which] ? "flex" : "none";
  split.style.display = state.panels[which] ? "block" : "none";
  status(`${which === "nav" ? "Navigation pane" : "Data dictionary"} ` +
         `${state.panels[which] ? "shown" : "hidden"}`);
}

async function cmdHex() {
  if (!state.open) { alertBox("Hex View", "Open a file first."); return; }
  const r = await api("/api/hex?offset=0&length=8192");
  const box = el("div");
  const pre = el("pre");
  pre.style.cssText = "max-height:420px;overflow:auto;background:#fff;border:1px solid #999;" +
    "padding:4px;font:11px/1.4 'Courier New',monospace;user-select:text";
  pre.textContent = r.lines.map((l) =>
    `${l.offset.toString(16).padStart(8, "0")}  ${l.hex.padEnd(47, " ")}  ${l.ascii}`).join("\n");
  box.appendChild(pre);
  dialog({ title: `Hex View — ${r.length} bytes`, width: 720, content: box });
}

async function cmdStatistics() {
  if (!state.open) { alertBox("Statistics", "Open a file first."); return; }
  const r = await api("/api/statistics");
  const money = (v) => (v == null ? "—" : `${Number(v).toFixed(r.decimalPlaces)} ${r.currency}`);
  const box = el("div", "flexcol");
  const head = el("div", "",
    `${r.release}   records: ${r.records}   audit count: ${r.auditCount ?? "—"} ` +
    `(${r.countMatches ? "matches" : "MISMATCH"})`);
  box.appendChild(head);
  const wrap = el("div", "dlg-table");
  const t = el("table");
  const hr = el("tr");
  ["Call event type", "Records", "Charge", "Duration (s)"]
    .forEach((h, i) => hr.appendChild(el("th", i ? "num" : "", h)));
  t.appendChild(hr);
  r.rows.forEach((row) => {
    const tr = el("tr");
    tr.appendChild(el("td", "", row.type));
    tr.appendChild(el("td", "num", String(row.count)));
    tr.appendChild(el("td", "num", money(row.chargeScaled)));
    tr.appendChild(el("td", "num", String(row.duration)));
    t.appendChild(tr);
  });
  const total = el("tr");
  total.appendChild(el("td", "", "Total"));
  total.appendChild(el("td", "num", String(r.records)));
  total.appendChild(el("td", "num", money(r.chargeSumScaled)));
  total.appendChild(el("td", "num", String(r.durationSum)));
  t.appendChild(total);
  wrap.appendChild(t);
  box.appendChild(wrap);
  const audit = el("div", "",
    `AuditControlInfo totalCharge: ${money(r.auditTotalChargeScaled)} ` +
    `(${r.auditMatches ? "matches the record sum" : "does NOT match the record sum"})` +
    (r.auditTotalTaxValue != null ? `   totalTaxValue: ${money(r.auditTotalTaxValueScaled)}` : "") +
    (r.auditTotalDiscountValue != null ? `   totalDiscountValue: ${money(r.auditTotalDiscountValueScaled)}` : ""));
  box.appendChild(audit);
  dialog({ title: "File Statistics", width: 720, content: box, buttons: [{ label: "Close" }] });
  status(`Statistics: ${r.records} records, ${money(r.chargeSumScaled)}`);
}

async function cmdValidate(scope) {
  if (!state.open) { alertBox("Validation", "Open a file first."); return; }
  const r = await api("/api/validate", "POST", { profile: state.profile });
  if (r.skipped) {
    alertBox("Validation", r.reason || "Validation is not available for this file type.");
    status("Validation skipped: " + (r.reason || "not a TAP3 file"));
    return;
  }
  const box = el("div", "flexcol");
  const prof = r.profile ? `   profile: ${r.profile}` : "";
  const suppressed = r.suppressed ? `   suppressed: ${r.suppressed}` : "";
  box.appendChild(el("div", "",
    `${r.records} record(s)   ${r.errors} error(s)   ${r.warnings} warning(s)   ` +
    `charge total ${r.chargeSumScaled}${prof}${suppressed}`));
  const wrap = el("div", "dlg-table");
  const t = el("table");
  const head = el("tr");
  ["Severity", "Code", "Validation Description", "Location"]
    .forEach((h) => head.appendChild(el("th", "", h)));
  t.appendChild(head);
  r.findings.forEach((f) => {
    const tr = el("tr");
    const td = el("td");
    td.appendChild(el("span", `badge ${f.severity}`, f.severity));
    tr.appendChild(td);
    tr.appendChild(el("td", "", f.code));
    tr.appendChild(el("td", "", f.message));
    tr.appendChild(el("td", "", f.path));
    tr.onclick = () => { closeModal(); if (f.id) jumpToNode(f.id); };
    t.appendChild(tr);
  });
  wrap.appendChild(t);
  box.appendChild(wrap);
  dialog({
    title: scope === "node" ? "Validate current node" : "Validations — full file",
    width: 900, content: box, buttons: [{ label: "Close" }],
  });
  status(`Validation: ${r.errors} error(s), ${r.warnings} warning(s)`);
}

async function revealPath(path) {
  let r;
  try {
    r = await api(`/api/reveal?path=${encodeURIComponent(path)}`);
  } catch (_e) {
    return false;
  }
  const waitLoaded = async (kids) => {
    for (let i = 0; i < 40 && !kids.dataset.loaded; i++) await new Promise((res) => setTimeout(res, 30));
  };
  for (const aid of r.ancestors || []) {
    const row = state.rows.get(aid);
    if (!row) continue;
    const wrap = row.parentElement;
    const kids = wrap && wrap.querySelector(".tkids");
    if (!kids) continue;
    if (kids.classList.contains("hidden")) {
      const ex = row.querySelector(".expander.box");
      if (ex) ex.click();
      await waitLoaded(kids);
    }
  }
  const row = state.rows.get(r.id);
  if (!row) return false;
  try { state.modifiedCount = (await api("/api/modified")).count; } catch (_e) { /* keep old count */ }
  statusInfo();
  row.classList.add("modified");
  row.scrollIntoView({ block: "center" });
  selectNode(r.id, row);
  return true;
}

async function jumpToNode(id) {
  try {
    const n = await api(`/api/node/${id}`);
    await setMainRoot(id);                       // render the node as tree root
    const row = state.rows.get(id);
    if (row) { row.scrollIntoView({ block: "center" }); selectNode(id, row); }
    status(n.path);
  } catch (err) {
    status("cannot jump: " + err.message);
  }
}

async function cmdProfileEditor() {
  const cat = await api("/api/rules");
  const current = state.profile || {};
  const thresholds = Object.assign({}, cat.thresholds, current.thresholds || {});
  const overrides = current.rules || {};
  const box = el("div", "flexcol");
  box.appendChild(el("div", "muted",
    "Severity overrides mirror TADIG error overrides: off suppresses a finding."));
  const trow = el("div", "row");
  trow.appendChild(el("label", "", "Max duration:"));
  const duration = el("input"); duration.type = "number"; duration.min = "1";
  duration.value = thresholds.maxDurationSeconds;
  trow.appendChild(duration);
  trow.appendChild(el("label", "", "Charge tol.:"));
  const tol = el("input"); tol.type = "number"; tol.min = "0";
  tol.value = thresholds.chargeTolerance;
  trow.appendChild(tol);
  const dupLab = el("label", "", "Duplicates");
  const dup = el("input"); dup.type = "checkbox";
  dup.checked = !!thresholds.duplicateDetection;
  trow.appendChild(dup); trow.appendChild(dupLab);
  box.appendChild(trow);

  const wrap = el("div", "dlg-table");
  wrap.style.maxHeight = "420px";
  const t = el("table");
  const head = el("tr");
  ["Code", "Rule", "Severity"].forEach((h) => head.appendChild(el("th", "", h)));
  t.appendChild(head);
  const selects = {};
  cat.rules.forEach((rule) => {
    const tr = el("tr");
    tr.appendChild(el("td", "", rule.code));
    tr.appendChild(el("td", "", rule.title));
    const td = el("td");
    const sel = el("select");
    const def = el("option", "", `default (${rule.severity})`);
    def.value = "default";
    sel.appendChild(def);
    cat.severities.forEach((sev) => {
      const o = el("option", "", sev);
      o.value = sev;
      sel.appendChild(o);
    });
    sel.value = overrides[rule.code] || "default";
    td.appendChild(sel);
    tr.appendChild(td);
    selects[rule.code] = sel;
    t.appendChild(tr);
  });
  wrap.appendChild(t);
  box.appendChild(wrap);

  const collect = () => {
    const rules = {};
    Object.entries(selects).forEach(([code, sel]) => {
      if (sel.value && sel.value !== "default") rules[code] = sel.value;
    });
    return {
      name: current.name || "custom",
      thresholds: {
        maxDurationSeconds: parseInt(duration.value || "0", 10) || cat.thresholds.maxDurationSeconds,
        chargeTolerance: parseInt(tol.value || "0", 10) || 0,
        duplicateDetection: dup.checked,
      },
      rules,
    };
  };
  const apply = () => {
    state.profile = collect();
    localStorage.setItem("rs.profile", JSON.stringify(state.profile));
    closeModal();
    status(`Validation profile applied (${Object.keys(state.profile.rules).length} override(s))`);
    return true;
  };
  dialog({
    title: "Validation Profile", width: 720, content: box,
    buttons: [
      { label: "Apply & Validate", primary: true, onClick: () => { apply(); setTimeout(() => cmdValidate("all"), 80); } },
      { label: "Apply", onClick: apply },
      { label: "Reset", onClick: () => {
          state.profile = null;
          localStorage.removeItem("rs.profile");
          closeModal();
          status("Validation profile reset to defaults");
        } },
      { label: "Cancel" },
    ],
  });
}

async function cmdImportListing() {
  const box = el("div", "flexcol");
  box.appendChild(el("div", "muted",
    "Rebuilds a schema-valid TAP3.11 skeleton from a listing file written by " +
    "Roaming Studio (File → Export → Listing)."));
  const srow = el("div", "row");
  srow.appendChild(el("label", "", "Listing:"));
  const src = el("input");
  src.type = "text";
  srow.appendChild(src);
  if (window.tap3desktop && window.tap3desktop.pickFile) {
    const b = el("button", "", "Browse...");
    b.onclick = async () => {
      const f = await window.tap3desktop.pickFile({
        title: "Select a listing file",
        filters: [{ name: "Listing", extensions: ["lis", "txt", "csv"] },
                  { name: "All files", extensions: ["*"] }],
      });
      if (f) src.value = f;
    };
    srow.appendChild(b);
  }
  box.appendChild(srow);
  const orow = el("div", "row");
  orow.appendChild(el("label", "", "Output:"));
  const out = el("input");
  out.type = "text";
  out.placeholder = "imported.tap3";
  orow.appendChild(out);
  box.appendChild(orow);
  const log = el("div", "muted", "");
  box.appendChild(log);
  dialog({
    title: "Import Listing", width: 680, content: box,
    buttons: [
      { label: "Import", primary: true, onClick: async () => {
          try {
            const r = await api("/api/import-listing", "POST",
              { path: src.value, out: out.value || "imported.tap3" });
            state.path = r.path;
            setTitle();
            await refreshAll();
            status(`Imported ${r.events} event(s) from listing → ${r.path}`);
            log.textContent = `Written ${r.path} (${r.size} bytes)`;
            alertBox("Listing imported", `${r.events} event(s)
${r.path}`);
          } catch (err) {
            alertBox("Import Listing", String(err.message || err));
          }
        }, keepOpen: true },
      { label: "Close" },
    ],
  });
}

async function cmdBatchScan() {
  const box = el("div", "flexcol");
  const frow = el("div", "row");
  frow.appendChild(el("label", "", "Folder:"));
  const folder = el("input");
  folder.type = "text";
  folder.placeholder = "D:\tap_in";
  frow.appendChild(folder);
  if (window.tap3desktop && window.tap3desktop.pickDirectory) {
    const browse = el("button", "", "Browse...");
    browse.onclick = async () => {
      const dir = await window.tap3desktop.pickDirectory();
      if (dir) folder.value = dir;
    };
    frow.appendChild(browse);
  }
  box.appendChild(frow);

  const prow = el("div", "row");
  prow.appendChild(el("label", "", "Pattern:"));
  const pattern = el("input");
  pattern.type = "text";
  pattern.value = "*";
  prow.appendChild(pattern);
  const useProfile = el("input");
  useProfile.type = "checkbox";
  useProfile.checked = !!state.profile;
  prow.appendChild(useProfile);
  prow.appendChild(el("label", "", "Use validation profile"));
  box.appendChild(prow);

  const outRow = el("div", "row");
  outRow.appendChild(el("label", "", "Export to:"));
  const outPath = el("input");
  outPath.type = "text";
  outPath.placeholder = "scan_report.xlsx";
  outRow.appendChild(outPath);
  box.appendChild(outRow);

  const summary = el("div", "muted", "Choose a folder and press Scan.");
  box.appendChild(summary);
  const wrap = el("div", "dlg-table");
  wrap.style.maxHeight = "340px";
  box.appendChild(wrap);
  let lastRows = [];

  const params = () => ({ paths: [folder.value || "."], pattern: pattern.value || "*",
                          profile: useProfile.checked ? state.profile : null });
  const scan = async () => {
    wrap.innerHTML = "";
    summary.textContent = "Scanning...";
    const res = await api("/api/batch", "POST", params());
    lastRows = res.rows || [];
    const s = res.summary || {};
    summary.textContent = `${s.files} file(s)   ok: ${s.ok}   errors: ${s.with_errors}   ` +
      `failed: ${s.failed}   skipped: ${s.skipped || 0}   records: ${s.records}`;
    const t = el("table");
    const head = el("tr");
    ["File", "Release", "Records", "Errors", "Warn", "Status"]
      .forEach((h, i) => head.appendChild(el("th", i >= 2 && i <= 4 ? "num" : "", h)));
    t.appendChild(head);
    lastRows.forEach((row) => {
      const tr = el("tr");
      tr.appendChild(el("td", "", row.file));
      tr.appendChild(el("td", "", row.release));
      tr.appendChild(el("td", "num", String(row.records)));
      tr.appendChild(el("td", "num", String(row.errors)));
      tr.appendChild(el("td", "num", String(row.warnings)));
      tr.appendChild(el("td", "", row.status));
      tr.title = row.path + (row.message ? "\n" + row.message : "");
      tr.ondblclick = async () => {
        await api("/api/open", "POST", { path: row.path });
        closeModal();
        await refreshAll();
        status("Opened " + row.path);
      };
      t.appendChild(tr);
    });
    wrap.appendChild(t);
  };

  dialog({
    title: "Batch Scan", width: 900, content: box,
    buttons: [
      { label: "Scan", primary: true, onClick: scan, keepOpen: true },
      { label: "Export CSV", onClick: async () => {
          if (!lastRows.length) { alertBox("Batch Scan", "Scan a folder first."); return false; }
          const out = outPath.value || "scan_report.csv";
          const r = await api("/api/batch/export", "POST",
            Object.assign(params(), { out, fmt: "csv" }));
          summary.textContent = `CSV written: ${r.path} (${r.files} files)`;
        }, keepOpen: true },
      { label: "Export Excel", onClick: async () => {
          if (!lastRows.length) { alertBox("Batch Scan", "Scan a folder first."); return false; }
          const out = outPath.value || "scan_report.xlsx";
          const r = await api("/api/batch/export", "POST",
            Object.assign(params(), { out, fmt: "xlsx" }));
          summary.textContent = `Excel written: ${r.path} (${r.files} files)`;
        }, keepOpen: true },
      { label: "Close" },
    ],
  });
}

async function cmdGenerateRap() {
  if (!state.open) { alertBox("RAP", "Open a TAP3 file first."); return; }
  if (state.kind && state.kind !== "tap3") {
    alertBox("RAP", "RAP return files can only be generated from TAP3 files.");
    return;
  }
  let base = (state.header && state.header.file) || "return";
  if (state.path) {
    const dot = state.path.lastIndexOf(".");
    base = dot > state.path.lastIndexOf("/") && dot > state.path.lastIndexOf("\\")
      ? state.path.slice(0, dot) : state.path;
  }
  const box = el("div", "flexcol");
  box.appendChild(el("div", "muted",
    "Builds a RAP1.05 ReturnBatch from the current validation findings: " +
    "invalid records become SevereReturn, file-level problems become FatalReturn."));
  const row = el("div", "row");
  row.appendChild(el("label", "", "Output:"));
  const out = el("input");
  out.type = "text";
  out.value = base + "_RAP.rap";
  row.appendChild(out);
  box.appendChild(row);
  const wrow = el("div", "row");
  const inc = el("input");
  inc.type = "checkbox";
  inc.checked = true;
  wrow.appendChild(inc);
  wrow.appendChild(el("label", "", "Include warnings (otherwise errors only)"));
  box.appendChild(wrow);
  const log = el("div", "muted", "");
  box.appendChild(log);
  dialog({
    title: "Generate RAP Return File", width: 640, content: box,
    buttons: [
      { label: "Generate", primary: true, onClick: async () => {
          try {
            const r = await api("/api/rap", "POST",
              { out: out.value, include_warnings: inc.checked, profile: state.profile });
            log.textContent = `${r.release}: ${r.details} return detail(s), ` +
                              `${r.returned} finding(s) -> ${r.path}`;
            status(`RAP written: ${r.path}`);
            alertBox("RAP generated",
              `${r.release}
Return details: ${r.details}
` +
              `Findings returned: ${r.returned}

${r.path}`);
          } catch (err) {
            alertBox("RAP", String(err.message || err));
          }
        }, keepOpen: true },
      { label: "Close" },
    ],
  });
}

function cmdRules() {
  const rows = [
    ["TAP-001..008", "Batch structure: batchControlInfo, mandatory items, file sequence, release, schema mapping"],
    ["ACC-001..003", "AccountingInfo / localCurrency / tapDecimalPlaces"],
    ["NET-001..003", "UTC offset definitions and references"],
    ["EVT-001..009", "Call event mandatory groups, duration, charge, duplicates"],
    ["TS-001..003", "Timestamp format and UTC offset syntax"],
    ["AUD-001..005", "Audit totals, record count, earliest/latest"],
    ["BCD-001", "IMSI / MSISDN / IMEI BCD syntax"],
  ];
  const box = el("div", "dlg-table");
  const t = el("table");
  const head = el("tr");
  ["Rule group", "Description"].forEach((h) => head.appendChild(el("th", "", h)));
  t.appendChild(head);
  rows.forEach((r) => {
    const tr = el("tr");
    tr.appendChild(el("td", "", r[0]));
    tr.appendChild(el("td", "", r[1]));
    t.appendChild(tr);
  });
  box.appendChild(t);
  dialog({ title: "Validation rules", width: 760, content: box });
}

function cmdPrefs() {
  const box = el("div", "flexcol");
  const mk = (label, key) => {
    const row = el("div", "row");
    const cb = el("input"); cb.type = "checkbox"; cb.checked = !!state.prefs[key];
    cb.onchange = () => {
      state.prefs[key] = cb.checked;
      localStorage.setItem("rs.prefs", JSON.stringify(state.prefs));
    };
    row.appendChild(cb);
    row.appendChild(el("label", "", label));
    box.appendChild(row);
  };
  mk("Show scaled amounts next to charges", "showScale");
  mk("Show ASN.1 tag numbers in the tree", "showTags");
  dialog({
    title: "Preferences", width: 420, content: box,
    buttons: [{ label: "OK", primary: true, onClick: async () => { await refreshAll(); } },
              { label: "Cancel" }],
  });
}

function cmdAbout() {
  alertBox("About Roaming Studio",
    "Roaming Studio — TAP3 / RAP / NRTRDE editor and validator\n" +
    "TD.57 data dictionary · ASN.1 schema driven\n\n" +
    "Renderer: Chromium / Electron\n" +
    "Backend: TAP3 Studio (Python)\n" +
    "Dictionary text extracted from GSM TD57 standard", 520);
}

async function cmdExport(fmt) {
  if (!state.open) { alertBox("Export", "Open a file first."); return; }
  const r = await api(`/api/export?fmt=${fmt}`);
  alertBox("Export", `Written to:\n${r.path}`);
}

/* ---------------------------------------------------------- context menu */
function openCtx(x, y) {
  const layer = $("#ctxLayer");
  layer.classList.add("on");
  layer.innerHTML = "";
  const dd = el("div", "dropdown");
  dd.style.position = "absolute";
  dd.style.left = x + "px"; dd.style.top = y + "px";
  [
    { label: "Edit Value...", cmd: "editValue" },
    { label: "Insert Child...", cmd: "insertChild" },
    { label: "Insert Sibling...", cmd: "insertSibling" },
    { label: "Clone Node", cmd: "clone" },
    { label: "Delete Node", cmd: "delete" },
    { sep: true },
    { label: "Copy Path", cmd: "copyPath" },
    { label: "Find...", cmd: "find" },
  ].forEach((it) => dd.appendChild(menuItem(it)));
  layer.appendChild(dd);
  const w = dd.offsetWidth, h = dd.offsetHeight;
  dd.style.left = Math.max(2, Math.min(x, window.innerWidth - w - 4)) + "px";
  dd.style.top = Math.max(2, Math.min(y, window.innerHeight - h - 4)) + "px";
}

function closeCtx() {
  $("#ctxLayer").classList.remove("on");
  $("#ctxLayer").innerHTML = "";
}

/* ------------------------------------------------------------- splitters */
function initSplitters() {
  const drag = (handle, target, side) => {
    handle.addEventListener("mousedown", (e) => {
      e.preventDefault();
      const startX = e.clientX;
      const startW = target.getBoundingClientRect().width;
      const move = (ev) => {
        let w = side === "left" ? startW + (ev.clientX - startX) : startW - (ev.clientX - startX);
        w = Math.max(120, Math.min(window.innerWidth - 320, w));
        target.style.width = w + "px";
      };
      const up = () => {
        document.removeEventListener("mousemove", move);
        document.removeEventListener("mouseup", up);
      };
      document.addEventListener("mousemove", move);
      document.addEventListener("mouseup", up);
    });
  };
  drag($("#splitLeft"), $("#leftPane"), "left");
  drag($("#splitRight"), $("#rightPane"), "right");
}

/* ------------------------------------------------------ desktop integration */
function initDesktop() {
  const desk = window.tap3desktop;
  if (!desk) return;
  document.body.classList.add("desktop");
  $("#btnMin").onclick = () => desk.minimize();
  $("#btnMax").onclick = () => desk.maximize();
  $("#btnClose").onclick = () => desk.quit();
  desk.info().then((i) => status(`Ready — desktop v${i.version}`)).catch(() => null);
}

/* popups must not survive scrolling, resizing or losing focus */
document.addEventListener("scroll", closeCtx, true);
window.addEventListener("resize", closeCtx);
window.addEventListener("blur", closeCtx);

/* --------------------------------------------------------------- keyboard */
document.addEventListener("keydown", (e) => {
  const ctrl = e.ctrlKey || e.metaKey;
  if (ctrl && e.key.toLowerCase() === "o") { e.preventDefault(); runCommand("open"); }
  else if (ctrl && e.key.toLowerCase() === "s") { e.preventDefault(); runCommand("save"); }
  else if (ctrl && e.key.toLowerCase() === "f") { e.preventDefault(); runCommand("find"); }
  else if (ctrl && e.key.toLowerCase() === "h") { e.preventDefault(); runCommand("replace"); }
  else if (ctrl && e.key.toLowerCase() === "g") { e.preventDefault(); runCommand("gotoCall"); }
  else if (ctrl && e.key.toLowerCase() === "r") { e.preventDefault(); runCommand("refresh"); }
  else if (ctrl && e.key === "End") { e.preventDefault(); runCommand("gotoLast"); }
  else if (ctrl && e.key === "Home") { e.preventDefault(); runCommand("gotoFirst"); }
  else if (e.key === "F2") { e.preventDefault(); runCommand("editValue"); }
  else if (e.key === "F5") { e.preventDefault(); runCommand("validate"); }
  else if (e.key === "Delete") {
    if (state.selected && document.activeElement === document.body) runCommand("delete");
  }
});

/* --------------------------------------------------------------- startup */
async function boot() {
  buildMenubar();
  buildToolbar();
  initSplitters();
  initDesktop();
  try {
    const s = await api("/api/state");
    if (s.open) {
      applyState(s);
      await loadNav();
      const ev = (state.nav.children || []).find((c) => c.kind === "events");
      const startId = ev && ev.items.length ? ev.items[0].id : s.root.id;
      await setMainRoot(startId);
    } else {
      status("Ready — File > Open, or File > New");
    }
  } catch (err) {
    status("startup error: " + err.message);
  }
}

boot();
