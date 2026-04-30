FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY workflows/ /usr/share/nginx/html/workflows/
# Fix permissions — nginx worker runs as nginx user
RUN chmod -R 644 /usr/share/nginx/html/workflows/ && \
    chmod 755 /usr/share/nginx/html/workflows/
EXPOSE 80
