FROM nginx:1.24

# Installation de certbot pour Let's Encrypt
RUN apt-get update && apt-get install -y certbot python3-certbot-nginx && apt-get clean

COPY config/nginx.conf /etc/nginx/nginx.conf
EXPOSE 80 443