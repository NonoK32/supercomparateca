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
    throw new Error(data.detail ? JSON.stringify(data.detail) : `Error ${resp.status}`);
  }
  return data;
}

// ---- Autenticación ----
async function mostrarApp() {
  $("vista-auth").classList.add("hidden");
  $("vista-app").classList.remove("hidden");
  $("btn-logout").classList.remove("hidden");
  try {
    await cargarSupermercados();
    await cargarProductos();
  } catch (err) {
    // Un 401 aquí ya habrá llamado a cerrarSesion() desde api().
    mensaje(err.message, true);
  }
}

function mostrarAuth() {
  $("vista-app").classList.add("hidden");
  $("vista-auth").classList.remove("hidden");
  $("btn-logout").classList.add("hidden");
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
  if (!resp.ok) throw new Error("Email o contraseña incorrectos");
  token = (await resp.json()).access_token;
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

$("form-registro").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/auth/registro", {
      method: "POST",
      json: {
        nombre: $("reg-nombre").value,
        email: $("reg-email").value,
        password: $("reg-password").value,
      },
    });
    mensaje("Cuenta creada, ya puedes iniciar sesión");
  } catch (err) {
    mensaje(err.message, true);
  }
});

$("btn-logout").addEventListener("click", cerrarSesion);

// ---- Supermercados ----
async function cargarSupermercados() {
  const sms = await api("/supermercados");
  const sel = $("sel-supermercado");
  sel.innerHTML = "";
  for (const sm of sms) {
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
  try {
    const ticket = await api("/tickets", { method: "POST", form });
    mostrarTicket(ticket);
    mensaje(`Ticket procesado: ${ticket.lineas.length} línea(s)`);
  } catch (err) {
    mensaje(err.message, true);
  }
});

function mostrarTicket(ticket) {
  $("card-ticket").classList.remove("hidden");
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
  const tdTexto = document.createElement("td");
  tdTexto.textContent = linea.texto_original;
  const tdPrecio = document.createElement("td");
  tdPrecio.textContent = `${linea.precio_total} €`;
  const tdProducto = document.createElement("td");

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

function mostrarComparativa(data) {
  const cont = $("resultado-precios");
  cont.textContent = "";
  if (!data.supermercados.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = `Aún no hay precios para «${data.nombre_normalizado}».`;
    cont.appendChild(p);
    return;
  }

  const tabla = document.createElement("table");
  const thead = document.createElement("thead");
  const trHead = document.createElement("tr");
  for (const titulo of ["Supermercado", "Precio actual", "Fecha", "Obs."]) {
    const th = document.createElement("th");
    th.textContent = titulo;
    trHead.appendChild(th);
  }
  thead.appendChild(trHead);
  tabla.appendChild(thead);

  const tbody = document.createElement("tbody");
  data.supermercados.forEach((s, i) => {
    const tr = document.createElement("tr");
    // El primero es el más barato (la API ordena por precio ascendente).
    tr.append(
      celda(s.supermercado, i === 0 ? "barato" : ""),
      celda(`${s.precio_actual} €`),
      celda(s.fecha),
      celda(String(s.num_observaciones)),
    );
    tbody.appendChild(tr);
  });
  tabla.appendChild(tbody);
  cont.appendChild(tabla);
}

// ---- Arranque ----
if (token) {
  mostrarApp();
} else {
  mostrarAuth();
}
