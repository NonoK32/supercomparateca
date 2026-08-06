"use strict";

// En producción (HTTPS, detrás de Traefik) la API va en el mismo origen bajo
// /api (sin CORS). En desarrollo se publica en el puerto 8000 del host.
const API_BASE =
  location.protocol === "https:" ? "/api" : `http://${location.hostname}:8000`;

let token = localStorage.getItem("token") || null;

const $ = (id) => document.getElementById(id);

function mensaje(texto, esError = false) {
  const el = $("mensaje");
  el.textContent = texto;
  el.className = esError ? "error" : "";
  setTimeout(() => el.classList.add("hidden"), 3500);
}

async function api(path, { method = "GET", json, form } = {}) {
  const headers = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  let body;
  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form !== undefined) {
    body = form;
  }
  const resp = await fetch(API_BASE + path, { method, headers, body });
  if (resp.status === 401) {
    // Token ausente/expirado: cerramos sesión y volvemos al login.
    cerrarSesion();
    throw new Error("Sesión expirada, vuelve a iniciar sesión");
  }
  if (resp.status === 204) return null;
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(textoError(data.detail, resp.status));
  }
  return data;
}

// El `detail` de FastAPI es una cadena en los errores propios, pero una lista
// de {loc, msg} en los de validación de Pydantic. Sin distinguirlos, el usuario
// veía el JSON en crudo, comillas incluidas.
function textoError(detail, status) {
  if (!detail) return `Error ${status}`;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join(". ");
  }
  return JSON.stringify(detail);
}

// ---- Autenticación ----
async function mostrarApp() {
  $("vista-auth").classList.add("hidden");
  $("vista-app").classList.remove("hidden");
  $("btn-logout").classList.remove("hidden");
  $("tabs").classList.remove("hidden");
  document.body.classList.remove("sin-sesion");
  try {
    await cargarSupermercados();
    await cargarProductos();
    await cargarTickets();
  } catch (err) {
    // Un 401 aquí ya habrá llamado a cerrarSesion() desde api().
    mensaje(err.message, true);
  }
}

function mostrarAuth() {
  $("vista-app").classList.add("hidden");
  $("vista-auth").classList.remove("hidden");
  $("btn-logout").classList.add("hidden");
  $("tabs").classList.add("hidden");
  // Sin pestañas no hay barra fija al pie, así que <main> no debe reservar su
  // hueco (styles.css, body.sin-sesion).
  document.body.classList.add("sin-sesion");
  // Se vuelve al par de tarjetas por defecto: si se salió estando en
  // «recuperar», al cerrar sesión hay que ver el login otra vez.
  mostrarTarjetasAuth(["card-login", "card-registro"]);
  $("aviso-sin-verificar").classList.add("hidden");
  // Aquí y no en el arranque: a esta vista se llega también al cerrar sesión y
  // al caducar el token (api() responde al 401 con cerrarSesion()). Si el
  // widget se montara solo al arrancar, quien entrase con sesión y la perdiera
  // se quedaría con un registro que siempre da 400.
  montarTurnstile();
}

function cerrarSesion() {
  token = null;
  localStorage.removeItem("token");
  mostrarAuth();
}

async function login(email, password) {
  const form = new URLSearchParams({ username: email, password });
  const resp = await fetch(API_BASE + "/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form,
  });
  if (resp.status === 403) {
    // Credenciales buenas pero correo sin confirmar: se ofrece el reenvío en
    // vez de dejar a la persona atascada sin saber qué hacer.
    $("aviso-sin-verificar").classList.remove("hidden");
    const data = await resp.json().catch(() => ({}));
    throw new Error(textoError(data.detail, resp.status));
  }
  if (!resp.ok) throw new Error("Email o contraseña incorrectos");
  iniciarSesionCon((await resp.json()).access_token);
}

// Punto único donde se guarda la sesión: lo usan el login, la confirmación de
// correo y el restablecimiento de contraseña, que también devuelven token.
function iniciarSesionCon(nuevoToken) {
  token = nuevoToken;
  localStorage.setItem("token", token);
  mostrarApp();
}

$("form-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await login($("login-email").value, $("login-password").value);
  } catch (err) {
    mensaje(err.message, true);
  }
});

// ---- Recuperación de contraseña y confirmación de correo ----
// Token del enlace de restablecimiento, si se ha llegado desde el correo.
let tokenRestablecer = null;

// Alterna entre las tarjetas de la pantalla de acceso. `#vista-auth` es una
// rejilla de dos columnas en escritorio: mostrar recuperar/restablecer a la
// vez que login y registro dejaría cuatro tarjetas compitiendo.
function mostrarTarjetasAuth(cuales) {
  for (const id of ["card-login", "card-registro", "card-recuperar", "card-restablecer"]) {
    $(id).classList.toggle("hidden", !cuales.includes(id));
  }
}

$("btn-olvide").addEventListener("click", () => {
  $("rec-email").value = $("login-email").value;
  mostrarTarjetasAuth(["card-recuperar"]);
  $("rec-email").focus();
});

// Salida de las dos pantallas intermedias. Sin esto, un enlace caducado deja
// atrapado en el formulario de restablecer sin más opción que recargar.
for (const id of ["btn-rec-volver", "btn-res-volver"]) {
  $(id).addEventListener("click", () => {
    mostrarTarjetasAuth(["card-login", "card-registro"]);
  });
}

$("form-recuperar").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/auth/recuperar", { method: "POST", json: { email: $("rec-email").value } });
  } catch (err) {
    mensaje(err.message, true);
    return;
  }
  // El mensaje es deliberadamente ambiguo: confirmar que la dirección existe
  // convertiría esto en un comprobador de quién tiene cuenta.
  mensaje("Si esa dirección tiene cuenta, te hemos enviado un enlace");
  mostrarTarjetasAuth(["card-login", "card-registro"]);
});

$("btn-reenviar").addEventListener("click", async () => {
  try {
    await api("/auth/reenviar-verificacion", {
      method: "POST",
      json: { email: $("login-email").value },
    });
    mensaje("Si tu cuenta está sin confirmar, te hemos escrito");
  } catch (err) {
    mensaje(err.message, true);
  }
});

$("form-restablecer").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const data = await api("/auth/restablecer", {
      method: "POST",
      json: { token: tokenRestablecer, password: $("res-password").value },
    });
    mensaje("Contraseña cambiada");
    iniciarSesionCon(data.access_token);
    mostrarTarjetasAuth(["card-login", "card-registro"]);
  } catch (err) {
    mensaje(err.message, true);
  }
});

// Los enlaces del correo llegan como ?verificar=… o ?restablecer=…
async function procesarEnlaceDeCorreo() {
  const params = new URLSearchParams(location.search);
  const verificar = params.get("verificar");
  const restablecer = params.get("restablecer");
  if (!verificar && !restablecer) return false;

  // El token sale de la barra de direcciones cuanto antes: si no, queda en el
  // historial y en cualquier captura de pantalla.
  history.replaceState(null, "", location.pathname);

  if (restablecer) {
    tokenRestablecer = restablecer;
    mostrarTarjetasAuth(["card-restablecer"]);
    $("res-password").focus();
    return true;
  }

  try {
    const data = await api("/auth/verificar", { method: "POST", json: { token: verificar } });
    mensaje("Correo confirmado, ya estás dentro");
    iniciarSesionCon(data.access_token);
    return true;
  } catch (err) {
    mensaje(err.message, true);
    return false;
  }
}

// ---- Anti-bot (Turnstile) ----
// La clave de sitio la sirve la API en /auth/config, no va incrustada en el
// HTML: el frontend es una imagen estática y así cambiarla no obliga a
// reconstruirla. Si viene vacía (desarrollo), no se monta nada y el registro
// funciona igual, porque el backend tampoco verifica.
let turnstileMontado = false;

async function montarTurnstile() {
  // Un solo montaje por carga de página: mostrarAuth() puede llamarse varias
  // veces y el widget ya montado sobrevive, porque cambiar de vista solo
  // alterna clases y no toca el DOM del formulario.
  if (turnstileMontado) return;
  turnstileMontado = true;

  let cfg;
  try {
    cfg = await api("/auth/config");
  } catch {
    // Sin config no bloqueamos el formulario; el backend decide. Se libera la
    // guarda para que un fallo puntual de red no deje el widget sin montar
    // durante el resto de la sesión.
    turnstileMontado = false;
    return;
  }
  if (!cfg.turnstile_site_key) return;

  const cont = $("turnstile-registro");
  cont.className = "cf-turnstile";
  cont.dataset.sitekey = cfg.turnstile_site_key;
  const script = document.createElement("script");
  script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js";
  script.async = true;
  script.defer = true;
  document.head.appendChild(script);
}

$("form-registro").addEventListener("submit", async (e) => {
  e.preventDefault();
  const cont = $("turnstile-registro");
  try {
    await api("/auth/registro", {
      method: "POST",
      json: {
        nombre: $("reg-nombre").value,
        email: $("reg-email").value,
        password: $("reg-password").value,
        // Vacío si el widget no está montado; el backend solo lo exige cuando
        // tiene clave secreta configurada.
        turnstile_token: window.turnstile ? window.turnstile.getResponse(cont) : undefined,
      },
    });
    mensaje("Cuenta creada, ya puedes iniciar sesión");
    $("form-registro").reset();
  } catch (err) {
    mensaje(err.message, true);
  } finally {
    // El token de Turnstile es de un solo uso: sin resetear, un segundo intento
    // reenviaría el mismo y Cloudflare lo rechazaría.
    if (window.turnstile) window.turnstile.reset(cont);
  }
});

$("btn-logout").addEventListener("click", cerrarSesion);

// ---- Pestañas ----
// Cada botón declara el panel que muestra en data-panel. En móvil la barra va
// fija al pie y en escritorio bajo la cabecera; eso es solo CSS.
function activarPestana(idPanel) {
  for (const tab of document.querySelectorAll(".tab")) {
    const activa = tab.dataset.panel === idPanel;
    tab.setAttribute("aria-selected", String(activa));
    $(tab.dataset.panel).classList.toggle("hidden", !activa);
  }
  // Al cambiar de pestaña se vuelve arriba: si no, se hereda el scroll de la
  // pantalla anterior y la nueva aparece empezada por la mitad.
  window.scrollTo(0, 0);
}

for (const tab of document.querySelectorAll(".tab")) {
  tab.addEventListener("click", () => activarPestana(tab.dataset.panel));
}

// ---- Supermercados ----
// Nombre por id, para poder etiquetar los tickets del listado sin pedir el
// supermercado uno por uno (la API solo devuelve supermercado_id).
const nombreSupermercado = new Map();

async function cargarSupermercados() {
  const sms = await api("/supermercados");
  const sel = $("sel-supermercado");
  sel.innerHTML = "";
  nombreSupermercado.clear();
  for (const sm of sms) {
    nombreSupermercado.set(sm.id, sm.nombre);
    const opt = document.createElement("option");
    opt.value = sm.id;
    opt.textContent = sm.nombre;
    sel.appendChild(opt);
  }
}

$("btn-add-super").addEventListener("click", async () => {
  const nombre = $("nuevo-super").value.trim();
  if (!nombre) return;
  try {
    await api("/supermercados", { method: "POST", json: { nombre } });
    $("nuevo-super").value = "";
    await cargarSupermercados();
    mensaje("Supermercado añadido");
  } catch (err) {
    mensaje(err.message, true);
  }
});

// ---- Tickets ----
$("form-ticket").addEventListener("submit", async (e) => {
  e.preventDefault();
  const archivo = $("ticket-imagen").files[0];
  if (!archivo) return;
  const form = new FormData();
  form.append("supermercado_id", $("sel-supermercado").value);
  form.append("imagen", archivo);
  if ($("ticket-fecha").value) form.append("fecha_compra", $("ticket-fecha").value);

  // El OCR es con diferencia lo más lento de la app (segundos). Sin bloquear el
  // botón se reenvía el mismo ticket dos veces creyendo que no ha hecho nada.
  const btn = e.target.querySelector("button[type=submit]");
  const textoBtn = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Procesando…";
  try {
    const ticket = await api("/tickets", { method: "POST", form });
    e.target.reset();
    await cargarTickets();
    activarPestana("panel-tickets");
    mostrarTicket(ticket);
    mensaje(`Ticket procesado: ${ticket.lineas.length} línea(s)`);
  } catch (err) {
    mensaje(err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = textoBtn;
  }
});

// Listado de tickets propios. Sin esto, un ticket a medio asociar quedaba
// inalcanzable en cuanto se recargaba la página. GET /tickets ya devuelve las
// líneas dentro, así que abrir uno no necesita otra petición.
async function cargarTickets() {
  let tickets;
  try {
    tickets = await api("/tickets");
  } catch (err) {
    mensaje(err.message, true);
    return;
  }
  const cont = $("lista-tickets");
  cont.textContent = "";

  if (!tickets.length) {
    const p = document.createElement("p");
    p.className = "vacio";
    p.textContent = "Todavía no has subido ningún ticket.";
    cont.appendChild(p);
    return;
  }

  // Más recientes primero: lo que se acaba de subir es lo que se va a asociar.
  tickets.sort((a, b) => b.fecha_compra.localeCompare(a.fecha_compra) || b.id - a.id);
  for (const t of tickets) cont.appendChild(filaTicket(t));
}

function filaTicket(ticket) {
  const fila = document.createElement("div");
  fila.className = "ticket-item";
  fila.dataset.ticketId = ticket.id;

  const info = document.createElement("button");
  info.type = "button";
  info.className = "info ticket-abrir";
  const titulo = document.createElement("span");
  titulo.className = "titulo";
  titulo.textContent =
    nombreSupermercado.get(ticket.supermercado_id) || "Supermercado";
  const sub = document.createElement("span");
  sub.className = "sub";
  const pendientes = ticket.lineas.filter((l) => !l.producto_id).length;
  sub.textContent =
    `${ticket.fecha_compra} · ${ticket.lineas.length} línea(s)` +
    (pendientes ? ` · ${pendientes} sin asociar` : "");
  info.append(titulo, sub);
  info.addEventListener("click", () => mostrarTicket(ticket));

  const acciones = document.createElement("div");
  acciones.className = "acciones";
  const borrar = document.createElement("button");
  borrar.type = "button";
  borrar.className = "ghost";
  borrar.textContent = "Borrar";
  borrar.setAttribute("aria-label", `Borrar el ticket del ${ticket.fecha_compra}`);
  borrar.addEventListener("click", async () => {
    // Se lleva por delante las líneas y su histórico de precios: se confirma.
    if (!confirm(`¿Borrar el ticket del ${ticket.fecha_compra}? No se puede deshacer.`)) {
      return;
    }
    try {
      await api(`/tickets/${ticket.id}`, { method: "DELETE" });
      // Si el que se borra es el que está abierto, se cierra el detalle.
      if (ticketAbierto === ticket.id) cerrarDetalleTicket();
      await cargarTickets();
      mensaje("Ticket borrado");
    } catch (err) {
      mensaje(err.message, true);
    }
  });
  acciones.appendChild(borrar);

  fila.append(info, acciones);
  return fila;
}

// Qué ticket se está viendo en el detalle, para marcarlo en la lista y saber si
// hay que cerrarlo al borrarlo.
let ticketAbierto = null;

function cerrarDetalleTicket() {
  ticketAbierto = null;
  $("card-ticket").classList.add("hidden");
}

function mostrarTicket(ticket) {
  ticketAbierto = ticket.id;
  for (const fila of document.querySelectorAll(".ticket-item")) {
    fila.setAttribute(
      "aria-current",
      String(Number(fila.dataset.ticketId) === ticket.id),
    );
  }
  const card = $("card-ticket");
  card.classList.remove("hidden");
  // Reiniciar la animación: sin quitar la clase y forzar un reflujo, abrir un
  // segundo ticket no volvería a "imprimirlo".
  card.classList.remove("imprimiendo");
  void card.offsetWidth;
  card.classList.add("imprimiendo");

  const badge = $("ticket-estado");
  badge.textContent = ticket.estado;
  badge.className = "badge" + (ticket.estado === "procesado" ? " ok" : "");
  const tbody = $("tabla-lineas").querySelector("tbody");
  tbody.innerHTML = "";
  for (const linea of ticket.lineas) {
    tbody.appendChild(filaLinea(linea));
  }
}

function filaLinea(linea) {
  const tr = document.createElement("tr");
  // data-label alimenta el apilado en movil: en pantallas estrechas la fila
  // se muestra como ficha y cada celda lleva su etiqueta delante (styles.css).
  const tdTexto = document.createElement("td");
  tdTexto.dataset.label = "Texto";
  tdTexto.textContent = linea.texto_original;
  const tdPrecio = document.createElement("td");
  tdPrecio.dataset.label = "Precio";
  tdPrecio.textContent = `${linea.precio_total} €`;
  const tdProducto = document.createElement("td");
  tdProducto.dataset.label = "Producto";

  if (linea.producto_id) {
    tdProducto.textContent = "✓ asociada";
  } else {
    const input = document.createElement("input");
    input.placeholder = "nombre del producto";
    const btn = document.createElement("button");
    btn.textContent = "Asociar";
    btn.className = "sec";
    btn.addEventListener("click", async () => {
      const nombre = input.value.trim();
      if (!nombre) return;
      try {
        await api(`/lineas/${linea.id}/asociar`, {
          method: "POST",
          json: { nuevo_producto: { nombre_normalizado: nombre } },
        });
        tdProducto.textContent = "✓ asociada";
        await cargarProductos();
        mensaje("Línea asociada");
      } catch (err) {
        mensaje(err.message, true);
      }
    });
    const wrap = document.createElement("div");
    wrap.className = "fila";
    wrap.append(input, btn);
    tdProducto.appendChild(wrap);
    // Zona dudosa (§5bis punto 3): en vez de teclear el producto de cero, se
    // ofrecen los parecidos. Se piden aparte para no bloquear el pintado.
    pintarSugerencias(linea, tdProducto);
  }
  tr.append(tdTexto, tdPrecio, tdProducto);
  return tr;
}

async function pintarSugerencias(linea, tdProducto) {
  let sugerencias;
  try {
    sugerencias = await api(`/lineas/${linea.id}/sugerencias`);
  } catch {
    return; // Sin sugerencias siempre queda la asociación manual.
  }
  if (!sugerencias.length) return;

  const cont = document.createElement("div");
  cont.className = "sugerencias";
  const etiqueta = document.createElement("span");
  etiqueta.className = "muted";
  etiqueta.textContent = "¿Es este producto?";
  cont.appendChild(etiqueta);

  for (const s of sugerencias.slice(0, 3)) {
    const btn = document.createElement("button");
    btn.className = "sec";
    btn.textContent = s.nombre_normalizado;
    btn.title = `Parecido a «${s.texto_alias}» (${Math.round(s.score * 100)}%)`;
    btn.addEventListener("click", async () => {
      try {
        await api(`/lineas/${linea.id}/asociar`, {
          method: "POST",
          json: { producto_id: s.producto_id },
        });
        tdProducto.textContent = "✓ asociada";
        mensaje("Línea asociada");
      } catch (err) {
        mensaje(err.message, true);
      }
    });
    cont.appendChild(btn);
  }
  tdProducto.appendChild(cont);
}

// ---- Productos y comparativa ----
async function cargarProductos() {
  const productos = await api("/productos");
  const sel = $("sel-producto");
  sel.innerHTML = "";
  for (const p of productos) {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.nombre_normalizado;
    sel.appendChild(opt);
  }
}

$("btn-comparar").addEventListener("click", async () => {
  const id = $("sel-producto").value;
  if (!id) return;
  try {
    const data = await api(`/productos/${id}/precios`);
    mostrarComparativa(data);
  } catch (err) {
    mensaje(err.message, true);
  }
});

function celda(texto, clase) {
  const td = document.createElement("td");
  td.textContent = texto;
  if (clase) td.className = clase;
  return td;
}

// Importe en formato español: coma decimal y símbolo detrás.
function euros(valor) {
  return `${Number(valor).toFixed(2).replace(".", ",")} €`;
}

// ---- Impresión de resultados ----
// Los resultados se pintan como un ticket de caja: cabecera del comercio,
// concepto a la izquierda, importe a la derecha, doble raya antes del total.
// No es decoración: alinear importes en columna es justo lo que hace legible
// una comparación de precios.
function papelNuevo(cont, titulo) {
  cont.textContent = "";
  const papel = document.createElement("div");
  papel.className = "card recibo dentado imprimiendo";

  const cabecera = document.createElement("p");
  cabecera.className = "recibo-cabecera";
  cabecera.textContent = "SuperComparateca";

  const h = document.createElement("p");
  h.className = "recibo-titulo";
  h.textContent = titulo;

  papel.append(cabecera, h, raya());
  cont.appendChild(papel);
  return papel;
}

function raya(doble = false) {
  const hr = document.createElement("hr");
  hr.className = doble ? "raya-doble" : "raya";
  return hr;
}

function lineaTotal(concepto, importe) {
  const fila = document.createElement("p");
  fila.className = "recibo-total";
  const izq = document.createElement("span");
  izq.textContent = concepto;
  const der = document.createElement("span");
  der.className = "cifra";
  der.textContent = importe;
  fila.append(izq, der);
  return fila;
}

// El sello. Es la firma de la interfaz: aparece una sola vez por resultado y
// dice lo único que el usuario venía a saber.
function sello(titulo, valor) {
  const s = document.createElement("div");
  s.className = "sello";
  const t = document.createElement("span");
  t.className = "sello-titulo";
  t.textContent = `★ ${titulo}`;
  const v = document.createElement("span");
  v.className = "sello-valor";
  v.textContent = valor;
  s.append(t, v);
  return s;
}

function tablaRecibo(cabeceras, filas) {
  const wrap = document.createElement("div");
  wrap.className = "tabla-scroll";
  const tabla = document.createElement("table");
  tabla.className = "recibo-tabla";

  const thead = document.createElement("thead");
  const trHead = document.createElement("tr");
  for (const titulo of cabeceras) {
    const th = document.createElement("th");
    th.textContent = titulo;
    trHead.appendChild(th);
  }
  thead.appendChild(trHead);

  const tbody = document.createElement("tbody");
  for (const fila of filas) {
    const tr = document.createElement("tr");
    if (fila.gana) tr.className = "gana";
    for (const texto of fila.celdas) tr.appendChild(celda(texto));
    tbody.appendChild(tr);
  }
  tabla.append(thead, tbody);
  wrap.appendChild(tabla);
  return wrap;
}

function vacio(cont, texto) {
  cont.textContent = "";
  const p = document.createElement("p");
  p.className = "vacio";
  p.textContent = texto;
  cont.appendChild(p);
}

function mostrarComparativa(data) {
  const cont = $("resultado-precios");
  if (!data.supermercados.length) {
    vacio(cont, `Todavía no hay precios de «${data.nombre_normalizado}». Sube un ticket que lo incluya.`);
    return;
  }

  const papel = papelNuevo(cont, data.nombre_normalizado);
  // La API ordena por precio ascendente: el primero es el más barato.
  papel.appendChild(
    tablaRecibo(
      ["Supermercado", "Obs.", "Precio"],
      data.supermercados.map((s, i) => ({
        gana: i === 0,
        celdas: [s.supermercado, String(s.num_observaciones), euros(s.precio_actual)],
      })),
    ),
  );

  const barato = data.supermercados[0];
  const caro = data.supermercados[data.supermercados.length - 1];
  const diferencia = Number(caro.precio_actual) - Number(barato.precio_actual);

  // Con un solo supermercado no hay nada que comparar: ni diferencia ni sello.
  if (data.supermercados.length > 1) {
    papel.append(raya(true), lineaTotal("Diferencia", euros(diferencia)));
    papel.appendChild(sello("Más barato", barato.supermercado));
  }
}

// ---- Cesta habitual (FR10) ----
$("btn-cesta").addEventListener("click", async () => {
  try {
    mostrarCesta(await api("/cesta/comparativa"));
  } catch (err) {
    mensaje(err.message, true);
  }
});

function mostrarCesta(data) {
  const cont = $("resultado-cesta");
  if (!data.productos.length) {
    vacio(cont, "Todavía no has confirmado productos en tus tickets. Asocia las líneas de uno y vuelve.");
    return;
  }

  const papel = papelNuevo(cont, "Cesta habitual");

  // Lo que compone la cesta, impreso como el detalle de un ticket.
  papel.appendChild(
    tablaRecibo(
      ["Producto", "Veces"],
      data.productos.map((p) => ({
        celdas: [p.nombre_normalizado, `×${p.veces_comprado}`],
      })),
    ),
  );

  const total = data.productos.length;
  papel.append(raya(true));

  // La API ordena por cobertura y luego por total: el primero es el mejor
  // candidato real, no solo el de suma más baja.
  papel.appendChild(
    tablaRecibo(
      ["Supermercado", "Cubre", "Total"],
      data.supermercados.map((s, i) => ({
        gana: i === 0,
        celdas: [s.supermercado, `${s.productos_cubiertos}/${total}`, euros(s.total)],
      })),
    ),
  );

  if (data.supermercados.length) {
    const mejor = data.supermercados[0];
    papel.appendChild(sello("Tu cesta sale mejor en", mejor.supermercado));
    // Un supermercado con pocos productos tendría un total engañosamente bajo:
    // se avisa en vez de dejar que la cifra hable sola.
    if (mejor.productos_cubiertos < total) {
      const nota = document.createElement("p");
      nota.className = "muted";
      nota.style.textAlign = "center";
      nota.textContent =
        `Solo tiene precio de ${mejor.productos_cubiertos} de tus ${total} productos, ` +
        "así que el total no es comparable del todo.";
      papel.appendChild(nota);
    }
  }
}

// ---- Baja de la cuenta (derecho de supresión, art. 17 RGPD) ----
// La confirmación es un formulario, no un confirm(): hace falta la contraseña,
// porque la acción es irreversible y un token robado no debería bastar.
$("btn-baja").addEventListener("click", () => {
  $("baja-confirmar").classList.remove("hidden");
  $("btn-baja").classList.add("hidden");
  $("baja-password").focus();
});

$("btn-baja-cancelar").addEventListener("click", () => {
  $("baja-confirmar").classList.add("hidden");
  $("btn-baja").classList.remove("hidden");
  $("baja-password").value = "";
});

$("form-baja").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = e.target.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    await api("/auth/me", {
      method: "DELETE",
      json: { password: $("baja-password").value },
    });
    // No se usa cerrarSesion(): ese camino vuelve al login como si la sesión
    // hubiera caducado, y aquí conviene decir que la cuenta ya no existe.
    token = null;
    localStorage.removeItem("token");
    mostrarAuth();
    $("baja-confirmar").classList.add("hidden");
    $("btn-baja").classList.remove("hidden");
    mensaje("Cuenta borrada");
  } catch (err) {
    mensaje(err.message, true);
  } finally {
    btn.disabled = false;
    $("baja-password").value = "";
  }
});

// ---- Arranque ----
// Los enlaces del correo mandan sobre la sesión guardada: quien acaba de
// pulsar «confirmar mi correo» espera que pase eso, no que se le cuele la
// sesión anterior.
procesarEnlaceDeCorreo().then((gestionado) => {
  if (gestionado) return;
  if (token) mostrarApp();
  else mostrarAuth();
});
