# Imagen nginx que corre como usuario no-root y sirve en el puerto 8080 (NFR2).
FROM nginxinc/nginx-unprivileged:alpine

# Sustituye la config de la imagen para fijar Cache-Control: sin ella el
# navegador se queda los ficheros dias y no ve los despliegues (ver default.conf).
COPY default.conf /etc/nginx/conf.d/default.conf
COPY index.html styles.css app.js /usr/share/nginx/html/

# Valida la configuracion durante el build: una config rota aqui deja el
# frontend caido, y desde que produccion descarga imagenes ya no hay red de
# seguridad. Que falle el CI y no el despliegue.
RUN nginx -t

EXPOSE 8080
