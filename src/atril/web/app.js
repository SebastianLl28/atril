// Atril · app visual. Sin dependencias ni paso de build.
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const LADOS = ["original", "referencia"];
const LIMITE_PAGINAS = 35;

// Combinaciones frecuentes de la tarea; después se puede ajustar cada casilla.
const PRESETS = {
  mejorar: { traducir: "", mejorar_lectura: true, comentarios: false, contexto: false, resumen: false },
  traducir: { traducir: "es", mejorar_lectura: true, comentarios: false, contexto: false, resumen: false },
  "traducir-enriquecer": { traducir: "es", mejorar_lectura: true, comentarios: true, contexto: true, resumen: true },
  enriquecer: { traducir: "", mejorar_lectura: true, comentarios: true, contexto: true, resumen: true },
};

const estado = {
  p: null,            // proyecto (detalle del backend)
  palabras: {},       // lado → palabras por página
  sel: { original: null, referencia: null },  // [desde, hasta] 1-based
  guia: null,         // lado donde empezó la selección; el otro se deduce del mapa
  ajustado: false,    // el usuario corrigió a mano la selección del otro lado
  ultimo: {},         // lado → última página con clic simple (base del mayús+clic)
  hits: { original: [], referencia: [] },
  indiceLado: "original",
  parteEditada: false,
  vista: null,        // { lado, n } en la vista grande
  pdfs: [],           // PDFs de ~/Documents/books, para el diálogo de proyecto nuevo
  imprimir: null,     // parte que se va a imprimir
};

// ---------------------------------------------------------------- utilidades
async function api(ruta, opciones = {}) {
  const r = await fetch(ruta, {
    headers: opciones.body ? { "Content-Type": "application/json" } : {},
    ...opciones,
    body: opciones.body ? JSON.stringify(opciones.body) : undefined,
  });
  if (!r.ok) {
    let msg = r.statusText;
    try { const d = await r.json(); msg = typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail); } catch {}
    throw new Error(msg);
  }
  return r.json();
}

function avisar(texto) { $("#estado").textContent = texto; }

async function ocupado(texto, fn) {
  avisar(texto);
  document.body.style.cursor = "progress";
  try { const r = await fn(); avisar(""); return r; }
  catch (e) { avisar(""); alert(e.message); throw e; }
  finally { document.body.style.cursor = ""; }
}

const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const otro = (lado) => (lado === "original" ? "referencia" : "original");
const rango = (r) => (r ? (r[0] === r[1] ? `${r[0]}` : `${r[0]}–${r[1]}`) : "—");
const dentro = (r, n) => r && n >= r[0] && n <= r[1];
const iguales = (a, b) => (!a && !b) || (a && b && a[0] === b[0] && a[1] === b[1]);

function slug(texto) {
  return texto.normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 50);
}

// ---------------------------------------------------------------- mapa (igual que mapa.py)
function rangoOriginal(desde, hasta) {
  const pags = estado.p.mapa.slice(desde - 1, hasta);
  return pags.length ? [Math.min(...pags), Math.max(...pags)] : null;
}

function rangoReferencia(desde, hasta) {
  const pags = [];
  estado.p.mapa.forEach((o, i) => { if (o >= desde && o <= hasta) pags.push(i + 1); });
  return pags.length ? [pags[0], pags[pags.length - 1]] : null;
}

function deducido(lado, r) {
  if (!r || !estado.p.referencia) return null;
  return lado === "original" ? rangoReferencia(...r) : rangoOriginal(...r);
}

// ---------------------------------------------------------------- proyectos
async function cargarProyectos(elegir) {
  const lista = await api("/api/proyectos");
  const sel = $("#proyecto");
  sel.innerHTML = '<option value="">— proyecto —</option>' +
    lista.map((p) => `<option value="${p.slug}">${esc(p.titulo)} (${p.slug})</option>`).join("");
  const guardado = elegir || new URLSearchParams(location.search).get("p") ||
    localStorage.getItem("atril.proyecto");
  if (guardado && lista.some((p) => p.slug === guardado)) {
    sel.value = guardado;
    await abrir(guardado);
  }
}

async function abrir(slugProyecto) {
  if (!slugProyecto) {
    $("#trabajo").hidden = true; $("#vacio").hidden = false; return;
  }
  const p = await ocupado("Abriendo…", () => api(`/api/proyectos/${slugProyecto}`));
  localStorage.setItem("atril.proyecto", slugProyecto);
  Object.assign(estado, {
    p, palabras: {}, sel: { original: null, referencia: null }, guia: null, ajustado: false,
    ultimo: {}, hits: { original: [], referencia: [] }, indiceLado: "original", parteEditada: false,
  });
  $("#vacio").hidden = true;
  $("#trabajo").hidden = false;
  $("#trabajo").classList.toggle("solo", !p.referencia);
  $("#exportado").hidden = true;
  ponerTarea(PRESETS.mejorar);
  ponerFuentes({});
  $("#instrucciones").value = "";
  $("#resultados").innerHTML = "";
  $("#buscar").value = "";
  for (const lado of LADOS) dibujarPanel(lado);
  dibujarIndice();
  dibujarPartes();
  actualizar();
  // El conteo de palabras extrae el texto de todo el libro: se pide aparte para no frenar.
  for (const lado of LADOS) {
    if (!p[lado]) continue;
    api(`/api/proyectos/${p.slug}/${lado}/palabras`).then((w) => {
      if (estado.p === p) { estado.palabras[lado] = w; dibujarSeleccion(); }
    });
  }
}

// ---------------------------------------------------------------- paneles de miniaturas
function dibujarPanel(lado) {
  const panel = $(`.panel[data-lado="${lado}"]`);
  const info = estado.p[lado];
  const cont = $(".paginas", panel);
  cont.innerHTML = "";
  if (!info) return;
  $(".nombre", panel).textContent = `${lado === "original" ? "Documento" : "Otra versión"} · ${info.idioma.toUpperCase()} · ${info.nombre}`;
  $(".nombre", panel).title = info.pdf;
  $(".ir", panel).max = info.paginas;
  const frag = document.createDocumentFragment();
  for (let n = 1; n <= info.paginas; n++) {
    const fig = document.createElement("figure");
    fig.className = "pag";
    fig.dataset.n = n;
    const img = document.createElement("img");
    img.loading = "lazy";
    img.decoding = "async";
    img.alt = `página ${n}`;
    img.style.aspectRatio = `1 / ${info.proporcion}`;
    img.src = `/api/proyectos/${estado.p.slug}/${lado}/pagina/${n}`;
    const cap = document.createElement("figcaption");
    fig.append(img, cap);
    frag.append(fig);
  }
  cont.append(frag);
  etiquetas(lado);
}

function etiquetas(lado) {
  const mapa = estado.p.mapa;
  const anclas = estado.p.anclas;
  for (const fig of $$(`.panel[data-lado="${lado}"] .pag`)) {
    const n = +fig.dataset.n;
    let txt = `p. ${n}`;
    if (lado === "referencia" && mapa.length) txt += ` <span class="eq">↔ ${mapa[n - 1]}</span>`;
    fig.querySelector("figcaption").innerHTML = txt;
    fig.classList.toggle("ancla", lado === "referencia" && n in anclas);
  }
}

function marcar() {
  for (const lado of LADOS) {
    const sug = estado.guia && lado !== estado.guia ? deducido(estado.guia, estado.sel[estado.guia]) : null;
    const hits = new Set(estado.hits[lado]);
    for (const fig of $$(`.panel[data-lado="${lado}"] .pag`)) {
      const n = +fig.dataset.n;
      fig.classList.toggle("sel", dentro(estado.sel[lado], n));
      fig.classList.toggle("sug", estado.ajustado && dentro(sug, n));
      fig.classList.toggle("hit", hits.has(n));
    }
  }
}

function irA(lado, n, bloque = "center") {
  const fig = $(`.panel[data-lado="${lado}"] .pag[data-n="${n}"]`);
  if (fig) fig.scrollIntoView({ block: bloque, behavior: "smooth" });
}

// ---------------------------------------------------------------- selección
function clic(lado, n, extender) {
  const base = estado.ultimo[lado];
  const r = extender && base ? [Math.min(base, n), Math.max(base, n)] : [n, n];
  if (!extender) estado.ultimo[lado] = n;
  if (estado.guia === null || lado === estado.guia || !estado.p.referencia) {
    estado.guia = lado;
    estado.sel[lado] = r;
    estado.sel[otro(lado)] = deducido(lado, r);
    estado.ajustado = false;
    const o = estado.sel[otro(lado)];
    if (o) irA(otro(lado), o[0], "start");
  } else {
    // Clic en el otro panel: ajuste manual de lo que dedujo el mapa.
    estado.sel[lado] = r;
    estado.ajustado = !iguales(r, deducido(estado.guia, estado.sel[estado.guia]));
  }
  actualizar();
}

function elegirRango(lado, r, titulo) {
  estado.guia = lado;
  estado.sel[lado] = r;
  estado.sel[otro(lado)] = deducido(lado, r);
  estado.ajustado = false;
  estado.ultimo[lado] = r[0];
  irA(lado, r[0], "start");
  const o = estado.sel[otro(lado)];
  if (o) irA(otro(lado), o[0], "start");
  if (titulo && !estado.parteEditada) {
    $("#parte").value = slug(titulo);
    $("#titulo-parte").value = titulo;
  }
  actualizar();
}

function limpiar() {
  Object.assign(estado, { sel: { original: null, referencia: null }, guia: null, ajustado: false, ultimo: {} });
  actualizar();
}

function palabrasDe(lado) {
  const r = estado.sel[lado];
  const w = estado.palabras[lado];
  if (!r || !w) return null;
  return w.slice(r[0] - 1, r[1]).reduce((a, b) => a + b, 0);
}

function dibujarSeleccion() {
  const filas = [];
  for (const lado of LADOS) {
    const info = estado.p[lado];
    if (!info) continue;
    const r = estado.sel[lado];
    const n = r ? r[1] - r[0] + 1 : 0;
    const w = palabrasDe(lado);
    const nota = lado !== estado.guia && estado.guia
      ? (estado.ajustado ? ' <span class="ajustado">(ajustado a mano)</span>' : " (según el mapa)") : "";
    filas.push(`<p><span class="lado">${info.idioma.toUpperCase()}</span> p. ${rango(r)}` +
      (r ? ` · ${n} pág${n === 1 ? "" : "s"}${w !== null ? ` · ~${w.toLocaleString("es")} palabras` : ""}` : "") +
      `${nota}</p>`);
  }
  $("#seleccion").innerHTML = filas.join("") ||
    '<p class="nota">Clic en una página para empezar; mayús+clic extiende el rango.</p>';
  const r = estado.sel.original;
  const n = r ? r[1] - r[0] + 1 : 0;
  const aviso = $("#aviso");
  aviso.hidden = n <= LIMITE_PAGINAS;
  aviso.textContent = `La parte tiene ${n} páginas del documento: más de ${LIMITE_PAGINAS} suele ser demasiado para una sola sesión de /libro. Conviene partirla.`;
  $("#btn-ancla").hidden = !estado.ajustado;
}

function dibujarAnclas() {
  const anclas = Object.entries(estado.p.anclas);
  $("#anclas").innerHTML = !estado.p.referencia ? "" : anclas.length
    ? "Anclas: " + anclas.map(([r, o]) =>
        `<span>${r}→${o}<button type="button" data-ref="${r}" title="Quitar ancla">×</button></span>`).join("")
    : '<p class="nota">Sin anclas manuales.</p>';
}

function actualizar() {
  marcar();
  dibujarSeleccion();
  dibujarAnclas();
}

async function guardarAncla() {
  const ref = estado.sel.referencia, orig = estado.sel.original;
  if (!ref || !orig) return;
  const p = estado.p;
  let res = await ocupado("Recalculando el mapa…",
    () => api(`/api/proyectos/${p.slug}/anclas`, { method: "POST", body: { referencia: ref[0], original: orig[0] } }));
  if (ref[1] !== ref[0] || orig[1] !== orig[0]) {
    res = await ocupado("Recalculando el mapa…",
      () => api(`/api/proyectos/${p.slug}/anclas`, { method: "POST", body: { referencia: ref[1], original: orig[1] } }));
  }
  Object.assign(p, res);
  estado.ajustado = false;  // la selección actual queda como está
  etiquetas("referencia");
  actualizar();
}

async function quitarAncla(ref) {
  const p = estado.p;
  const res = await ocupado("Recalculando el mapa…",
    () => api(`/api/proyectos/${p.slug}/anclas/${ref}`, { method: "DELETE" }));
  Object.assign(p, res);
  etiquetas("referencia");
  actualizar();
}

// ---------------------------------------------------------------- índice
function dibujarIndice() {
  const lados = LADOS.filter((l) => estado.p[l] && estado.p[l].indice.length);
  $("#pestanas-indice").innerHTML = lados.length > 1 ? lados.map((l) =>
    `<button type="button" data-lado="${l}" class="${l === estado.indiceLado ? "activa" : ""}">${estado.p[l].idioma.toUpperCase()}</button>`).join("") : "";
  if (!lados.includes(estado.indiceLado)) estado.indiceLado = lados[0] || "original";
  const info = estado.p[estado.indiceLado];
  const entradas = info ? info.indice : [];
  const nota = $("#indice-nota");
  nota.hidden = !(info && info.indice_detectado);
  nota.textContent = entradas.length
    ? "Este PDF no trae índice: títulos detectados por tamaño de letra."
    : "Este PDF no trae índice: marca las páginas con clic y mayús+clic.";
  $("#indice").innerHTML = entradas.length ? entradas.map(([nivel, titulo, pag], i) =>
    `<li class="n${nivel}" data-i="${i}" style="padding-left:${(nivel - 1) * 0.9 + 0.3}em" title="${esc(titulo)}">` +
    `<span>${esc(titulo)}</span><span class="pag">${pag}</span></li>`).join("")
    : "";
}

function rangoEntrada(lado, i) {
  // Desde la página de la entrada hasta antes de la siguiente del mismo nivel o superior.
  const entradas = estado.p[lado].indice;
  const [nivel, , desde] = entradas[i];
  let hasta = estado.p[lado].paginas;
  for (let k = i + 1; k < entradas.length; k++) {
    if (entradas[k][0] <= nivel && entradas[k][2] > desde) { hasta = entradas[k][2] - 1; break; }
  }
  return [desde, Math.max(desde, hasta)];
}

// ---------------------------------------------------------------- búsqueda
async function buscar(termino) {
  const p = estado.p;
  estado.hits = { original: [], referencia: [] };
  if (termino.length < 2) { $("#resultados").innerHTML = ""; marcar(); return; }
  await ocupado("Buscando…", async () => {
    for (const lado of LADOS) {
      if (p[lado]) estado.hits[lado] = await api(`/api/proyectos/${p.slug}/${lado}/buscar?q=${encodeURIComponent(termino)}`);
    }
  });
  $("#resultados").innerHTML = LADOS.filter((l) => p[l]).map((l) => {
    const h = estado.hits[l];
    return `<button type="button" data-lado="${l}" ${h.length ? "" : "disabled"}>${p[l].idioma.toUpperCase()}: ${h.length} página${h.length === 1 ? "" : "s"}${h.length ? " · ir a la siguiente" : ""}</button>`;
  }).join("");
  marcar();
}

const siguienteHit = {};
function irSiguiente(lado) {
  const h = estado.hits[lado];
  if (!h.length) return;
  siguienteHit[lado] = ((siguienteHit[lado] ?? -1) + 1) % h.length;
  irA(lado, h[siguienteHit[lado]]);
}

// ---------------------------------------------------------------- tarea y fuentes
function leerTarea() {
  const idioma = $("#idioma-salida").value;
  return {
    traducir: idioma === "otro" ? ($("#idioma-otro").value.trim() || null) : (idioma || null),
    mejorar_lectura: $("#t-mejorar").checked,
    comentarios: $("#t-comentarios").checked,
    contexto: $("#t-contexto").checked,
    resumen: $("#t-resumen").checked,
  };
}

function ponerTarea(t) {
  const idioma = t.traducir || "";
  const conocido = ["", "es", "en"].includes(idioma);
  $("#idioma-salida").value = conocido ? idioma : "otro";
  $("#idioma-otro").value = conocido ? "" : idioma;
  $("#idioma-otro").hidden = conocido;
  $("#t-mejorar").checked = t.mejorar_lectura ?? true;
  $("#t-comentarios").checked = !!t.comentarios;
  $("#t-contexto").checked = !!t.contexto;
  $("#t-resumen").checked = !!t.resumen;
  marcarPreset();
}

function marcarPreset() {
  const t = leerTarea();
  for (const b of $$("#presets button")) {
    const p = PRESETS[b.dataset.preset];
    b.classList.toggle("activa", Object.keys(p).every((k) => (p[k] || null) === (t[k] || null)));
  }
}

function resumenTarea(t) {
  if (!t) return "";
  const partes = [t.traducir ? `traducir → ${t.traducir}` : "mismo idioma"];
  if (t.mejorar_lectura) partes.push("lectura");
  if (t.comentarios) partes.push("comentarios");
  if (t.contexto) partes.push("contexto");
  if (t.resumen) partes.push("resumen");
  return partes.join(" · ");
}

function filaPdf(f = {}) {
  const div = document.createElement("div");
  div.className = "fila-pdf";
  const opciones = estado.pdfs.map((x) =>
    `<option value="${esc(x.ruta)}" ${x.solo_imagenes ? "disabled" : ""}>${esc(x.nombre)}${x.solo_imagenes ? " (solo imágenes)" : ` (${x.paginas} p.)`}</option>`).join("");
  div.innerHTML = `<select aria-label="PDF de apoyo">${opciones}</select>` +
    `<input placeholder="p. ej. 3-8" aria-label="Páginas" pattern="\\d+(-\\d+)?"><button type="button" title="Quitar">×</button>`;
  if (f.pdf) $("select", div).value = f.pdf;
  else { const libre = estado.pdfs.find((x) => !x.solo_imagenes); if (libre) $("select", div).value = libre.ruta; }
  if (f.paginas) $("input", div).value = f.paginas;
  $("#f-pdfs").append(div);
  contarFuentes();
}

function leerFuentes() {
  const pdfs = $$("#f-pdfs .fila-pdf").map((d) => {
    const m = $("input", d).value.trim().match(/^(\d+)(?:-(\d+))?$/);
    return m ? { pdf: $("select", d).value, paginas: [+m[1], +(m[2] || m[1])] } : null;
  });
  if (pdfs.includes(null)) throw new Error("Escribe el rango de páginas de cada PDF de apoyo (p. ej. 3-8).");
  return {
    notas: $("#f-notas").value,
    enlaces: $("#f-enlaces").value.split("\n").map((e) => e.trim()).filter(Boolean),
    pdfs,
  };
}

function ponerFuentes(f = {}) {
  $("#f-notas").value = "";  // las notas no se guardan en libro.json, solo si había
  $("#f-enlaces").value = (f.enlaces || []).join("\n");
  $("#f-pdfs").innerHTML = "";
  for (const x of f.pdfs || []) filaPdf({ pdf: x.pdf, paginas: x.paginas });
  contarFuentes();
}

function contarFuentes() {
  const n = (+!!$("#f-notas").value.trim()) +
    $("#f-enlaces").value.split("\n").filter((e) => e.trim()).length + $$("#f-pdfs .fila-pdf").length;
  $("#fuentes-cuenta").textContent = n ? `(${n})` : "";
}

async function cargarPdfs() {
  if (!estado.pdfs.length) estado.pdfs = await api("/api/pdfs");
  return estado.pdfs;
}

// ---------------------------------------------------------------- exportar
function dibujarPartes() {
  const p = estado.p;
  const base = (id) => `/api/proyectos/${p.slug}/partes/${encodeURIComponent(id)}/pdf`;
  $("#partes").innerHTML = p.partes.length ? [...p.partes].reverse().map((x) => {
    const i = p.partes.indexOf(x);
    const enlaces = [
      x.pdfs.carta ? `<a href="${base(x.id)}?tipo=carta" target="_blank">PDF</a>` : "",
      x.pdfs["2x1"] ? `<a href="${base(x.id)}?tipo=2x1" target="_blank">2 por hoja</a>` : "",
      x.pdfs.carta ? `<button type="button" data-imprimir="${i}">Imprimir</button>` : "",
    ].join("");
    return `<li><b>${esc(x.titulo || x.id)}</b>` +
      `<div class="meta">${esc(x.id)} · p. ${x.original}${x.referencia ? ` ↔ ${x.referencia}` : ""}` +
      `${x.fecha ? ` · ${x.fecha}` : ""}${x.paginas_pdf ? ` · ${x.paginas_pdf} págs de PDF` : ""}</div>` +
      `<span class="estado ${x.estado}">${x.estado}</span> <span class="tarea-chip">${esc(resumenTarea(x.tarea || (x.idioma_destino ? { traducir: x.idioma_destino, mejorar_lectura: true } : null)))}</span>` +
      `<div class="botones"><button type="button" data-elegir="${i}" title="Volver a elegir estas páginas">Elegir</button>${enlaces}</div></li>`;
  }).join("") : '<li class="nota">Todavía no hay partes exportadas.</li>';
}

async function abrirImpresion(i) {
  const x = estado.p.partes[i];
  estado.imprimir = x;
  $("#i-parte").textContent = x.titulo || x.id;
  $("#i-tipo").value = "carta";
  $("#i-tipo").querySelector('[value="2x1"]').disabled = !x.pdfs["2x1"];
  $("#i-copias").value = 1;
  $("#i-paginas").value = "";
  $("#dlg-imprimir").showModal();
  try {
    const imp = await api("/api/impresoras");
    $("#i-impresora").textContent = imp.predeterminada || "predeterminada del sistema";
  } catch { $("#i-impresora").textContent = "predeterminada del sistema"; }
}

async function mandarImpresion(ev) {
  ev.preventDefault();
  const x = estado.imprimir;
  const cuerpo = { tipo: $("#i-tipo").value, copias: +$("#i-copias").value || 1,
                   paginas: $("#i-paginas").value.trim() || null };
  const r = await ocupado("Enviando a la impresora…", () =>
    api(`/api/proyectos/${estado.p.slug}/partes/${encodeURIComponent(x.id)}/imprimir`, { method: "POST", body: cuerpo }));
  $("#dlg-imprimir").close();
  avisar(r.mensaje || "Enviado a la impresora");
}

function elegirParte(i) {
  const x = estado.p.partes[i];
  const r = x.original.split("-").map(Number);
  elegirRango("original", [r[0], r[1] ?? r[0]]);
  if (x.referencia && estado.p.referencia) {
    const q = x.referencia.split("-").map(Number);
    estado.sel.referencia = [q[0], q[1] ?? q[0]];
    estado.ajustado = !iguales(estado.sel.referencia, deducido("original", estado.sel.original));
    irA("referencia", q[0], "start");
  }
  $("#parte").value = x.id;
  $("#titulo-parte").value = x.titulo || "";
  if (x.tarea) ponerTarea(x.tarea);
  else if (x.idioma_destino) ponerTarea({ traducir: x.idioma_destino, mejorar_lectura: true });
  cargarPdfs().then(() => ponerFuentes(x.fuentes || {}));
  estado.parteEditada = true;
  actualizar();
}

async function exportar(ev) {
  ev.preventDefault();
  const p = estado.p;
  if (!estado.sel.original && !estado.sel.referencia) { alert("Elige primero las páginas."); return; }
  let fuentes;
  try { fuentes = leerFuentes(); } catch (e) { alert(e.message); return; }
  const cuerpo = {
    parte: $("#parte").value.trim(),
    original: estado.sel.original,
    referencia: p.referencia ? estado.sel.referencia : null,
    instrucciones: $("#instrucciones").value,
    titulo_parte: $("#titulo-parte").value.trim() || null,
    tarea: leerTarea(),
    fuentes,
  };
  if (p.partes.some((x) => x.id === cuerpo.parte) &&
      !confirm(`La parte «${cuerpo.parte}» ya existe. ¿Volver a exportarla? Se reemplaza contexto.md y figuras/; salida/ no se toca.`)) return;
  const r = await ocupado("Exportando…", () => api(`/api/proyectos/${p.slug}/exportar`, { method: "POST", body: cuerpo }));
  p.partes = r.partes;
  dibujarPartes();
  const caja = $("#exportado");
  caja.hidden = false;
  caja.innerHTML = `<b>Paquete listo</b> · ${r.figuras} figuras<br>${esc(r.contexto)}` +
    `<code id="comando">${esc(r.comando)}</code><button type="button" id="btn-copiar">Copiar comando</button>`;
}

// ---------------------------------------------------------------- vista grande
function abrirVista(lado, n) {
  const info = estado.p[lado];
  n = Math.min(Math.max(1, n), info.paginas);
  estado.vista = { lado, n };
  $("#vista-img").src = `/api/proyectos/${estado.p.slug}/${lado}/pagina/${n}?ancho=1100`;
  $("#vista-titulo").textContent = `${info.idioma.toUpperCase()} · p. ${n} de ${info.paginas}`;
  const dlg = $("#dlg-vista");
  if (!dlg.open) dlg.showModal();
}

// ---------------------------------------------------------------- nuevo proyecto
async function dialogoNuevo() {
  $("#dlg-nuevo").showModal();
  avisar("Revisando los PDFs…");
  estado.pdfs = await api("/api/pdfs");
  avisar("");
  const opciones = estado.pdfs.map((f) => f.solo_imagenes
    ? `<option value="${esc(f.ruta)}" disabled>${esc(f.nombre)} — solo imágenes, no se acepta</option>`
    : `<option value="${esc(f.ruta)}">${esc(f.nombre)} (${f.paginas} p.)</option>`).join("");
  $("#n-original").innerHTML = '<option value="">— elige un PDF —</option>' + opciones;
  $("#n-referencia").innerHTML = '<option value="">— ninguna —</option>' + opciones;
}

async function crearProyecto(ev) {
  ev.preventDefault();
  const cuerpo = {
    slug: $("#n-slug").value.trim(),
    titulo: $("#n-titulo").value.trim(),
    original: $("#n-original").value,
    referencia: $("#n-referencia").value || null,
    idioma_original: $("#n-idioma-original").value.trim() || "en",
    idioma_referencia: $("#n-idioma-referencia").value.trim() || "es",
  };
  const p = await ocupado(cuerpo.referencia ? "Creando y calculando el mapa…" : "Creando…",
    () => api("/api/proyectos", { method: "POST", body: cuerpo }));
  $("#dlg-nuevo").close();
  await cargarProyectos(p.slug);
}

// ---------------------------------------------------------------- eventos
$("#proyecto").addEventListener("change", (e) => abrir(e.target.value));
$("#btn-nuevo").addEventListener("click", dialogoNuevo);
$("#n-cancelar").addEventListener("click", () => $("#dlg-nuevo").close());
$("#form-nuevo").addEventListener("submit", crearProyecto);
$("#n-original").addEventListener("change", (e) => {
  if (!$("#n-titulo").value) $("#n-titulo").value = e.target.selectedOptions[0].text.replace(/ \(\d+ p\.\)$/, "").replace(/\.pdf$/i, "").split("/").pop();
  if (!$("#n-slug").value) $("#n-slug").value = slug($("#n-titulo").value);
});

$("#tamano").addEventListener("input", (e) => {
  document.documentElement.style.setProperty("--mini", `${e.target.value}px`);
  localStorage.setItem("atril.tamano", e.target.value);
});
const tamano = localStorage.getItem("atril.tamano");
if (tamano) { $("#tamano").value = tamano; document.documentElement.style.setProperty("--mini", `${tamano}px`); }

for (const panel of $$(".panel")) {
  const lado = panel.dataset.lado;
  $(".paginas", panel).addEventListener("click", (e) => {
    const fig = e.target.closest(".pag");
    if (fig) clic(lado, +fig.dataset.n, e.shiftKey);
  });
  $(".paginas", panel).addEventListener("dblclick", (e) => {
    const fig = e.target.closest(".pag");
    if (fig) abrirVista(lado, +fig.dataset.n);
  });
  $(".ir", panel).addEventListener("change", (e) => { if (e.target.value) irA(lado, +e.target.value); });
}
// Evita que mayús+clic seleccione texto en la página.
document.addEventListener("mousedown", (e) => { if (e.shiftKey && e.target.closest(".pag")) e.preventDefault(); });

$("#pestanas-indice").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (b) { estado.indiceLado = b.dataset.lado; dibujarIndice(); }
});
$("#indice").addEventListener("click", (e) => {
  const li = e.target.closest("li[data-i]");
  if (!li) return;
  const lado = estado.indiceLado, i = +li.dataset.i;
  elegirRango(lado, rangoEntrada(lado, i), estado.p[lado].indice[i][1]);
});

$("#form-buscar").addEventListener("submit", (e) => { e.preventDefault(); buscar($("#buscar").value.trim()); });
$("#buscar").addEventListener("search", (e) => { if (!e.target.value) buscar(""); });
$("#resultados").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (b) irSiguiente(b.dataset.lado);
});

$("#btn-limpiar").addEventListener("click", limpiar);
$("#btn-ancla").addEventListener("click", guardarAncla);
$("#anclas").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-ref]");
  if (b) quitarAncla(b.dataset.ref);
});

$("#presets").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-preset]");
  if (b) ponerTarea(PRESETS[b.dataset.preset]);
});
$("#idioma-salida").addEventListener("change", (e) => {
  $("#idioma-otro").hidden = e.target.value !== "otro";
  marcarPreset();
});
for (const id of ["#idioma-otro", "#t-mejorar", "#t-comentarios", "#t-contexto", "#t-resumen"]) {
  $(id).addEventListener("change", marcarPreset);
}
$("#f-agregar-pdf").addEventListener("click", async () => { await cargarPdfs(); filaPdf(); $("#fuentes").open = true; });
$("#f-pdfs").addEventListener("click", (e) => {
  if (e.target.matches(".fila-pdf button")) { e.target.closest(".fila-pdf").remove(); contarFuentes(); }
});
$("#f-notas").addEventListener("input", contarFuentes);
$("#f-enlaces").addEventListener("input", contarFuentes);
for (const id of ["#parte", "#titulo-parte"]) {
  $(id).addEventListener("input", () => { estado.parteEditada = true; });
}
$("#form-exportar").addEventListener("submit", exportar);
$("#exportado").addEventListener("click", async (e) => {
  if (e.target.id !== "btn-copiar") return;
  await navigator.clipboard.writeText($("#comando").textContent);
  e.target.textContent = "¡Copiado!";
});
$("#partes").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.elegir !== undefined) elegirParte(+b.dataset.elegir);
  if (b.dataset.imprimir !== undefined) abrirImpresion(+b.dataset.imprimir);
});
$("#form-imprimir").addEventListener("submit", mandarImpresion);
$("#i-cancelar").addEventListener("click", () => $("#dlg-imprimir").close());

$("#dlg-vista").addEventListener("click", (e) => {
  const paso = e.target.dataset?.paso;
  if (paso) abrirVista(estado.vista.lado, estado.vista.n + +paso);
  else if (e.target.id === "vista-cerrar" || e.target === $("#dlg-vista")) $("#dlg-vista").close();
});
document.addEventListener("keydown", (e) => {
  if (!$("#dlg-vista").open) return;
  if (e.key === "ArrowRight") abrirVista(estado.vista.lado, estado.vista.n + 1);
  if (e.key === "ArrowLeft") abrirVista(estado.vista.lado, estado.vista.n - 1);
});

cargarProyectos().catch((e) => avisar(e.message));
