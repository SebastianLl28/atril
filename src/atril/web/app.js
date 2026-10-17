// Atril visual app. No dependencies and no build step.
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
// Side names match the JSON fields of the API.
const SIDES = ["original", "referencia"];
const PAGE_LIMIT = 35;

// Common task combinations; each checkbox can be adjusted afterwards.
const PRESETS = {
  improve: { traducir: "", mejorar_lectura: true, comentarios: false, contexto: false, resumen: false },
  translate: { traducir: "es", mejorar_lectura: true, comentarios: false, contexto: false, resumen: false },
  "translate-enrich": { traducir: "es", mejorar_lectura: true, comentarios: true, contexto: true, resumen: true },
  enrich: { traducir: "", mejorar_lectura: true, comentarios: true, contexto: true, resumen: true },
};

const state = {
  p: null,            // project detail from the backend
  words: {},          // side → words per page
  sel: { original: null, referencia: null },  // [start, end], 1-based
  lead: null,         // side where the selection started; the other is deduced from the map
  adjusted: false,    // the user corrected the other side's selection by hand
  last: {},           // side → last plain-clicked page (base for shift+click)
  hits: { original: [], referencia: [] },
  tocSide: "original",
  partEdited: false,
  viewer: null,       // { side, n } in the large view
  pdfs: [],           // PDFs in ~/Documents/books, for the new-project dialog
  printing: null,     // part about to be printed
};

// ---------------------------------------------------------------- utilities
async function api(path, options = {}) {
  const r = await fetch(path, {
    headers: options.body ? { "Content-Type": "application/json" } : {},
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!r.ok) {
    let msg = r.statusText;
    try { const d = await r.json(); msg = typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail); } catch {}
    throw new Error(msg);
  }
  return r.json();
}

function notify(text) { $("#status").textContent = text; }

async function busy(text, fn) {
  notify(text);
  document.body.style.cursor = "progress";
  try { const r = await fn(); notify(""); return r; }
  catch (e) { notify(""); alert(e.message); throw e; }
  finally { document.body.style.cursor = ""; }
}

const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const other = (side) => (side === "original" ? "referencia" : "original");
const fmtRange = (r) => (r ? (r[0] === r[1] ? `${r[0]}` : `${r[0]}–${r[1]}`) : "—");
const inside = (r, n) => r && n >= r[0] && n <= r[1];
const sameRange = (a, b) => (!a && !b) || (a && b && a[0] === b[0] && a[1] === b[1]);

function slug(text) {
  return text.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 50);
}

// ---------------------------------------------------------------- map
// originalRange / referenceRange mirror mapping.original_range / mapping.reference_range
// in mapping.py: if one changes, change the other.
function originalRange(start, end) {
  const pages = state.p.mapa.slice(start - 1, end);
  return pages.length ? [Math.min(...pages), Math.max(...pages)] : null;
}

function referenceRange(start, end) {
  const pages = [];
  state.p.mapa.forEach((o, i) => { if (o >= start && o <= end) pages.push(i + 1); });
  return pages.length ? [pages[0], pages[pages.length - 1]] : null;
}

function deduced(side, r) {
  if (!r || !state.p.referencia) return null;
  return side === "original" ? referenceRange(...r) : originalRange(...r);
}

// ---------------------------------------------------------------- projects
async function loadProjects(choose) {
  const list = await api("/api/proyectos");
  const sel = $("#project-select");
  sel.innerHTML = '<option value="">— proyecto —</option>' +
    list.map((p) => `<option value="${p.slug}">${esc(p.titulo)} (${p.slug})</option>`).join("");
  const saved = choose || new URLSearchParams(location.search).get("p") ||
    localStorage.getItem("atril.proyecto");
  if (saved && list.some((p) => p.slug === saved)) {
    sel.value = saved;
    await openProject(saved);
  }
}

async function openProject(projectSlug) {
  if (!projectSlug) {
    $("#workspace").hidden = true; $("#empty").hidden = false; return;
  }
  const p = await busy("Abriendo…", () => api(`/api/proyectos/${projectSlug}`));
  localStorage.setItem("atril.proyecto", projectSlug);
  Object.assign(state, {
    p, words: {}, sel: { original: null, referencia: null }, lead: null, adjusted: false,
    last: {}, hits: { original: [], referencia: [] }, tocSide: "original", partEdited: false,
  });
  $("#empty").hidden = true;
  $("#workspace").hidden = false;
  $("#workspace").classList.toggle("single", !p.referencia);
  $("#exported").hidden = true;
  setTask(PRESETS.improve);
  setSources({});
  $("#instructions").value = "";
  $("#results").innerHTML = "";
  $("#search").value = "";
  for (const side of SIDES) drawPanel(side);
  drawToc();
  drawParts();
  refresh();
  // Word counts extract the whole book's text: fetched separately so they don't block.
  for (const side of SIDES) {
    if (!p[side]) continue;
    api(`/api/proyectos/${p.slug}/${side}/palabras`).then((w) => {
      if (state.p === p) { state.words[side] = w; drawSelection(); }
    });
  }
}

// ---------------------------------------------------------------- thumbnail panels
function drawPanel(side) {
  const panel = $(`.panel[data-side="${side}"]`);
  const info = state.p[side];
  const container = $(".pages", panel);
  container.innerHTML = "";
  if (!info) return;
  $(".name", panel).textContent = `${side === "original" ? "Documento" : "Otra versión"} · ${info.idioma.toUpperCase()} · ${info.nombre}`;
  $(".name", panel).title = info.pdf;
  $(".goto", panel).max = info.paginas;
  const frag = document.createDocumentFragment();
  for (let n = 1; n <= info.paginas; n++) {
    const fig = document.createElement("figure");
    fig.className = "page";
    fig.dataset.n = n;
    const img = document.createElement("img");
    img.loading = "lazy";
    img.decoding = "async";
    img.alt = `página ${n}`;
    img.style.aspectRatio = `1 / ${info.proporcion}`;
    img.src = `/api/proyectos/${state.p.slug}/${side}/pagina/${n}`;
    const cap = document.createElement("figcaption");
    fig.append(img, cap);
    frag.append(fig);
  }
  container.append(frag);
  labels(side);
}

function labels(side) {
  const map = state.p.mapa;
  const anchors = state.p.anclas;
  for (const fig of $$(`.panel[data-side="${side}"] .page`)) {
    const n = +fig.dataset.n;
    let txt = `p. ${n}`;
    if (side === "referencia" && map.length) txt += ` <span class="eq">↔ ${map[n - 1]}</span>`;
    fig.querySelector("figcaption").innerHTML = txt;
    fig.classList.toggle("anchored", side === "referencia" && n in anchors);
  }
}

function highlight() {
  for (const side of SIDES) {
    const suggested = state.lead && side !== state.lead ? deduced(state.lead, state.sel[state.lead]) : null;
    const hits = new Set(state.hits[side]);
    for (const fig of $$(`.panel[data-side="${side}"] .page`)) {
      const n = +fig.dataset.n;
      fig.classList.toggle("sel", inside(state.sel[side], n));
      fig.classList.toggle("suggested", state.adjusted && inside(suggested, n));
      fig.classList.toggle("hit", hits.has(n));
    }
  }
}

function goTo(side, n, block = "center") {
  const fig = $(`.panel[data-side="${side}"] .page[data-n="${n}"]`);
  if (fig) fig.scrollIntoView({ block, behavior: "smooth" });
}

// ---------------------------------------------------------------- selection
function click(side, n, extend) {
  const base = state.last[side];
  const r = extend && base ? [Math.min(base, n), Math.max(base, n)] : [n, n];
  if (!extend) state.last[side] = n;
  if (state.lead === null || side === state.lead || !state.p.referencia) {
    state.lead = side;
    state.sel[side] = r;
    state.sel[other(side)] = deduced(side, r);
    state.adjusted = false;
    const o = state.sel[other(side)];
    if (o) goTo(other(side), o[0], "start");
  } else {
    // Click on the other panel: manual adjustment of what the map deduced.
    state.sel[side] = r;
    state.adjusted = !sameRange(r, deduced(state.lead, state.sel[state.lead]));
  }
  refresh();
}

function pickRange(side, r, title) {
  state.lead = side;
  state.sel[side] = r;
  state.sel[other(side)] = deduced(side, r);
  state.adjusted = false;
  state.last[side] = r[0];
  goTo(side, r[0], "start");
  const o = state.sel[other(side)];
  if (o) goTo(other(side), o[0], "start");
  if (title && !state.partEdited) {
    $("#part-id").value = slug(title);
    $("#part-title").value = title;
  }
  refresh();
}

function clearSelection() {
  Object.assign(state, { sel: { original: null, referencia: null }, lead: null, adjusted: false, last: {} });
  refresh();
}

function wordsIn(side) {
  const r = state.sel[side];
  const w = state.words[side];
  if (!r || !w) return null;
  return w.slice(r[0] - 1, r[1]).reduce((a, b) => a + b, 0);
}

function drawSelection() {
  const rows = [];
  for (const side of SIDES) {
    const info = state.p[side];
    if (!info) continue;
    const r = state.sel[side];
    const n = r ? r[1] - r[0] + 1 : 0;
    const w = wordsIn(side);
    const note = side !== state.lead && state.lead
      ? (state.adjusted ? ' <span class="adjusted">(ajustado a mano)</span>' : " (según el mapa)") : "";
    rows.push(`<p><span class="side">${info.idioma.toUpperCase()}</span> p. ${fmtRange(r)}` +
      (r ? ` · ${n} pág${n === 1 ? "" : "s"}${w !== null ? ` · ~${w.toLocaleString("es")} palabras` : ""}` : "") +
      `${note}</p>`);
  }
  $("#selection").innerHTML = rows.join("") ||
    '<p class="note">Clic en una página para empezar; mayús+clic extiende el rango.</p>';
  const r = state.sel.original;
  const n = r ? r[1] - r[0] + 1 : 0;
  const warning = $("#warning");
  warning.hidden = n <= PAGE_LIMIT;
  warning.textContent = `La parte tiene ${n} páginas del documento: más de ${PAGE_LIMIT} suele ser demasiado para una sola sesión de /libro. Conviene partirla.`;
  $("#btn-anchor").hidden = !state.adjusted;
}

function drawAnchors() {
  const anchors = Object.entries(state.p.anclas);
  $("#anchors").innerHTML = !state.p.referencia ? "" : anchors.length
    ? "Anclas: " + anchors.map(([r, o]) =>
        `<span>${r}→${o}<button type="button" data-ref="${r}" title="Quitar ancla">×</button></span>`).join("")
    : '<p class="note">Sin anclas manuales.</p>';
}

function refresh() {
  highlight();
  drawSelection();
  drawAnchors();
}

async function saveAnchor() {
  const ref = state.sel.referencia, orig = state.sel.original;
  if (!ref || !orig) return;
  const p = state.p;
  let res = await busy("Recalculando el mapa…",
    () => api(`/api/proyectos/${p.slug}/anclas`, { method: "POST", body: { referencia: ref[0], original: orig[0] } }));
  if (ref[1] !== ref[0] || orig[1] !== orig[0]) {
    res = await busy("Recalculando el mapa…",
      () => api(`/api/proyectos/${p.slug}/anclas`, { method: "POST", body: { referencia: ref[1], original: orig[1] } }));
  }
  Object.assign(p, res);
  state.adjusted = false;  // the current selection stays as it is
  labels("referencia");
  refresh();
}

async function removeAnchor(ref) {
  const p = state.p;
  const res = await busy("Recalculando el mapa…",
    () => api(`/api/proyectos/${p.slug}/anclas/${ref}`, { method: "DELETE" }));
  Object.assign(p, res);
  labels("referencia");
  refresh();
}

// ---------------------------------------------------------------- table of contents
function drawToc() {
  const sides = SIDES.filter((s) => state.p[s] && state.p[s].indice.length);
  $("#toc-tabs").innerHTML = sides.length > 1 ? sides.map((s) =>
    `<button type="button" data-side="${s}" class="${s === state.tocSide ? "active" : ""}">${state.p[s].idioma.toUpperCase()}</button>`).join("") : "";
  if (!sides.includes(state.tocSide)) state.tocSide = sides[0] || "original";
  const info = state.p[state.tocSide];
  const entries = info ? info.indice : [];
  const note = $("#toc-note");
  note.hidden = !(info && info.indice_detectado);
  note.textContent = entries.length
    ? "Este PDF no trae índice: títulos detectados por tamaño de letra."
    : "Este PDF no trae índice: marca las páginas con clic y mayús+clic.";
  $("#toc").innerHTML = entries.length ? entries.map(([level, title, page], i) =>
    `<li class="n${level}" data-i="${i}" style="padding-left:${(level - 1) * 0.9 + 0.3}em" title="${esc(title)}">` +
    `<span>${esc(title)}</span><span class="page">${page}</span></li>`).join("")
    : "";
}

function entryRange(side, i) {
  // From the entry's page up to just before the next entry of the same or a higher level.
  const entries = state.p[side].indice;
  const [level, , start] = entries[i];
  let end = state.p[side].paginas;
  for (let k = i + 1; k < entries.length; k++) {
    if (entries[k][0] <= level && entries[k][2] > start) { end = entries[k][2] - 1; break; }
  }
  return [start, Math.max(start, end)];
}

// ---------------------------------------------------------------- search
async function search(term) {
  const p = state.p;
  state.hits = { original: [], referencia: [] };
  if (term.length < 2) { $("#results").innerHTML = ""; highlight(); return; }
  await busy("Buscando…", async () => {
    for (const side of SIDES) {
      if (p[side]) state.hits[side] = await api(`/api/proyectos/${p.slug}/${side}/buscar?q=${encodeURIComponent(term)}`);
    }
  });
  $("#results").innerHTML = SIDES.filter((s) => p[s]).map((s) => {
    const h = state.hits[s];
    return `<button type="button" data-side="${s}" ${h.length ? "" : "disabled"}>${p[s].idioma.toUpperCase()}: ${h.length} página${h.length === 1 ? "" : "s"}${h.length ? " · ir a la siguiente" : ""}</button>`;
  }).join("");
  highlight();
}

const nextHit = {};
function goToNext(side) {
  const h = state.hits[side];
  if (!h.length) return;
  nextHit[side] = ((nextHit[side] ?? -1) + 1) % h.length;
  goTo(side, h[nextHit[side]]);
}

// ---------------------------------------------------------------- task and sources
function readTask() {
  const lang = $("#output-lang").value;
  return {
    traducir: lang === "other" ? ($("#other-lang").value.trim() || null) : (lang || null),
    mejorar_lectura: $("#t-improve").checked,
    comentarios: $("#t-comments").checked,
    contexto: $("#t-context").checked,
    resumen: $("#t-summary").checked,
  };
}

function setTask(t) {
  const lang = t.traducir || "";
  const known = ["", "es", "en"].includes(lang);
  $("#output-lang").value = known ? lang : "other";
  $("#other-lang").value = known ? "" : lang;
  $("#other-lang").hidden = known;
  $("#t-improve").checked = t.mejorar_lectura ?? true;
  $("#t-comments").checked = !!t.comentarios;
  $("#t-context").checked = !!t.contexto;
  $("#t-summary").checked = !!t.resumen;
  markPreset();
}

function markPreset() {
  const t = readTask();
  for (const b of $$("#presets button")) {
    const p = PRESETS[b.dataset.preset];
    b.classList.toggle("active", Object.keys(p).every((k) => (p[k] || null) === (t[k] || null)));
  }
}

function taskSummary(t) {
  if (!t) return "";
  const items = [t.traducir ? `traducir → ${t.traducir}` : "mismo idioma"];
  if (t.mejorar_lectura) items.push("lectura");
  if (t.comentarios) items.push("comentarios");
  if (t.contexto) items.push("contexto");
  if (t.resumen) items.push("resumen");
  return items.join(" · ");
}

function pdfRow(f = {}) {
  const div = document.createElement("div");
  div.className = "pdf-row";
  const options = state.pdfs.map((x) =>
    `<option value="${esc(x.ruta)}" ${x.solo_imagenes ? "disabled" : ""}>${esc(x.nombre)}${x.solo_imagenes ? " (solo imágenes)" : ` (${x.paginas} p.)`}</option>`).join("");
  div.innerHTML = `<select aria-label="PDF de apoyo">${options}</select>` +
    `<input placeholder="p. ej. 3-8" aria-label="Páginas" pattern="\\d+(-\\d+)?"><button type="button" title="Quitar">×</button>`;
  if (f.pdf) $("select", div).value = f.pdf;
  else { const usable = state.pdfs.find((x) => !x.solo_imagenes); if (usable) $("select", div).value = usable.ruta; }
  if (f.paginas) $("input", div).value = f.paginas;
  $("#s-pdfs").append(div);
  countSources();
}

function readSources() {
  const pdfs = $$("#s-pdfs .pdf-row").map((d) => {
    const m = $("input", d).value.trim().match(/^(\d+)(?:-(\d+))?$/);
    return m ? { pdf: $("select", d).value, paginas: [+m[1], +(m[2] || m[1])] } : null;
  });
  if (pdfs.includes(null)) throw new Error("Escribe el rango de páginas de cada PDF de apoyo (p. ej. 3-8).");
  return {
    notas: $("#s-notes").value,
    enlaces: $("#s-links").value.split("\n").map((e) => e.trim()).filter(Boolean),
    pdfs,
  };
}

function setSources(f = {}) {
  $("#s-notes").value = "";  // notes are not stored in libro.json
  $("#s-links").value = (f.enlaces || []).join("\n");
  $("#s-pdfs").innerHTML = "";
  for (const x of f.pdfs || []) pdfRow({ pdf: x.pdf, paginas: x.paginas });
  countSources();
}

function countSources() {
  const n = (+!!$("#s-notes").value.trim()) +
    $("#s-links").value.split("\n").filter((e) => e.trim()).length + $$("#s-pdfs .pdf-row").length;
  $("#sources-count").textContent = n ? `(${n})` : "";
}

async function loadPdfs() {
  if (!state.pdfs.length) state.pdfs = await api("/api/pdfs");
  return state.pdfs;
}

// ---------------------------------------------------------------- export
function drawParts() {
  const p = state.p;
  const base = (id) => `/api/proyectos/${p.slug}/partes/${encodeURIComponent(id)}/pdf`;
  $("#parts").innerHTML = p.partes.length ? [...p.partes].reverse().map((x) => {
    const i = p.partes.indexOf(x);
    const links = [
      x.pdfs.carta ? `<a href="${base(x.id)}?tipo=carta" target="_blank">PDF</a>` : "",
      x.pdfs["2x1"] ? `<a href="${base(x.id)}?tipo=2x1" target="_blank">2 por hoja</a>` : "",
      x.pdfs.carta ? `<button type="button" data-print="${i}">Imprimir</button>` : "",
    ].join("");
    return `<li><b>${esc(x.titulo || x.id)}</b>` +
      `<div class="meta">${esc(x.id)} · p. ${x.original}${x.referencia ? ` ↔ ${x.referencia}` : ""}` +
      `${x.fecha ? ` · ${x.fecha}` : ""}${x.paginas_pdf ? ` · ${x.paginas_pdf} págs de PDF` : ""}</div>` +
      `<span class="status ${x.estado}">${x.estado}</span> <span class="task-chip">${esc(taskSummary(x.tarea || (x.idioma_destino ? { traducir: x.idioma_destino, mejorar_lectura: true } : null)))}</span>` +
      `<div class="buttons"><button type="button" data-pick="${i}" title="Volver a elegir estas páginas">Elegir</button>${links}</div></li>`;
  }).join("") : '<li class="note">Todavía no hay partes exportadas.</li>';
}

async function openPrintDialog(i) {
  const x = state.p.partes[i];
  state.printing = x;
  $("#pr-part").textContent = x.titulo || x.id;
  $("#pr-kind").value = "carta";
  $("#pr-kind").querySelector('[value="2x1"]').disabled = !x.pdfs["2x1"];
  $("#pr-copies").value = 1;
  $("#pr-pages").value = "";
  $("#dlg-print").showModal();
  try {
    const printers = await api("/api/impresoras");
    $("#pr-printer").textContent = printers.predeterminada || "predeterminada del sistema";
  } catch { $("#pr-printer").textContent = "predeterminada del sistema"; }
}

async function sendPrint(ev) {
  ev.preventDefault();
  const x = state.printing;
  const body = { tipo: $("#pr-kind").value, copias: +$("#pr-copies").value || 1,
                 paginas: $("#pr-pages").value.trim() || null };
  const r = await busy("Enviando a la impresora…", () =>
    api(`/api/proyectos/${state.p.slug}/partes/${encodeURIComponent(x.id)}/imprimir`, { method: "POST", body }));
  $("#dlg-print").close();
  notify(r.mensaje || "Enviado a la impresora");
}

function pickPart(i) {
  const x = state.p.partes[i];
  const r = x.original.split("-").map(Number);
  pickRange("original", [r[0], r[1] ?? r[0]]);
  if (x.referencia && state.p.referencia) {
    const q = x.referencia.split("-").map(Number);
    state.sel.referencia = [q[0], q[1] ?? q[0]];
    state.adjusted = !sameRange(state.sel.referencia, deduced("original", state.sel.original));
    goTo("referencia", q[0], "start");
  }
  $("#part-id").value = x.id;
  $("#part-title").value = x.titulo || "";
  if (x.tarea) setTask(x.tarea);
  else if (x.idioma_destino) setTask({ traducir: x.idioma_destino, mejorar_lectura: true });
  loadPdfs().then(() => setSources(x.fuentes || {}));
  state.partEdited = true;
  refresh();
}

async function exportPart(ev) {
  ev.preventDefault();
  const p = state.p;
  if (!state.sel.original && !state.sel.referencia) { alert("Elige primero las páginas."); return; }
  let sources;
  try { sources = readSources(); } catch (e) { alert(e.message); return; }
  const body = {
    parte: $("#part-id").value.trim(),
    original: state.sel.original,
    referencia: p.referencia ? state.sel.referencia : null,
    instrucciones: $("#instructions").value,
    titulo_parte: $("#part-title").value.trim() || null,
    tarea: readTask(),
    fuentes: sources,
  };
  if (p.partes.some((x) => x.id === body.parte) &&
      !confirm(`La parte «${body.parte}» ya existe. ¿Volver a exportarla? Se reemplaza contexto.md y figuras/; salida/ no se toca.`)) return;
  const r = await busy("Exportando…", () => api(`/api/proyectos/${p.slug}/exportar`, { method: "POST", body }));
  p.partes = r.partes;
  drawParts();
  const box = $("#exported");
  box.hidden = false;
  box.innerHTML = `<b>Paquete listo</b> · ${r.figuras} figuras<br>${esc(r.contexto)}` +
    `<code id="command">${esc(r.comando)}</code><button type="button" id="btn-copy">Copiar comando</button>`;
}

// ---------------------------------------------------------------- large view
function openViewer(side, n) {
  const info = state.p[side];
  n = Math.min(Math.max(1, n), info.paginas);
  state.viewer = { side, n };
  $("#viewer-img").src = `/api/proyectos/${state.p.slug}/${side}/pagina/${n}?ancho=1100`;
  $("#viewer-title").textContent = `${info.idioma.toUpperCase()} · p. ${n} de ${info.paginas}`;
  const dlg = $("#dlg-viewer");
  if (!dlg.open) dlg.showModal();
}

// ---------------------------------------------------------------- new project
async function newProjectDialog() {
  $("#dlg-new").showModal();
  notify("Revisando los PDFs…");
  state.pdfs = await api("/api/pdfs");
  notify("");
  const options = state.pdfs.map((f) => f.solo_imagenes
    ? `<option value="${esc(f.ruta)}" disabled>${esc(f.nombre)} — solo imágenes, no se acepta</option>`
    : `<option value="${esc(f.ruta)}">${esc(f.nombre)} (${f.paginas} p.)</option>`).join("");
  $("#n-original").innerHTML = '<option value="">— elige un PDF —</option>' + options;
  $("#n-reference").innerHTML = '<option value="">— ninguna —</option>' + options;
}

async function createProject(ev) {
  ev.preventDefault();
  const body = {
    slug: $("#n-slug").value.trim(),
    titulo: $("#n-title").value.trim(),
    original: $("#n-original").value,
    referencia: $("#n-reference").value || null,
    idioma_original: $("#n-original-lang").value.trim() || "en",
    idioma_referencia: $("#n-reference-lang").value.trim() || "es",
  };
  const p = await busy(body.referencia ? "Creando y calculando el mapa…" : "Creando…",
    () => api("/api/proyectos", { method: "POST", body }));
  $("#dlg-new").close();
  await loadProjects(p.slug);
}

// ---------------------------------------------------------------- events
$("#project-select").addEventListener("change", (e) => openProject(e.target.value));
$("#btn-new").addEventListener("click", newProjectDialog);
$("#n-cancel").addEventListener("click", () => $("#dlg-new").close());
$("#new-form").addEventListener("submit", createProject);
$("#n-original").addEventListener("change", (e) => {
  if (!$("#n-title").value) $("#n-title").value = e.target.selectedOptions[0].text.replace(/ \(\d+ p\.\)$/, "").replace(/\.pdf$/i, "").split("/").pop();
  if (!$("#n-slug").value) $("#n-slug").value = slug($("#n-title").value);
});

$("#thumb-size").addEventListener("input", (e) => {
  document.documentElement.style.setProperty("--thumb", `${e.target.value}px`);
  localStorage.setItem("atril.tamano", e.target.value);
});
const thumbSize = localStorage.getItem("atril.tamano");
if (thumbSize) { $("#thumb-size").value = thumbSize; document.documentElement.style.setProperty("--thumb", `${thumbSize}px`); }

for (const panel of $$(".panel")) {
  const side = panel.dataset.side;
  $(".pages", panel).addEventListener("click", (e) => {
    const fig = e.target.closest(".page");
    if (fig) click(side, +fig.dataset.n, e.shiftKey);
  });
  $(".pages", panel).addEventListener("dblclick", (e) => {
    const fig = e.target.closest(".page");
    if (fig) openViewer(side, +fig.dataset.n);
  });
  $(".goto", panel).addEventListener("change", (e) => { if (e.target.value) goTo(side, +e.target.value); });
}
// Keeps shift+click from selecting text on the page.
document.addEventListener("mousedown", (e) => { if (e.shiftKey && e.target.closest(".page")) e.preventDefault(); });

$("#toc-tabs").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (b) { state.tocSide = b.dataset.side; drawToc(); }
});
$("#toc").addEventListener("click", (e) => {
  const li = e.target.closest("li[data-i]");
  if (!li) return;
  const side = state.tocSide, i = +li.dataset.i;
  pickRange(side, entryRange(side, i), state.p[side].indice[i][1]);
});

$("#search-form").addEventListener("submit", (e) => { e.preventDefault(); search($("#search").value.trim()); });
$("#search").addEventListener("search", (e) => { if (!e.target.value) search(""); });
$("#results").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (b) goToNext(b.dataset.side);
});

$("#btn-clear").addEventListener("click", clearSelection);
$("#btn-anchor").addEventListener("click", saveAnchor);
$("#anchors").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-ref]");
  if (b) removeAnchor(b.dataset.ref);
});

$("#presets").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-preset]");
  if (b) setTask(PRESETS[b.dataset.preset]);
});
$("#output-lang").addEventListener("change", (e) => {
  $("#other-lang").hidden = e.target.value !== "other";
  markPreset();
});
for (const id of ["#other-lang", "#t-improve", "#t-comments", "#t-context", "#t-summary"]) {
  $(id).addEventListener("change", markPreset);
}
$("#s-add-pdf").addEventListener("click", async () => { await loadPdfs(); pdfRow(); $("#sources").open = true; });
$("#s-pdfs").addEventListener("click", (e) => {
  if (e.target.matches(".pdf-row button")) { e.target.closest(".pdf-row").remove(); countSources(); }
});
$("#s-notes").addEventListener("input", countSources);
$("#s-links").addEventListener("input", countSources);
for (const id of ["#part-id", "#part-title"]) {
  $(id).addEventListener("input", () => { state.partEdited = true; });
}
$("#export-form").addEventListener("submit", exportPart);
$("#exported").addEventListener("click", async (e) => {
  if (e.target.id !== "btn-copy") return;
  await navigator.clipboard.writeText($("#command").textContent);
  e.target.textContent = "¡Copiado!";
});
$("#parts").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.pick !== undefined) pickPart(+b.dataset.pick);
  if (b.dataset.print !== undefined) openPrintDialog(+b.dataset.print);
});
$("#print-form").addEventListener("submit", sendPrint);
$("#pr-cancel").addEventListener("click", () => $("#dlg-print").close());

$("#dlg-viewer").addEventListener("click", (e) => {
  const step = e.target.dataset?.step;
  if (step) openViewer(state.viewer.side, state.viewer.n + +step);
  else if (e.target.id === "viewer-close" || e.target === $("#dlg-viewer")) $("#dlg-viewer").close();
});
document.addEventListener("keydown", (e) => {
  if (!$("#dlg-viewer").open) return;
  if (e.key === "ArrowRight") openViewer(state.viewer.side, state.viewer.n + 1);
  if (e.key === "ArrowLeft") openViewer(state.viewer.side, state.viewer.n - 1);
});

loadProjects().catch((e) => notify(e.message));
