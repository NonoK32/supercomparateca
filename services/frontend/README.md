# frontend

Interfaz web simple (incluida desde el MVP): **HTML + CSS + JavaScript vanilla**,
sin framework ni paso de build. Se sirve con **nginx** (imagen no-root) y habla con
el `api` por HTTP.

Permite: registro/login, subir la foto de un ticket, confirmar a qué producto
corresponde cada línea y comparar el precio de un producto entre supermercados.

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
