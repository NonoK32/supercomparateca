# frontend

Interfaz web simple (incluida desde el MVP): **HTML + CSS + JavaScript vanilla**,
sin framework ni paso de build. Se sirve con **nginx** (imagen no-root) y habla con
el `api` por HTTP.

Permite: registro/login, subir un ticket, confirmar a qué producto corresponde
cada línea y comparar el precio de un producto entre supermercados.

## Pestañas

`Subir` · `Tickets` · `Productos` · `Cesta` · `Admin` (esta última solo si
`GET /auth/me` dice que el rol es `admin`).

**Productos** sustituyó al antiguo «Comparar precios», que era un `<select>` con el
catálogo entero. Ahora es un buscador que sugiere según se escribe, preguntando al
api (`GET /productos?q=&limite=8`) en vez de filtrar la copia en memoria: esa se carga
al entrar y se queda vieja en cuanto alguien confirma una línea. Es un combobox ARIA
con teclado (`↓ ↑`, `Enter`, `Esc`) y las peticiones fuera de orden se descartan, o
una búsqueda vieja repinta encima de la nueva. Al elegir se ve el producto con su
precio en cada supermercado; **Comparar con otro** añade un segundo y pinta un tercer
papel con cuál sale más barato a su mejor precio.

**Admin** es solo cosmético: cada endpoint del `api` vuelve a comprobar el rol, así
que esconder la pestaña no protege nada — únicamente evita enseñar botones que
darían 403. Se puebla al abrirla, no al entrar en la app.

## Cómo entra el ticket

Dos formas, a elegir con los botones de la tarjeta «Subir ticket»:

- **Subir archivo** — imágenes o un **PDF** (`accept="image/*,application/pdf"`,
  `multiple`), eligiéndolos o arrastrándolos. De un PDF no hay miniatura: un `<img>`
  no lo pinta, así que en la tira sale su nombre.
- **Escanear con la cámara** — `getUserMedia` con la cámara trasera (`ideal`, no
  `exact`: en un portátil no existe y hay que caer en la que haya), y el fotograma
  se dibuja en un `<canvas>` **a la resolución del sensor**, no a la que se ve en
  pantalla — la letra de un ticket es pequeña y el OCR necesita esos píxeles.

**Un ticket largo no cabe en una foto**, así que se sube en varias páginas y el `api`
las lee como un único documento. En la cámara, cada *Capturar* **añade** una página y
la cámara **sigue abierta** (reabrirla en cada trozo es esperar otra vez a que
arranque); se sale con *Terminar*, que lleva a la tira de miniaturas — donde se
comprueba que no falta nada antes de gastar el OCR, que son segundos por página. El
selector y arrastrar y soltar, en cambio, **sustituyen** la selección: es lo que hace
un `<input type=file multiple>` y lo que se espera al volver a elegir.

**El orden importa**: el supermercado se busca solo en la cabecera, que es la de la
primera página. Y el tope es de **10 páginas**, el mismo que aplica el `api`
(`MAX_ARCHIVOS` en los dos sitios); aquí se avisa antes para no gastar una subida
entera en un 400 previsible.

Nada de esto es un segundo camino de subida: las páginas —vengan de la cámara, del
selector o de arrastrar— viven todas en el mismo `<input type=file>` (vía
`DataTransfer`), así que las miniaturas, el envío y la segunda pasada del OCR leen de
un único sitio. En el envío van repetidas bajo el mismo campo `imagen`, que es como
se manda una lista en multipart.

Tres cosas que se rompen con facilidad:

- **`getUserMedia` no existe fuera de un contexto seguro.** HTTPS o `localhost`.
  Servido por `http://` en una IP de la red local no está definido, y por eso el
  botón de la cámara **nace oculto** y solo se muestra si el navegador la ofrece:
  un botón que no puede funcionar es peor que no tenerlo.
- **Hay que parar las pistas del flujo, no basta con ocultar el vídeo**, o el piloto
  de la cámara se queda encendido. Se cierra al capturar, al volver a «Subir
  archivo», al cambiar de pestaña (`activarPestana`) y al salir de la sesión
  (`mostrarAuth`, que es por donde se pasa tanto al cerrar sesión como al caducar el
  token o borrar la cuenta). Ojo: ya **no** se cierra al capturar, justamente para
  poder encadenar páginas.
- **Las miniaturas son `URL.createObjectURL`** y se quedan en memoria hasta que se
  revocan. `pintarPaginas()` repinta la tira entera en cada captura, así que revoca
  las de la tanda anterior antes de crear las nuevas.

Si algún día se le pone una cabecera `Permissions-Policy` a nginx, necesita
`camera=(self)` o la cámara deja de abrirse. Lo mismo que ya pasa con la CSP y
`challenges.cloudflare.com` para el widget de Turnstile.

## Ejecutar

Se levanta con el resto del stack:

```bash
docker compose up --build
```

- Frontend en `http://localhost:8090`.
- Espera el `api` en `http://<host>:8000` (ver `API_BASE` en `app.js`).

El `api` debe permitir el origen del frontend por CORS (`CORS_ORIGINS`, ya
configurado en `docker-compose.yml`).

## Archivos

- `index.html` — estructura y vistas (auth / app).
- `styles.css` — estilos.
- `app.js` — lógica: llamadas a la API, token en `localStorage`, render de tablas.
