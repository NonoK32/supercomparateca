"use strict";

// La API se publica en el puerto 8000 del mismo host donde se abre el frontend.
const API_BASE = `http://${location.hostname}:8000`;

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
  if (resp.status === 204) return null;
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.detail ? JSON.stringify(data.detail) : `Error ${resp.status}`);
  }
  return data;
}

// ---- Autenticación ----
function mostrarApp() {
  $("vista-auth").classList.add("hidden");
  $("vista-app").classList.remove("hidden");
  $("btn-logout").classList.remove("hidden");
  cargarSupermercados();
  cargarProductos();
}

function mostrarAuth() {
  $("vista-app").classList.add("hidden");
  $("vista-auth").classList.remove("hidden");
  $("btn-logout").classList.add("hidden");
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

$("btn-logout").addEventListener("click", () => {
  token = null;
  localStorage.removeItem("token");
  mostrarAuth();
});

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
  }
  tr.append(tdTexto, tdPrecio, tdProducto);
  return tr;
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

function mostrarComparativa(data) {
  const cont = $("resultado-precios");
  if (!data.supermercados.length) {
    cont.innerHTML = `<p class="muted">Aún no hay precios para «${data.nombre_normalizado}».</p>`;
    return;
  }
  let html = `<table><thead><tr><th>Supermercado</th><th>Precio actual</th><th>Fecha</th><th>Obs.</th></tr></thead><tbody>`;
  data.supermercados.forEach((s, i) => {
    const clase = i === 0 ? "barato" : "";
    html += `<tr class="${clase}"><td>${s.supermercado}</td><td>${s.precio_actual} €</td><td>${s.fecha}</td><td>${s.num_observaciones}</td></tr>`;
  });
  html += "</tbody></table>";
  cont.innerHTML = html;
}

// ---- Arranque ----
if (token) {
  mostrarApp();
} else {
  mostrarAuth();
}
