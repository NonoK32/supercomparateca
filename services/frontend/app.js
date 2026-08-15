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
    const error = new Error(textoError(data.detail, resp.status));
    // El detalle estructurado viaja con el error (p. ej. qué datos del ticket
    // no se han podido leer): quien sepa reaccionar lo mira, el resto enseña
    // el mensaje y ya está.
    error.detail = data.detail;
    throw error;
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
  if (detail.mensaje) return detail.mensaje;
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
    await comprobarRol();
    await cargarSupermercados();
    await cargarProductos();
    await cargarTickets();
  } catch (err) {
    // Un 401 aquí ya habrá llamado a cerrarSesion() desde api().
    mensaje(err.message, true);
  }
}

function mostrarAuth() {
  // Salir de la sesión (a mano, por token caducado o al borrar la cuenta) tiene
  // que apagar la cámara: es el punto por el que se pasa en los tres casos.
  cerrarCamara();
  // El siguiente que entre puede no ser admin: el tab no puede quedar puesto
  // del anterior.
  soyAdmin = false;
  $("tab-admin").classList.add("hidden");
  $("vista-app").classList.add("hidden");
  $("vista-auth").classList.remove("hidden");
  $("btn-logout").classList.add("hidden");
  $("tabs").classList.add("hidden");
  // Sin pestañas no hay barra fija al pie, así que <main> no debe reservar su
  // hueco (styles.css, body.sin-sesion).
  document.body.classList.add("sin-sesion");
  // Se vuelve al login: si se salió estando en «recuperar» o en el registro,
  // al cerrar sesión hay que ver otra vez la puerta de entrada.
  mostrarTarjetasAuth(["card-login"]);
  $("aviso-sin-verificar").classList.add("hidden");
  // Aquí y no solo en el arranque: a esta vista se llega también al cerrar
  // sesión y al caducar el token. El montaje es idempotente.
  montarGoogle();
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

// Una sola tarjeta a la vez en la pantalla de acceso. Cambiar de operación
// reimprime la hoja: es el único movimiento del sistema (y ya respeta
// prefers-reduced-motion), y sin él el cambio de formulario pasa desapercibido,
// porque entrar y registrarse se parecen mucho.
function mostrarTarjetasAuth(cuales) {
  for (const id of ["card-login", "card-registro", "card-recuperar", "card-restablecer"]) {
    const card = $(id);
    const visible = cuales.includes(id);
    card.classList.toggle("hidden", !visible);
    if (!visible) continue;
    card.classList.remove("imprimiendo");
    void card.offsetWidth; // reinicia la animación
    card.classList.add("imprimiendo");
  }
}

$("btn-ir-registro").addEventListener("click", () => {
  mostrarTarjetasAuth(["card-registro"]);
  // El widget anti-bot se monta al abrir el registro, no antes: Turnstile se
  // dibuja sobre un contenedor que hasta ahora estaba oculto, y montarlo dentro
  // de un `display:none` es pedirle que se pinte a ciegas.
  montarTurnstile();
  $("reg-nombre").focus();
});

$("btn-ir-login").addEventListener("click", () => {
  mostrarTarjetasAuth(["card-login"]);
  $("login-email").focus();
});

$("btn-olvide").addEventListener("click", () => {
  $("rec-email").value = $("login-email").value;
  mostrarTarjetasAuth(["card-recuperar"]);
  $("rec-email").focus();
});

// Salida de las dos pantallas intermedias. Sin esto, un enlace caducado deja
// atrapado en el formulario de restablecer sin más opción que recargar.
for (const id of ["btn-rec-volver", "btn-res-volver"]) {
  $(id).addEventListener("click", () => {
    mostrarTarjetasAuth(["card-login"]);
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
  mostrarTarjetasAuth(["card-login"]);
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
    mostrarTarjetasAuth(["card-login"]);
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
// La configuración pública (claves de sitio, si hay correo, si hay Google) se
// pide una vez: la necesitan el widget anti-bot y el botón de Google, y no
// cambia mientras la página está abierta.
let promesaConfig = null;

function configAuth() {
  if (!promesaConfig) {
    promesaConfig = api("/auth/config").catch((err) => {
      // Un fallo puntual de red no debe dejar la página sin widget ni sin botón
      // para siempre: se olvida la promesa y el siguiente intento repite.
      promesaConfig = null;
      throw err;
    });
  }
  return promesaConfig;
}

// ---- Acceso con Google ----
// Se usa el flujo de ID token de Google Identity Services: el navegador recibe
// un token firmado y el api lo verifica. No hay redirección ni secreto de
// cliente porque no pedimos acceso a nada de Google salvo la identidad.
let googleMontado = false;

async function montarGoogle() {
  if (googleMontado) return;
  let cfg;
  try {
    cfg = await configAuth();
  } catch {
    return; // Siempre queda entrar con email y contraseña.
  }
  if (!cfg.google_client_id) return;
  googleMontado = true;

  const script = document.createElement("script");
  script.src = "https://accounts.google.com/gsi/client";
  script.async = true;
  script.defer = true;
  script.onload = () => {
    window.google.accounts.id.initialize({
      client_id: cfg.google_client_id,
      callback: async ({ credential }) => {
        try {
          const data = await api("/auth/google", {
            method: "POST",
            json: { credential },
          });
          iniciarSesionCon(data.access_token);
        } catch (err) {
          mensaje(err.message, true);
        }
      },
    });
    // El botón lo dibuja Google: su marca y su tipografía son requisito suyo,
    // y son justo lo que la gente reconoce sin leer.
    window.google.accounts.id.renderButton($("boton-google"), {
      theme: "outline",
      size: "large",
      text: "signin_with",
      shape: "rectangular",
      locale: "es",
      width: Math.min(400, $("card-login").clientWidth - 32 || 320),
    });
    $("acceso-google").classList.remove("hidden");
  };
  document.head.appendChild(script);
}

let turnstileMontado = false;

async function montarTurnstile() {
  // Un solo montaje por carga de página: se puede entrar y salir del registro
  // varias veces y el widget ya montado sobrevive, porque cambiar de tarjeta
  // solo alterna clases y no toca el DOM del formulario.
  if (turnstileMontado) return;
  turnstileMontado = true;

  let cfg;
  try {
    cfg = await configAuth();
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
    mensaje("Cuenta creada: confirma tu correo y ya puedes entrar");
    $("form-registro").reset();
    // De vuelta a la puerta de entrada, que es lo siguiente que toca.
    mostrarTarjetasAuth(["card-login"]);
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
  // Irse a otra pestaña deja de enseñar la cámara, pero no la apaga: sin esto
  // el piloto se queda encendido con el vídeo ya fuera de la vista.
  cerrarCamara();
  for (const tab of document.querySelectorAll(".tab")) {
    const activa = tab.dataset.panel === idPanel;
    tab.setAttribute("aria-selected", String(activa));
    $(tab.dataset.panel).classList.toggle("hidden", !activa);
  }
  // El panel de admin se puebla al abrirlo, no al entrar en la app: son tres
  // peticiones que la mayoría de sesiones no llegan a usar, y así se ve el
  // estado de ahora y no el de cuando se inició sesión.
  if (idPanel === "panel-admin" && soyAdmin) {
    cargarAdmin().catch((err) => mensaje(err.message, true));
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
  sel.appendChild(new Option("— elige un supermercado —", ""));
  for (const sm of sms) {
    nombreSupermercado.set(sm.id, sm.nombre);
    const opt = document.createElement("option");
    opt.value = sm.id;
    opt.textContent = sm.nombre;
    sel.appendChild(opt);
  }
  sel.appendChild(new Option("+ Crear supermercado nuevo…", SUPER_NUEVO));
}

// Valor centinela de la opción "crear supermercado", como en los productos.
const SUPER_NUEVO = "nuevo";

// ---- Tickets ----
// Las páginas a la espera de que el usuario conteste lo que el OCR no supo
// leer. Es una lista: un ticket largo se sube en varias capturas.
let ticketPendiente = null;

// El mismo tope que aplica el api (routers/tickets.py). Se avisa también aquí
// para no gastar una subida entera en un 400 que ya se veía venir.
const MAX_ARCHIVOS = 10;

// Lo que el ocr-service sabe leer: una foto, o un PDF (lleve capa de texto o
// sea un escaneo).
const esTicket = (archivo) =>
  archivo.type.startsWith("image/") || archivo.type === "application/pdf";

// El <input type=file> es la única lista de páginas que hay: la cámara,
// arrastrar y soltar y el selector escriben todos ahí. Así el envío y la
// segunda pasada del OCR no tienen que elegir de dónde leer.
const paginasElegidas = () => Array.from($("ticket-imagen").files);

function fijarPaginas(archivos) {
  // Cambiar el FileList de un input solo se puede a través de un DataTransfer;
  // no hay otra forma que dé el navegador.
  const datos = new DataTransfer();
  for (const archivo of archivos.slice(0, MAX_ARCHIVOS)) datos.items.add(archivo);
  $("ticket-imagen").files = datos.files;
  pintarPaginas();
}

function pintarPaginas() {
  const archivos = paginasElegidas();
  const tira = $("capturas");
  // Las miniaturas de la tanda anterior siguen ocupando memoria hasta que se
  // revocan, y aquí se repinta en cada captura.
  for (const img of tira.querySelectorAll("img")) URL.revokeObjectURL(img.src);
  tira.replaceChildren();
  tira.classList.toggle("hidden", archivos.length === 0);

  archivos.forEach((archivo, i) => {
    const pagina = document.createElement("span");
    pagina.className = "captura";
    if (archivo.type.startsWith("image/")) {
      const img = document.createElement("img");
      img.src = URL.createObjectURL(archivo);
      img.alt = `Página ${i + 1} de ${archivos.length}`;
      pagina.appendChild(img);
    } else {
      // Un <img> no sabe pintar un PDF: se enseña el nombre y ya.
      pagina.classList.add("captura-pdf");
      pagina.textContent = archivo.name;
    }
    tira.appendChild(pagina);
  });
  rotularZona(archivos);
}

function rotularZona(archivos) {
  const n = archivos.length;
  $("zona-titulo").textContent = n ? "Ticket listo" : "Pegar aquí el ticket";
  $("zona-pista").textContent =
    n === 0
      ? "Toca para elegir las fotos o el PDF · o arrástralos"
      : n === 1
        ? `${archivos[0].name} · toca para cambiarlo`
        : `${n} páginas · toca para cambiarlas`;
}

// El OCR tarda varios segundos con la pantalla quieta: sin decir nada, eso se
// lee como que la página se ha colgado. Se dice qué está pasando y se deja de
// admitir otra foto mientras tanto.
function marcarLeyendo(activo, paginas = 0) {
  $("zona-foto").classList.toggle("leyendo", activo);
  if (!activo) return;
  $("zona-titulo").textContent = "Leyendo el ticket…";
  // Cada página es una pasada de OCR, así que con varias la espera se multiplica
  // y conviene decirlo en vez de dejar que parezca que se ha atascado.
  $("zona-pista").textContent =
    paginas > 1 ? `${paginas} páginas · esto tarda un poco` : "Puede tardar unos segundos";
}

function olvidarTicket() {
  // reset() vacía el input, y el repintado suelta las miniaturas.
  $("form-ticket").reset();
  pintarPaginas();
}

$("ticket-imagen").addEventListener("change", () => {
  const archivos = paginasElegidas();
  if (archivos.length > MAX_ARCHIVOS) {
    mensaje(`Como mucho ${MAX_ARCHIVOS} páginas por ticket; me quedo con las primeras`, true);
    fijarPaginas(archivos); // recorta al tope
    return;
  }
  pintarPaginas();
});

// ---- Escanear con la cámara ----
// Es otra forma de elegir las páginas, no otro camino de subida: cada fotograma
// capturado se añade al mismo <input type=file> y de ahí en adelante todo es
// idéntico a unas fotos elegidas a mano. Así el envío, las miniaturas y la
// segunda pasada del OCR siguen teniendo un único sitio del que leer el ticket.
let flujoCamara = null;

function mostrarModo(modo) {
  const enCamara = modo === "camara";
  $("modo-archivo").setAttribute("aria-pressed", String(!enCamara));
  $("modo-camara").setAttribute("aria-pressed", String(enCamara));
  $("zona-foto").classList.toggle("hidden", enCamara);
  $("zona-camara").classList.toggle("hidden", !enCamara);
  $("botones-camara").classList.toggle("hidden", !enCamara);
  // Con la cámara abierta no hay nada que procesar todavía: primero se captura
  // lo que haga falta, se ven las páginas, y entonces se envía.
  $("btn-procesar").classList.toggle("hidden", enCamara);
}

// Con la cámara abierta no se ven las miniaturas, así que si no se dice por
// dónde va uno, no hay forma de saberlo.
function rotularCamara() {
  const n = paginasElegidas().length;
  $("camara-pista").textContent =
    n === 0
      ? "Encuadra el ticket entero y pulsa Capturar"
      : `${n} página${n > 1 ? "s" : ""} · sigue por donde se cortó, o pulsa Terminar`;
  $("btn-terminar-camara").disabled = n === 0;
}

async function abrirCamara() {
  mostrarModo("camara");
  rotularCamara();
  try {
    flujoCamara = await navigator.mediaDevices.getUserMedia({
      // La trasera es la que enfoca el ticket. En un portátil no existe, y por
      // eso `ideal` y no `exact`: con `exact` fallaría en vez de coger la que
      // haya.
      video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 } },
    });
  } catch (err) {
    mostrarModo("archivo");
    mensaje(
      err.name === "NotAllowedError"
        ? "No has dado permiso para usar la cámara"
        : "No he podido abrir la cámara. Sube una foto o un PDF.",
      true,
    );
    return;
  }
  const video = $("camara-video");
  video.srcObject = flujoCamara;
  await video.play();
}

// El piloto de la cámara sigue encendido hasta que se paran las pistas: hay que
// cerrarla en cuanto deja de verse, no solo al capturar.
function cerrarCamara() {
  for (const pista of flujoCamara ? flujoCamara.getTracks() : []) pista.stop();
  flujoCamara = null;
  $("camara-video").srcObject = null;
}

function capturar() {
  const video = $("camara-video");
  if (!video.videoWidth) {
    mensaje("La cámara todavía está arrancando", true);
    return;
  }
  const lienzo = document.createElement("canvas");
  // Al tamaño real de la cámara, no al que se ve en pantalla: la letra de un
  // ticket es pequeña y el OCR necesita todos los píxeles que haya.
  lienzo.width = video.videoWidth;
  lienzo.height = video.videoHeight;
  lienzo.getContext("2d").drawImage(video, 0, 0);
  lienzo.toBlob(
    (blob) => {
      const yaHay = paginasElegidas();
      if (yaHay.length >= MAX_ARCHIVOS) {
        mensaje(`Ya van ${MAX_ARCHIVOS} páginas, que es el máximo por ticket`, true);
        return;
      }
      const foto = new File([blob], `ticket-${Date.now()}.jpg`, { type: "image/jpeg" });
      // Se añade, no sustituye: son trozos del mismo papel. Y la cámara sigue
      // abierta, porque encadenar la página siguiente sin esperar otra vez a
      // que arranque es justo el motivo de que esto exista.
      fijarPaginas([...yaHay, foto]);
      rotularCamara();
    },
    "image/jpeg",
    // La letra de un ticket se emborrona en cuanto el JPEG aprieta, y ahí es
    // donde el OCR empieza a perder los decimales de los precios.
    0.92,
  );
}

// Sin getUserMedia el botón no llega a pintarse. No es solo cosa de navegadores
// viejos: en un http:// que no sea localhost tampoco existe.
if (navigator.mediaDevices?.getUserMedia) {
  $("modo-camara").classList.remove("hidden");
}
$("modo-archivo").addEventListener("click", () => {
  cerrarCamara();
  mostrarModo("archivo");
});
$("modo-camara").addEventListener("click", abrirCamara);
$("btn-capturar").addEventListener("click", capturar);
// Terminar: se apaga la cámara y se pasa a ver las páginas capturadas, que es
// donde se comprueba que no falta un trozo antes de gastar el OCR.
$("btn-terminar-camara").addEventListener("click", () => {
  cerrarCamara();
  mostrarModo("archivo");
});

// Arrastrar y soltar en escritorio. Se asigna al input de verdad (vía
// DataTransfer) para no llevar la cuenta de los archivos por otro lado.
const zona = $("zona-foto");
for (const evento of ["dragenter", "dragover"]) {
  zona.addEventListener(evento, (e) => {
    e.preventDefault();
    zona.classList.add("arrastrando");
  });
}
for (const evento of ["dragleave", "drop"]) {
  zona.addEventListener(evento, () => zona.classList.remove("arrastrando"));
}
zona.addEventListener("drop", (e) => {
  e.preventDefault();
  // Se cuelan cosas que no son tickets al arrastrar una carpeta entera; se
  // filtran en vez de rechazar el lote.
  const archivos = Array.from(e.dataTransfer.files).filter(esTicket);
  if (!archivos.length) {
    mensaje("Eso no parece un ticket: arrastra fotos o un PDF", true);
    return;
  }
  if (archivos.length > MAX_ARCHIVOS) {
    mensaje(`Como mucho ${MAX_ARCHIVOS} páginas por ticket; me quedo con las primeras`, true);
  }
  fijarPaginas(archivos);
});

$("form-ticket").addEventListener("submit", async (e) => {
  e.preventDefault();
  const archivos = paginasElegidas();
  if (!archivos.length) {
    mensaje("Elige la foto o el PDF del ticket", true);
    return;
  }
  await procesarTicket(archivos, {}, e.target.querySelector("button[type=submit]"));
});

// El OCR es con diferencia lo más lento de la app (segundos). Sin bloquear el
// botón se reenvía el mismo ticket dos veces creyendo que no ha hecho nada.
async function procesarTicket(archivos, datos, btn) {
  const form = new FormData();
  // Todas las páginas bajo el mismo campo `imagen`: repetir el campo es como se
  // manda una lista en multipart, y es lo que el api espera.
  for (const archivo of archivos) form.append("imagen", archivo);
  for (const [clave, valor] of Object.entries(datos)) {
    if (valor) form.append(clave, valor);
  }
  const textoBtn = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Leyendo…";
  marcarLeyendo(true, archivos.length);
  try {
    const ticket = await api("/tickets", { method: "POST", form });
    olvidarTicket();
    cerrarPreguntaDatos();
    ticketPendiente = null;
    await cargarTickets();
    activarPestana("panel-tickets");
    mostrarTicket(ticket);
    mensaje(`Ticket procesado: ${ticket.lineas.length} línea(s)`);
  } catch (err) {
    // 422 con la lista de lo que falta: el ticket no se ha creado y hay que
    // preguntarlo antes de seguir.
    if (err.detail && Array.isArray(err.detail.faltan)) {
      preguntarDatosQueFaltan(archivos, err.detail.faltan);
    } else {
      mensaje(err.message, true);
    }
  } finally {
    btn.disabled = false;
    btn.textContent = textoBtn;
    marcarLeyendo(false);
    // Si las páginas siguen puestas (fallo, o falta un dato que preguntar), el
    // recuadro vuelve a decir cuáles son; si se procesó bien, olvidarTicket()
    // ya lo ha dejado vacío.
    rotularZona(paginasElegidas());
  }
}

function preguntarDatosQueFaltan(archivos, faltan) {
  ticketPendiente = archivos;
  const pideSuper = faltan.includes("supermercado_id");
  const pideFecha = faltan.includes("fecha_compra");
  $("campo-super").classList.toggle("hidden", !pideSuper);
  $("campo-fecha").classList.toggle("hidden", !pideFecha);
  $("faltan-texto").textContent = pideSuper && pideFecha
    ? "No he sabido leer el supermercado ni la fecha en el ticket."
    : pideSuper
      ? "No he sabido leer de qué supermercado es el ticket."
      : "No he sabido leer la fecha de compra en el ticket.";
  $("card-subir").classList.add("hidden");
  $("card-faltan").classList.remove("hidden");
  (pideSuper ? $("sel-supermercado") : $("ticket-fecha")).focus();
}

function cerrarPreguntaDatos() {
  $("card-faltan").classList.add("hidden");
  $("card-subir").classList.remove("hidden");
  $("form-faltan").reset();
  $("nuevo-super").classList.add("hidden");
}

$("btn-faltan-cancelar").addEventListener("click", () => {
  ticketPendiente = null;
  cerrarPreguntaDatos();
  olvidarTicket();
});

// Crear el supermercado desde aquí: es el único sitio donde hace falta, y con
// el catálogo vacío (usuario nuevo) es además el camino obligado.
$("sel-supermercado").addEventListener("change", () => {
  const creando = $("sel-supermercado").value === SUPER_NUEVO;
  $("nuevo-super").classList.toggle("hidden", !creando);
  if (creando) $("nuevo-super").focus();
});

$("form-faltan").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!ticketPendiente) return;
  const datos = {};

  if (!$("campo-super").classList.contains("hidden")) {
    const sel = $("sel-supermercado");
    if (sel.value === SUPER_NUEVO) {
      const nombre = $("nuevo-super").value.trim();
      if (!nombre) {
        mensaje("Escribe el nombre del supermercado", true);
        return;
      }
      try {
        const creado = await api("/supermercados", {
          method: "POST",
          json: { nombre },
        });
        await cargarSupermercados();
        datos.supermercado_id = creado.id;
      } catch (err) {
        mensaje(err.message, true);
        return;
      }
    } else if (sel.value) {
      datos.supermercado_id = sel.value;
    } else {
      mensaje("Elige el supermercado", true);
      return;
    }
  }

  if (!$("campo-fecha").classList.contains("hidden")) {
    if (!$("ticket-fecha").value) {
      mensaje("Indica la fecha de compra", true);
      return;
    }
    datos.fecha_compra = $("ticket-fecha").value;
  }

  await procesarTicket(
    ticketPendiente,
    datos,
    e.target.querySelector("button[type=submit]"),
  );
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
    return [];
  }
  const cont = $("lista-tickets");
  cont.textContent = "";

  if (!tickets.length) {
    const p = document.createElement("p");
    p.className = "vacio";
    p.textContent = "Todavía no has subido ningún ticket.";
    cont.appendChild(p);
    return tickets;
  }

  // Más recientes primero: lo que se acaba de subir es lo que se va a asociar.
  tickets.sort((a, b) => b.fecha_compra.localeCompare(a.fecha_compra) || b.id - a.id);
  for (const t of tickets) cont.appendChild(filaTicket(t));
  return tickets;
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

function mostrarTicket(ticket, { animar = true } = {}) {
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
  // segundo ticket no volvería a "imprimirlo". Al repintar tras asociar una
  // línea no se anima: reimprimir el ticket entero a cada confirmación marea.
  if (animar) {
    card.classList.remove("imprimiendo");
    void card.offsetWidth;
    card.classList.add("imprimiendo");
  }

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
    tdProducto.appendChild(selectorProducto(linea));
    // Zona dudosa (§5bis punto 3): en vez de buscar el producto en la lista, se
    // ofrecen los parecidos. Se piden aparte para no bloquear el pintado.
    pintarSugerencias(linea, tdProducto);
  }
  tr.append(tdTexto, tdPrecio, tdProducto);
  return tr;
}

// Valor centinela de la opción "crear": no puede chocar con ningún id.
const OPCION_NUEVO = "nuevo";

// Elegir de la lista es el caso normal y crear, la excepción. Con un campo de
// texto libre acababan naciendo "LECHE DESNATADA" y "Leche desnatada" como
// productos distintos, y eso parte en dos el histórico de precios justo del
// producto que más se compra.
function selectorProducto(linea) {
  const wrap = document.createElement("div");
  wrap.className = "fila";

  const sel = document.createElement("select");
  sel.setAttribute("aria-label", `Producto para «${linea.texto_original}»`);
  sel.appendChild(new Option("— elige un producto —", ""));
  for (const p of catalogo) {
    sel.appendChild(new Option(p.nombre_normalizado, String(p.id)));
  }
  sel.appendChild(new Option("+ Crear producto nuevo…", OPCION_NUEVO));

  const nombre = document.createElement("input");
  nombre.placeholder = "nombre del producto nuevo";
  nombre.classList.add("hidden");

  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "sec";
  btn.textContent = "Asociar";

  // Con el catálogo vacío el desplegable no ofrece nada que elegir: se abre ya
  // en modo "crear" para que el primer ticket no obligue a pasar por una lista
  // vacía. Sin `focus()`, que aquí habría una fila por línea del ticket.
  if (!catalogo.length) {
    sel.value = OPCION_NUEVO;
    nombre.classList.remove("hidden");
    nombre.value = linea.texto_original;
  }

  sel.addEventListener("change", () => {
    const creando = sel.value === OPCION_NUEVO;
    nombre.classList.toggle("hidden", !creando);
    if (creando) {
      // Se parte del texto del ticket: es lo que se va a escribir de todos
      // modos, y en el móvil ahorra teclear. Sigue siendo editable, que es
      // donde se limpia el ruido del OCR.
      if (!nombre.value) nombre.value = linea.texto_original;
      nombre.focus();
      nombre.select();
    }
  });

  const asociar = async () => {
    let json;
    if (sel.value === OPCION_NUEVO) {
      const texto = nombre.value.trim();
      if (!texto) {
        mensaje("Escribe el nombre del producto nuevo", true);
        nombre.focus();
        return;
      }
      json = { nuevo_producto: { nombre_normalizado: texto } };
    } else if (sel.value) {
      json = { producto_id: Number(sel.value) };
    } else {
      mensaje("Elige un producto de la lista o crea uno nuevo", true);
      sel.focus();
      return;
    }
    btn.disabled = true;
    try {
      await api(`/lineas/${linea.id}/asociar`, { method: "POST", json });
      mensaje("Línea asociada");
      await repintarTrasAsociar();
    } catch (err) {
      mensaje(err.message, true);
      btn.disabled = false;
    }
  };

  btn.addEventListener("click", asociar);
  nombre.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") asociar();
  });

  wrap.append(sel, nombre, btn);
  return wrap;
}

// Tras asociar se repinta el ticket entero en vez de tachar solo esa línea: así
// el desplegable de las líneas que quedan incluye el producto recién creado, y
// sus sugerencias se recalculan con el alias que se acaba de aprender.
async function repintarTrasAsociar() {
  await cargarProductos();
  const tickets = await cargarTickets();
  const abierto = tickets.find((t) => t.id === ticketAbierto);
  if (abierto) mostrarTicket(abierto, { animar: false });
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
        mensaje("Línea asociada");
        await repintarTrasAsociar();
      } catch (err) {
        mensaje(err.message, true);
      }
    });
    cont.appendChild(btn);
  }
  tdProducto.appendChild(cont);
}

// ---- Productos y comparativa ----
// Catálogo en memoria: lo comparten el desplegable de cada línea sin asociar y
// el de la comparativa, así asociar no dispara una petición por fila.
let catalogo = [];

async function cargarProductos() {
  const productos = await api("/productos");
  // Por nombre: en un desplegable, el orden de creación no ayuda a nadie.
  productos.sort((a, b) =>
    a.nombre_normalizado.localeCompare(b.nombre_normalizado, "es"),
  );
  catalogo = productos;
}

// ---- Buscador de productos con sugerencias ----
// Se pregunta al api en vez de filtrar el catálogo que ya está en memoria: ese
// se carga una vez al entrar y se queda viejo en cuanto alguien confirma una
// línea, y además crece sin tope. El servidor ya sabe buscar y limitar.
const SUGERENCIAS = 8;

// Lo seleccionado en cada buscador. `b` solo existe si se ha pedido comparar.
const elegido = { a: null, b: null };

// `alElegir` decide qué pasa al elegir: el tab Productos lo enseña, la lista de
// la compra lo añade. Todo lo demás (sugerencias, teclado, carreras) es igual en
// los dos sitios y no tiene por qué duplicarse.
function montarBuscador(clave, alElegir) {
  const entrada = $(`busca-${clave}`);
  const lista = $(`sug-${clave}`);
  let opciones = [];
  let marcada = -1;
  let peticion = 0;
  let temporizador;

  function cerrar() {
    lista.classList.add("hidden");
    lista.replaceChildren();
    entrada.setAttribute("aria-expanded", "false");
    entrada.removeAttribute("aria-activedescendant");
    opciones = [];
    marcada = -1;
  }

  function marcar(i) {
    marcada = i;
    [...lista.children].forEach((li, n) => {
      const activa = n === i;
      li.classList.toggle("marcada", activa);
      li.setAttribute("aria-selected", String(activa));
    });
    if (i >= 0) {
      entrada.setAttribute("aria-activedescendant", lista.children[i].id);
      lista.children[i].scrollIntoView({ block: "nearest" });
    }
  }

  function elegir(producto) {
    cerrar();
    alElegir(producto, entrada);
  }

  async function buscar(texto) {
    // Cada tecla lanza una petición y las respuestas pueden llegar
    // desordenadas: se descarta todo lo que no sea la última pedida, o una
    // búsqueda vieja repinta encima de la nueva.
    const mia = ++peticion;
    let productos;
    try {
      productos = await api(
        `/productos?q=${encodeURIComponent(texto)}&limite=${SUGERENCIAS}`,
      );
    } catch (err) {
      mensaje(err.message, true);
      return;
    }
    if (mia !== peticion) return;

    opciones = productos;
    lista.replaceChildren();
    if (!productos.length) {
      const li = document.createElement("li");
      li.className = "sin-resultados";
      li.textContent = "Nada con ese nombre";
      lista.appendChild(li);
    } else {
      productos.forEach((p, i) => {
        const li = document.createElement("li");
        li.id = `sug-${clave}-${i}`;
        li.role = "option";
        li.textContent = p.nombre_normalizado;
        li.setAttribute("aria-selected", "false");
        // mousedown y no click: el blur del input llega antes que el click y
        // cerraría la lista justo debajo del dedo.
        li.addEventListener("mousedown", (e) => {
          e.preventDefault();
          elegir(p);
        });
        lista.appendChild(li);
      });
    }
    lista.classList.remove("hidden");
    entrada.setAttribute("aria-expanded", "true");
    marcar(-1);
  }

  entrada.addEventListener("input", () => {
    const texto = entrada.value.trim();
    // Lo escrito ya no corresponde a lo elegido: se suelta para que el
    // resultado no siga enseñando un producto que no es el del cuadro.
    if (elegido[clave] && texto !== elegido[clave].nombre_normalizado) {
      elegido[clave] = null;
      pintarProductos();
    }
    clearTimeout(temporizador);

    if (!texto) {
      cerrar();
      return;
    }
    // Sin esta espera se lanza una petición por pulsación.
    temporizador = setTimeout(() => buscar(texto), 200);
  });

  entrada.addEventListener("keydown", (e) => {
    if (e.key === "Escape") return cerrar();
    if (!opciones.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      marcar((marcada + 1) % opciones.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      marcar((marcada - 1 + opciones.length) % opciones.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      // Sin nada resaltado, Enter coge la primera: es lo que espera quien
      // escribe y pulsa Enter sin mirar.
      elegir(opciones[marcada >= 0 ? marcada : 0]);
    }
  });

  entrada.addEventListener("blur", () => setTimeout(cerrar, 0));
}

const alElegirEnProductos = (clave) => (producto, entrada) => {
  elegido[clave] = producto;
  entrada.value = producto.nombre_normalizado;
  pintarProductos();
};
montarBuscador("a", alElegirEnProductos("a"));
montarBuscador("b", alElegirEnProductos("b"));

$("btn-comparar-otro").addEventListener("click", () => {
  $("campo-b").classList.remove("hidden");
  $("btn-comparar-otro").classList.add("hidden");
  $("btn-quitar-b").classList.remove("hidden");
  $("busca-b").focus();
});

$("btn-quitar-b").addEventListener("click", () => {
  elegido.b = null;
  $("busca-b").value = "";
  $("campo-b").classList.add("hidden");
  $("btn-quitar-b").classList.add("hidden");
  $("btn-comparar-otro").classList.remove("hidden");
  pintarProductos();
});

// Los precios de lo elegido. Se piden aquí y no al elegir para que el bloque
// de comparar tenga los dos a la vez sin guardarlos por separado.
async function pintarProductos() {
  // Comparar no tiene sentido sin un primer producto elegido.
  $("btn-comparar-otro").disabled = !elegido.a;

  const cont = $("resultado-precios");
  if (!elegido.a) {
    cont.replaceChildren();
    return;
  }
  let datos;
  try {
    datos = await Promise.all(
      [elegido.a, elegido.b]
        .filter(Boolean)
        .map((p) => api(`/productos/${p.id}/precios`)),
    );
  } catch (err) {
    mensaje(err.message, true);
    return;
  }
  cont.replaceChildren();
  // Con dos productos, el veredicto es el papel de abajo. Si cada uno sellara
  // además su «más barato», habría tres sellos en pantalla y el sello dejaría
  // de significar nada: está reservado a una vez por resultado.
  const duelo = datos.length === 2;
  for (const data of datos) mostrarComparativa(data, { limpiar: false, sello: !duelo });
  if (duelo) mostrarDuelo(datos);
}

// Cuál de los dos productos sale más barato, cada uno a su mejor precio. Es la
// pregunta que se hace quien compara dos productos, y no la contesta ninguna de
// las dos tablas por separado.
function mostrarDuelo([uno, otro]) {
  const mejor = (data) => data.supermercados[0];
  if (!mejor(uno) || !mejor(otro)) return;

  const papel = papelNuevo($("resultado-precios"), "Cuál sale mejor", {
    limpiar: false,
  });
  const filas = [uno, otro]
    .map((data) => ({ data, precio: Number(mejor(data).precio_actual) }))
    .sort((x, y) => x.precio - y.precio);

  papel.appendChild(
    tablaRecibo(
      ["Producto", "Dónde", "Precio"],
      filas.map((f, i) => ({
        gana: i === 0,
        celdas: [
          f.data.nombre_normalizado,
          mejor(f.data).supermercado,
          euros(mejor(f.data).precio_actual),
        ],
      })),
    ),
  );

  // Sin «diferencia»: restarle el pan a la leche no es un dato de nada, y quien
  // compare dos marcas del mismo producto tiene los dos precios ahí al lado.
  papel.append(raya(true));
  papel.appendChild(sello("Más barato", filas[0].data.nombre_normalizado));
}

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
// `limpiar: false` para apilar varios papeles en el mismo contenedor, que es lo
// que hace falta al comparar dos productos. Por defecto sigue sustituyendo,
// como esperan el ticket y la cesta.
function papelNuevo(cont, titulo, { limpiar = true } = {}) {
  if (limpiar) cont.textContent = "";
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

function vacio(cont, texto, { limpiar = true } = {}) {
  if (limpiar) cont.textContent = "";
  const p = document.createElement("p");
  p.className = "vacio";
  p.textContent = texto;
  cont.appendChild(p);
}

function mostrarComparativa(data, opciones = {}) {
  const cont = $("resultado-precios");
  if (!data.supermercados.length) {
    vacio(cont, `Todavía no hay precios de «${data.nombre_normalizado}». Sube un ticket que lo incluya.`, opciones);
    return;
  }

  const papel = papelNuevo(cont, data.nombre_normalizado, opciones);
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
    if (opciones.sello !== false) {
      papel.appendChild(sello("Más barato", barato.supermercado));
    }
  }
}

// ---- Lista de la compra ----
// La lista vive aquí, en el navegador, y se manda entera para calcular: el api
// no la guarda. Una lista es cosa de un rato, y persistirla traería su propio
// CRUD y su borrado sin que nadie lo haya pedido.
let listaCompra = [];

montarBuscador("lista", (producto, entrada) => {
  // El cuadro se vacía en vez de quedarse con el nombre: aquí no se «elige» un
  // producto, se van añadiendo, y lo siguiente que se hace es buscar otro.
  entrada.value = "";
  if (listaCompra.some((p) => p.id === producto.id)) {
    mensaje(`«${producto.nombre_normalizado}» ya está en la lista`);
    return;
  }
  listaCompra.push(producto);
  actualizarLista();
});

$("btn-vaciar-lista").addEventListener("click", () => {
  listaCompra = [];
  actualizarLista();
});

async function actualizarLista() {
  const hayAlgo = listaCompra.length > 0;
  $("lista-vacia").classList.toggle("hidden", hayAlgo);
  $("btn-vaciar-lista").classList.toggle("hidden", !hayAlgo);
  if (!hayAlgo) {
    $("lista-compra").replaceChildren();
    $("resultado-lista").replaceChildren();
    return;
  }

  let datos;
  try {
    datos = await api("/cesta/lista", {
      method: "POST",
      json: { producto_ids: listaCompra.map((p) => p.id) },
    });
  } catch (err) {
    mensaje(err.message, true);
    return;
  }
  pintarRenglones(datos.productos);
  mostrarDondeComprar(datos);
}

function pintarRenglones(productos) {
  const ul = $("lista-compra");
  ul.replaceChildren();
  for (const producto of productos) {
    const li = document.createElement("li");
    li.className = "renglon";

    const cabeza = document.createElement("div");
    cabeza.className = "renglon-cabeza";
    const nombre = document.createElement("span");
    nombre.className = "renglon-nombre";
    nombre.textContent = producto.nombre_normalizado;
    cabeza.append(
      nombre,
      boton("Quitar", "ghost quitar", () => {
        listaCompra = listaCompra.filter((p) => p.id !== producto.producto_id);
        actualizarLista();
      }),
    );

    const precios = document.createElement("p");
    precios.className = "renglon-precios";
    if (!producto.supermercados.length) {
      precios.classList.add("sin-precio");
      precios.textContent = "Sin precios todavía · sube un ticket que lo incluya";
    } else {
      // De menor a mayor, como los devuelve el api. El primero es dónde
      // comprarlo, y por eso es el único que va marcado.
      producto.supermercados.forEach((s, i) => {
        const trozo = document.createElement("span");
        trozo.className = i === 0 ? "precio-sm gana" : "precio-sm";
        trozo.textContent = `${s.supermercado} ${euros(s.precio_actual)}`;
        precios.appendChild(trozo);
      });
    }

    li.append(cabeza, precios);
    ul.appendChild(li);
  }
}

// El veredicto sí es papel emitido por la máquina: lleva dentado y sello, como
// el ticket y la comparativa.
function mostrarDondeComprar(datos) {
  const cont = $("resultado-lista");
  const total = datos.productos.length;
  if (!datos.supermercados.length) {
    vacio(cont, "Ninguno de estos productos tiene precios todavía. Sube un ticket que los incluya.");
    return;
  }

  const papel = papelNuevo(cont, "Dónde comprar");
  papel.appendChild(
    tablaRecibo(
      ["Supermercado", "Cubre", "Total"],
      datos.supermercados.map((s, i) => ({
        gana: i === 0,
        celdas: [s.supermercado, `${s.productos_cubiertos}/${total}`, euros(s.total)],
      })),
    ),
  );
  papel.append(raya(true));

  const mejor = datos.supermercados[0];
  if (mejor.productos_cubiertos === total) {
    papel.append(lineaTotal("Total", euros(mejor.total)));
    papel.appendChild(sello("Compra aquí", mejor.supermercado));
  } else {
    // Sellar al que cubre la mitad sería recomendar una compra que no se puede
    // hacer. Se dice lo que hay y no se sella nada.
    const aviso = document.createElement("p");
    aviso.className = "aviso-cobertura";
    aviso.textContent =
      `Ningún supermercado tiene precios de los ${total} productos. ` +
      `${mejor.supermercado} es el que más cubre (${mejor.productos_cubiertos}), ` +
      "así que los totales no son comparables entre sí.";
    papel.appendChild(aviso);
  }
}

// ---- Panel de administración ----
// Esconder el tab no protege nada: cada endpoint de admin vuelve a comprobar el
// rol. Solo evita enseñar botones que darían 403.
let soyAdmin = false;
// Hace falta para no ofrecer sobre la propia fila acciones que el api rechaza
// siempre (409): la cuenta de uno se gestiona desde su perfil.
let miId = null;

async function comprobarRol() {
  try {
    const yo = await api("/auth/me");
    soyAdmin = yo.rol === "admin";
    miId = yo.id;
  } catch {
    soyAdmin = false; // el 401 ya lo gestiona api()
    miId = null;
  }
  $("tab-admin").classList.toggle("hidden", !soyAdmin);
}

// `etiquetas` son los mismos rótulos de la cabecera: en móvil la fila se apila
// como una ficha y cada dato necesita el suyo delante, porque la cabecera de la
// tabla deja de verse (mismo patrón que las líneas del ticket).
function filaCeldas(valores, etiquetas = []) {
  const tr = document.createElement("tr");
  valores.forEach((valor, i) => {
    const td = document.createElement("td");
    if (etiquetas[i]) td.dataset.label = etiquetas[i];
    if (valor instanceof Node) td.appendChild(valor);
    else td.textContent = valor;
    tr.appendChild(td);
  });
  return tr;
}

function cabecera(nombres) {
  const thead = document.createElement("thead");
  const tr = document.createElement("tr");
  for (const nombre of nombres) {
    const th = document.createElement("th");
    th.textContent = nombre;
    tr.appendChild(th);
  }
  thead.appendChild(tr);
  return thead;
}

function boton(texto, clase, alPulsar) {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = texto;
  if (clase) b.className = clase;
  b.addEventListener("click", alPulsar);
  return b;
}

// Todo borrado del panel es irreversible y sobre datos de otros: se confirma.
async function confirmando(pregunta, accion, recargar) {
  if (!confirm(pregunta)) return;
  try {
    await accion();
    await recargar();
  } catch (err) {
    mensaje(err.message, true);
  }
}

async function cargarAdmin() {
  await Promise.all([cargarAdminUsuarios(), cargarAdminProductos(), cargarAdminSupers()]);
}

// Lo que hay se filtra en el navegador y no en el api: son listas cortas (las
// cuentas y el catálogo de una instalación), ya están pedidas, y así el filtro
// responde sin ir y volver.
const filtrar = (texto, campos) =>
  campos.some((c) => (c || "").toLowerCase().includes(texto.toLowerCase()));

let usuariosAdmin = [];

async function cargarAdminUsuarios() {
  usuariosAdmin = await api("/usuarios");
  pintarAdminUsuarios();
}

function pintarAdminUsuarios() {
  const tabla = $("tabla-usuarios");
  const q = $("admin-q-usuarios").value.trim();
  const lista = usuariosAdmin.filter((u) => filtrar(q, [u.nombre, u.email]));

  const cols = ["Nombre", "Correo", "Rol", "", ""];
  tabla.replaceChildren(cabecera(cols));
  const cuerpo = document.createElement("tbody");
  for (const u of lista) {
    const esAdmin = u.rol === "admin";
    // Sobre la propia cuenta el api contesta 409 a las dos acciones (borrarse
    // aquí se saltaría la contraseña, y bajarse el rol deja la instalación sin
    // admin). Ofrecer botones que siempre fallan sería mentir.
    if (u.id === miId) {
      cuerpo.appendChild(
        filaCeldas(
          [u.nombre, u.email, u.rol, "— tu cuenta, se gestiona desde tu perfil —", ""],
          cols,
        ),
      );
      continue;
    }
    cuerpo.appendChild(
      filaCeldas([
        u.nombre,
        // Sin confirmar no se puede entrar: es una cuenta muerta y conviene que
        // se note al mirar la lista.
        u.email_verificado ? u.email : `${u.email} (sin confirmar)`,
        u.rol,
        boton(esAdmin ? "Quitar admin" : "Hacer admin", "sec", () =>
          confirmando(
            esAdmin
              ? `¿Quitar el rol de administrador a ${u.nombre}?`
              : `¿Hacer administrador a ${u.nombre}?`,
            () =>
              api(`/usuarios/${u.id}`, {
                method: "PATCH",
                json: { rol: esAdmin ? "usuario" : "admin" },
              }),
            cargarAdminUsuarios,
          ),
        ),
        boton("Borrar", "ghost", () =>
          confirmando(
            `¿Borrar la cuenta de ${u.nombre}? Sus tickets se desvinculan, así que sus precios se conservan. No se puede deshacer.`,
            () => api(`/usuarios/${u.id}`, { method: "DELETE" }),
            cargarAdminUsuarios,
          ),
        ),
      ], cols),
    );
  }
  tabla.appendChild(cuerpo);
  if (!lista.length) tabla.appendChild(filaCeldas(["Ninguna cuenta con ese texto"]));
}

$("admin-q-usuarios").addEventListener("input", pintarAdminUsuarios);

let productosAdmin = [];

async function cargarAdminProductos() {
  productosAdmin = await api("/productos");
  pintarAdminProductos();
}

function pintarAdminProductos() {
  const tabla = $("tabla-productos");
  const q = $("admin-q-productos").value.trim();
  const lista = productosAdmin.filter((p) =>
    filtrar(q, [p.nombre_normalizado, p.categoria, p.unidad_medida]),
  );

  tabla.replaceChildren(cabecera(COLS_PRODUCTO));
  const cuerpo = document.createElement("tbody");
  for (const p of lista) cuerpo.appendChild(filaProducto(p));
  tabla.appendChild(cuerpo);
  if (!lista.length) tabla.appendChild(filaCeldas(["Ningún producto con ese texto"]));
}

const COLS_PRODUCTO = ["Nombre", "Categoría", "Unidad", "", ""];

function filaProducto(p) {
  return filaCeldas([
    p.nombre_normalizado,
    // Vacio y no "—": en movil la celda vacia desaparece en vez de gastar un
    // renglon entero para decir que no hay dato.
    p.categoria || "",
    p.unidad_medida || "",
    boton("Editar", "sec", (e) => {
      e.target.closest("tr").replaceWith(filaProductoEditable(p));
    }),
    boton("Borrar", "ghost", () =>
      confirmando(
        `¿Borrar «${p.nombre_normalizado}» del catálogo?`,
        () => api(`/productos/${p.id}`, { method: "DELETE" }),
        cargarAdminProductos,
      ),
    ),
  ], COLS_PRODUCTO);
}

// Se edita en la propia fila: abrir otra pantalla para cambiar tres campos
// obliga a perder de vista la lista que se está repasando.
function filaProductoEditable(p) {
  const campo = (valor, etiqueta) => {
    const input = document.createElement("input");
    input.value = valor || "";
    input.setAttribute("aria-label", etiqueta);
    return input;
  };
  const nombre = campo(p.nombre_normalizado, "Nombre");
  const categoria = campo(p.categoria, "Categoría");
  const unidad = campo(p.unidad_medida, "Unidad de medida");

  const fila = filaCeldas([
    nombre,
    categoria,
    unidad,
    boton("Guardar", null, async () => {
      if (!nombre.value.trim()) {
        mensaje("El nombre no puede quedar vacío", true);
        return;
      }
      try {
        await api(`/productos/${p.id}`, {
          method: "PATCH",
          json: {
            nombre_normalizado: nombre.value.trim(),
            // Vaciar el campo es querer quitar el dato, y la API acepta null.
            categoria: categoria.value.trim() || null,
            unidad_medida: unidad.value.trim() || null,
          },
        });
        await cargarAdminProductos();
        mensaje("Producto actualizado");
      } catch (err) {
        mensaje(err.message, true);
      }
    }),
    boton("Cancelar", "sec", () => fila.replaceWith(filaProducto(p))),
  ], COLS_PRODUCTO);
  return fila;
}

$("admin-q-productos").addEventListener("input", pintarAdminProductos);

async function cargarAdminSupers() {
  const supers = await api("/supermercados");
  const tabla = $("tabla-supermercados");
  tabla.replaceChildren(cabecera(COLS_SUPER));
  const cuerpo = document.createElement("tbody");
  for (const sm of supers) cuerpo.appendChild(filaSuper(sm));
  tabla.appendChild(cuerpo);
}

const COLS_SUPER = ["Nombre", "", ""];

function filaSuper(sm) {
  return filaCeldas([
    sm.nombre,
    boton("Editar", "sec", (e) => {
      e.target.closest("tr").replaceWith(filaSuperEditable(sm));
    }),
    boton("Borrar", "ghost", () =>
      confirmando(
        `¿Borrar el supermercado «${sm.nombre}»?`,
        () => api(`/supermercados/${sm.id}`, { method: "DELETE" }),
        cargarAdminSupers,
      ),
    ),
  ], COLS_SUPER);
}

function filaSuperEditable(sm) {
  const nombre = document.createElement("input");
  nombre.value = sm.nombre;
  nombre.setAttribute("aria-label", "Nombre del supermercado");

  const fila = filaCeldas([
    nombre,
    boton("Guardar", null, async () => {
      if (!nombre.value.trim()) {
        mensaje("El nombre no puede quedar vacío", true);
        return;
      }
      try {
        await api(`/supermercados/${sm.id}`, {
          method: "PATCH",
          json: { nombre: nombre.value.trim() },
        });
        await cargarAdminSupers();
        await cargarSupermercados();
        mensaje("Supermercado actualizado");
      } catch (err) {
        mensaje(err.message, true);
      }
    }),
    boton("Cancelar", "sec", () => fila.replaceWith(filaSuper(sm))),
  ], COLS_SUPER);
  return fila;
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
