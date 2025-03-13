# Sécurisation du service web public pour WoodyToys

## 1. Organisation de l'environnement de travail

```bash
# Création d'une structure organisée pour les fichiers de configuration
mkdir -p ~/web-secure
cd ~/web-secure

# Copie des fichiers existants du TP5 comme base de travail
cp -r ~/web/* ./
```

## 2. Sécurisation du serveur (Hardening)

### 2.1 Vérification de la sécurité du VPS

```bash
# Vérification des ports ouverts
sudo ufw status
sudo netstat -tulnp

# Vérification de la version de Docker Engine
docker --version

# Analyse des ports exposés
sudo nmap -sS -p- localhost
```

### 2.2. Vérification des images Docker

```bash
# Vérification des images utilisées (versions spécifiques au lieu de "latest")
docker images

# Vérification des ports exposés par container
docker ps --format "{{.Names}}: {{.Ports}}"
```

## 3. Sécurisation des données

### 3.1 Isolation de la base de données avec des réseaux Docker dédiés

Nous avons créé deux réseaux Docker distincts pour isoler la base de données :

```bash
# Mise à jour du fichier docker-compose.yaml
cat > docker-compose.yaml << 'EOF'
services:
  web:
    container_name: web
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./html:/var/www/html
      - ./config/nginx.conf:/etc/nginx/nginx.conf
      - letsencrypt:/etc/letsencrypt
    depends_on:
      - php
    restart: unless-stopped
    networks:
      - dmz

  php:
    container_name: php
    build:
      context: ./php
      dockerfile: Dockerfile
    volumes:
      - ./html/www:/var/www/html/www
    restart: unless-stopped
    networks:
      - dmz
      - db_net
    env_file: 
      - db.env

  db:
    container_name: db
    image: mariadb:11.1
    volumes:
      - db-data:/var/lib/mysql
      - ./woodytoys.sql:/docker-entrypoint-initdb.d/woodytoys.sql
      - ./db/my-resolve.cnf:/etc/mysql/conf.d/my-resolve.cnf
    env_file:
      - db/root.env
      - db.env
    restart: unless-stopped
    networks:
      - db_net

networks:
  dmz:
    driver: bridge
  db_net:
    driver: bridge

volumes:
  db-data:
  letsencrypt:
EOF
```

### 3.2 Configuration de la résolution de noms dans MariaDB

```bash
# Création du répertoire pour la configuration MariaDB
mkdir -p db

# Configuration pour activer la résolution de noms
cat > db/my-resolve.cnf << 'EOF'
[mariadb]
disable-skip-name-resolve=1
EOF
```

### 3.3 Création d'un utilisateur avec privilèges limités pour l'accès à la DB

```bash
# Création des fichiers d'environnement
cat > db/root.env << 'EOF'
MARIADB_ROOT_PASSWORD=MySecureRootPassword123
EOF

cat > db.env << 'EOF'
MARIADB_HOST=db
MARIADB_DATABASE=woodytoys
MARIADB_USER=wt-user
MARIADB_PASSWORD=wt-secure-pwd123
EOF

# Mise à jour du script SQL pour créer un utilisateur avec accès restreint
cat > woodytoys.sql << 'EOF'
USE woodytoys;

CREATE TABLE products (
  id mediumint(8) unsigned NOT NULL auto_increment,
  product_name varchar(255) default NULL,
  product_price varchar(255) default NULL,
  PRIMARY KEY (id)
) AUTO_INCREMENT=1;

INSERT INTO products (product_name,product_price) VALUES 
  ("Set de 100 cubes multicolores","50"),
  ("Yoyo","10"),
  ("Circuit de billes","75"),
  ("Arc à flèches","20"),
  ("Maison de poupées","150");

-- Création d'un utilisateur avec privilèges limités
CREATE USER 'wt-user'@'php' IDENTIFIED BY 'wt-secure-pwd123';
GRANT SELECT ON `woodytoys`.* TO 'wt-user'@'php';
FLUSH PRIVILEGES;
EOF
```

### 3.4 Mise à jour du script PHP pour utiliser l'utilisateur non-privilégié

```bash
mkdir -p html/www
cat > html/www/products.php << 'EOF'
<html>
<style>
      table,
      th,
      td {
        padding: 10px;
        border: 1px solid black;
        border-collapse: collapse;
      }
</style>

<head>
<title>Catalogue WoodyToys</title>
</head>

<body>
<h1>Catalogue WoodyToys</h1>

<?php
$dbname = getenv('MARIADB_DATABASE');
$dbuser = getenv('MARIADB_USER');
$dbpass = getenv('MARIADB_PASSWORD');
$dbhost = getenv('MARIADB_HOST');
$connect = mysqli_connect($dbhost, $dbuser, $dbpass) or die("Unable to connect to '$dbhost'");
mysqli_select_db($connect,$dbname) or die("Could not open the database '$dbname'");
$result = mysqli_query($connect,"SELECT id, product_name, product_price FROM products");
?>

<table>
<tr>
    <th>Numéro de produit</th>
    <th>Descriptif</th> 
    <th>Prix</th>
</tr>

<?php
while ($row = mysqli_fetch_array($result)) {
    printf("<tr><th>%s</th> <th>%s</th> <th>%s</th></tr>", $row[0], $row[1],$row[2]);
}
?>

</table>
</body>
</html>
EOF
```

### 3.5 Installation de cron pour les tâches planifiées

```bash
# Installation de cron pour gérer les tâches planifiées
sudo apt-get update
sudo apt-get install -y cron

# Activation du service cron
sudo systemctl enable cron
sudo systemctl start cron
```

### 3.6 Mise en place d'une solution de backup pour la base de données

```bash
# Création d'un script de sauvegarde pour la base de données
cat > backup-db.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d)
BACKUP_DIR=~/backups
mkdir -p $BACKUP_DIR

cd ~/web-secure
PASSWORD=$(grep MARIADB_ROOT_PASSWORD db/root.env | cut -d= -f2)
docker exec db mariadb-dump --all-databases -uroot -p"$PASSWORD" | gzip > $BACKUP_DIR/woodytoys-$DATE.sql.gz

# Nettoyage des sauvegardes anciennes (plus de 30 jours)
find $BACKUP_DIR -name "woodytoys-*.sql.gz" -type f -mtime +30 -delete
EOF

# Rendre le script exécutable
chmod +x backup-db.sh

# Configuration d'une tâche cron pour la sauvegarde quotidienne
(crontab -l 2>/dev/null; echo "0 2 * * * ~/web-secure/backup-db.sh") | crontab -
```

## 4. Sécurisation des communications avec HTTPS

### 4.1 Préparation de l'infrastructure pour HTTPS

```bash
# Mise à jour du Dockerfile pour installer Certbot
cat > Dockerfile << 'EOF'
FROM nginx:1.24

# Installation de certbot pour Let's Encrypt
RUN apt-get update && apt-get install -y certbot python3-certbot-nginx && apt-get clean

COPY config/nginx.conf /etc/nginx/nginx.conf
EXPOSE 80 443
EOF
```

### 4.2 Configuration initiale de Nginx pour HTTPS avec certificat auto-signé

```bash
# Création du répertoire pour les certificats
mkdir -p certificate

# Génération d'un certificat auto-signé
sudo openssl req -nodes -newkey rsa:4096 -keyout certificate/nginx-selfsigned.key -out certificate/nginx-selfsigned.csr -subj "/C=BE/ST=Brabant-Wallon/L=Louvain-la-Neuve/O=WoodyToys/OU=IT/CN=www.m1-3.ephec-ti.be"

# Auto-signature du certificat
sudo openssl x509 -signkey certificate/nginx-selfsigned.key -in certificate/nginx-selfsigned.csr -req -days 365 -out certificate/nginx-selfsigned.crt

# Configuration Nginx pour utiliser le certificat auto-signé
cat > config/nginx.conf << 'EOF'
events {
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format log_per_virtualhost '[$host] $remote_addr [$time_local] $status '
                                   '"$request" $body_bytes_sent';
    access_log /dev/stdout log_per_virtualhost;
    error_log /dev/stderr;

    server {
        listen 80;
        server_name www.m1-3.ephec-ti.be;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl;
        server_name www.m1-3.ephec-ti.be;
        index index.html;
        root /var/www/html/www/;
        
        ssl_certificate /etc/ssl/certs/nginx-selfsigned.crt;
        ssl_certificate_key /etc/ssl/private/nginx-selfsigned.key;
        
        location ~ \.php$ {
            fastcgi_pass php:9000;
            include fastcgi_params;
            fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        }
    }

    server {
        listen 80;
        server_name blog.m1-3.ephec-ti.be;
        index index.html;
        root /var/www/html/blog/;
    }
}
EOF
```

### 4.3 Construction et lancement des containers avec HTTPS

```bash
# Construction et lancement des containers
docker compose down
docker compose build
docker compose up -d

# Test du site web avec HTTPS auto-signé
curl -k https://www.m1-3.ephec-ti.be
```

### 4.4 Obtention d'un certificat Let's Encrypt pour le domaine wildcard

```bash
# Obtention d'un certificat wildcard avec le challenge DNS
docker compose exec web certbot certonly --manual --preferred-challenges=dns --email admin@m1-3.ephec-ti.be --agree-tos -d *.m1-3.ephec-ti.be
```

Pendant le processus, nous avons dû ajouter un enregistrement TXT DNS pour la validation :

```
_acme-challenge IN TXT "TSp9x8JFmLa1MtSNWIdcPF_AEDhHDbUt7bj8O0IjVko"
```

### 4.5 Configuration de Nginx pour utiliser le certificat Let's Encrypt wildcard

```bash
cat > config/nginx.conf << 'EOF'
events {
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format log_per_virtualhost '[$host] $remote_addr [$time_local] $status '
                                   '"$request" $body_bytes_sent';
    access_log /dev/stdout log_per_virtualhost;
    error_log /dev/stderr;

    # Configurations SSL globales
    ssl_certificate /etc/letsencrypt/live/m1-3.ephec-ti.be/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/m1-3.ephec-ti.be/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers 'EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH';

    # Redirection HTTP du domaine apex vers www
    server {
        listen 80;
        server_name m1-3.ephec-ti.be;
        return 301 https://www.m1-3.ephec-ti.be$request_uri;
    }

    # Redirection HTTPS du domaine apex vers www
    server {
        listen 443 ssl;
        server_name m1-3.ephec-ti.be;
        return 301 https://www.m1-3.ephec-ti.be$request_uri;
    }
    
    # Redirection HTTP vers HTTPS pour www
    server {
        listen 80;
        server_name www.m1-3.ephec-ti.be;
        return 301 https://$host$request_uri;
    }

    # Configuration HTTPS pour www
    server {
        listen 443 ssl;
        server_name www.m1-3.ephec-ti.be;
        index index.html;
        root /var/www/html/www/;
        
        location ~ \.php$ {
            fastcgi_pass php:9000;
            include fastcgi_params;
            fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        }
    }

    # Redirection HTTP vers HTTPS pour blog
    server {
        listen 80;
        server_name blog.m1-3.ephec-ti.be;
        return 301 https://$host$request_uri;
    }

    # Configuration HTTPS pour blog
    server {
        listen 443 ssl;
        server_name blog.m1-3.ephec-ti.be;
        index index.html;
        root /var/www/html/blog/;
    }
}
EOF
```

### 4.6 Configuration du renouvellement automatique des certificats

```bash
# Création d'un script pour le renouvellement des certificats
cat > renew-certs.sh << 'EOF'
#!/bin/bash
cd ~/web-secure
docker compose exec -T web certbot renew --quiet
docker compose exec -T web nginx -s reload
EOF

# Rendre le script exécutable
chmod +x renew-certs.sh

# Configuration d'une tâche cron pour le renouvellement automatique
(crontab -l 2>/dev/null; echo "0 3 * * * ~/web-secure/renew-certs.sh") | crontab -
```

## 5. Test et vérification finale

```bash
# Redémarrage du service web pour appliquer la nouvelle configuration
docker compose exec web nginx -t
docker compose restart web

# Tests complets de l'infrastructure
curl -L https://www.m1-3.ephec-ti.be
curl -L https://blog.m1-3.ephec-ti.be
curl -L https://www.m1-3.ephec-ti.be/products.php
```
