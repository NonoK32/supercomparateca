# Imagen nginx que corre como usuario no-root y sirve en el puerto 8080 (NFR2).
FROM nginxinc/nginx-unprivileged:alpine

COPY index.html styles.css app.js /usr/share/nginx/html/

EXPOSE 8080
