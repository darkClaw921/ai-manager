FROM nginx:alpine

RUN apk add --no-cache curl ca-certificates \
    && rm /etc/nginx/conf.d/default.conf \
    && mkdir -p /etc/letsencrypt \
    && mkdir -p /var/www/certbot

COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
