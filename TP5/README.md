# Configuration du service web public pour WoodyToys

## 1. Initialisation de l'environnement

```bash
# Création d'une structure organisée pour les fichiers de configuration
mkdir -p ~/web/{html/{www,blog},php,config}
cd ~/web
```

## 2. Configuration de base du serveur web

### 2.1 Site web statique

```bash
# Création du fichier index.html pour le site principal
cat > ~/web/html/www/index.html << 'EOF'
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WoodyToys</title>
</head>
<body>
  <h1>Bienvenue sur le site de WoodyToys</h1>
  <p>Groupe M1-3</p>
</body>
</html>
EOF
```

```bash
# Création de la configuration nginx de base
cat > ~/web/config/nginx.conf << 'EOF'
events {
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    server {
        listen          80;
        server_name     www.m1-3.ephec-ti.be;
        index           index.html;
        root            /var/www/html/www/;
    }
}
EOF
```

```bash
# Création du Dockerfile pour nginx
cat > ~/web/Dockerfile << 'EOF'
FROM nginx:latest
COPY config/nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
EOF
```

```bash
# Vérification que www est correctement défini dans la zone DNS
cat ~/dns-public/zone/m1-3.zone | grep www
```

```bash
# Construction et lancement du container
docker build -t web .
docker run -p 80:80 --name web --rm -d --mount type=bind,source=$(pwd)/html,target=/var/www/html/ web

# Vérification que le serveur répond
curl -H "Host: www.m1-3.ephec-ti.be" http://localhost
# Vous devriez voir le contenu HTML de votre page d'accueil
```

### 2.2 Virtual Hosting

```bash
# Mise à jour de la zone DNS pour ajouter l'entrée blog
cat > ~/dns-public/zone/m1-3.zone << 'EOF'
; Zone file for m1-3.ephec-ti.be
$TTL 86400      ; 1 day
@       IN      SOA     ns.m1-3.ephec-ti.be. admin.m1-3.ephec-ti.be. (
                        2025030102      ; serial (YYYYMMDDNN)
                        21600           ; refresh (6 hours)
                        3600            ; retry (1 hour)
                        604800          ; expire (1 week)
                        86400           ; minimum TTL (1 day)
                        )
; Serveurs de noms
@       IN      NS      ns.m1-3.ephec-ti.be.

; Enregistrements A
@       IN      A       54.36.181.87    ; Adresse IP du domaine racine
ns      IN      A       54.36.181.87    ; Serveur DNS
www     IN      A       54.36.181.87    ; Site web
mail    IN      A       54.36.181.87    ; Serveur mail
blog    IN      CNAME   www             ; Blog (utilisation d'un CNAME)

; Enregistrement MX
@       IN      MX      10 mail.m1-3.ephec-ti.be.
EOF
```

```bash
# Redémarrer le service DNS avec la nouvelle config
docker restart dns

# Vérifier que l'entrée blog est correctement résolue
dig @localhost blog.m1-3.ephec-ti.be
```

```bash
# Création du fichier index.html pour le blog
cat > ~/web/html/blog/index.html << 'EOF'
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Blog WoodyToys</title>
</head>
<body>
  <h1>Blog de WoodyToys</h1>
  <p>Groupe M1-3</p>
</body>
</html>
EOF
```

```bash
# Mise à jour de la configuration nginx pour le virtual hosting
cat > ~/web/config/nginx.conf << 'EOF'
events {
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    server {
        listen          80;
        server_name     www.m1-3.ephec-ti.be;
        index           index.html;
        root            /var/www/html/www/;
    }

    server {
        listen          80;
        server_name     blog.m1-3.ephec-ti.be;
        index           index.html;
        root            /var/www/html/blog/;
    }
}
EOF
```

```bash
# Reconstruction et redémarrage du container
docker stop web
docker build -t web .
docker run -p 80:80 --name web --rm -d --mount type=bind,source=$(pwd)/html,target=/var/www/html/ web

# Vérification des deux sites
curl -H "Host: www.m1-3.ephec-ti.be" http://localhost
curl -H "Host: blog.m1-3.ephec-ti.be" http://localhost
```

### 2.3 Logging

```bash
# Mise à jour de la configuration nginx pour les logs
cat > ~/web/config/nginx.conf << 'EOF'
events {
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    # Format de log personnalisé incluant le virtual host
    log_format log_per_virtualhost '[$host] $remote_addr [$time_local] $status '
                                   '"$request" $body_bytes_sent';
    
    # Redirection des logs vers stdout/stderr pour être capturés par Docker
    access_log /dev/stdout log_per_virtualhost;
    error_log /dev/stderr;

    server {
        listen          80;
        server_name     www.m1-3.ephec-ti.be;
        index           index.html;
        root            /var/www/html/www/;
    }

    server {
        listen          80;
        server_name     blog.m1-3.ephec-ti.be;
        index           index.html;
        root            /var/www/html/blog/;
    }
}
EOF
```

```bash
# Reconstruction et redémarrage du container
docker stop web
docker build -t web .
docker run -p 80:80 --name web --rm -d --mount type=bind,source=$(pwd)/html,target=/var/www/html/ web

# Génération de quelques requêtes pour les logs
curl -H "Host: www.m1-3.ephec-ti.be" http://localhost
curl -H "Host: blog.m1-3.ephec-ti.be" http://localhost

# Vérification des logs
docker logs -f web
```

## 3. Site web dynamique

### 3.1 Installation de la base de données

```bash
# Installation du client MariaDB sur le VPS
sudo apt update
sudo apt install mariadb-client -y

# Lancement du container MariaDB
docker run --name db -e MYSQL_ROOT_PASSWORD=mypass --rm -d mariadb

# Récupération de l'adresse IP du container
DB_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' db)
echo "L'adresse IP du container MariaDB est : $DB_IP"
```

```bash
# Création du fichier SQL pour initialiser la DB
cat > ~/web/woodytoys.sql << 'EOF'
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
EOF
```

```bash
# Création de la base et import des données
mysql -h $DB_IP -u root -pmypass -e "CREATE DATABASE woodytoys;"
mysql -h $DB_IP -u root -pmypass < ~/web/woodytoys.sql

# Vérification des données
mysql -h $DB_IP -u root -pmypass -e "USE woodytoys; SELECT * FROM products;"
```

### 3.2 Premier script PHP

```bash
# Création du Dockerfile pour PHP
cat > ~/web/php/Dockerfile << 'EOF'
FROM php:8.3-fpm
RUN docker-php-ext-install mysqli
EOF
```

```bash
# Construction de l'image PHP
cd ~/web/php
docker build -t php .
cd ~/web

# Création d'un script PHP de test
cat > ~/web/html/www/products.php << 'EOF'
<?php phpinfo(); ?>
EOF
```

```bash
# Lancement du container PHP
docker run --name php --rm -d --mount type=bind,source=$(pwd)/html/www,target=/var/www/html/www php

# Récupération de l'IP du container PHP
PHP_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' php)
echo "L'adresse IP du container PHP est : $PHP_IP"
```

```bash
# Mise à jour de la configuration nginx pour intégrer PHP
cat > ~/web/config/nginx.conf << EOF
events {
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format log_per_virtualhost '[\$host] \$remote_addr [\$time_local] \$status '
                                   '"\$request" \$body_bytes_sent';
    access_log /dev/stdout log_per_virtualhost;
    error_log /dev/stderr;

    server {
        listen 80;
        server_name www.m1-3.ephec-ti.be;
        index index.html;
        root /var/www/html/www/;
        
        location ~ \\.php$ {
            fastcgi_pass $PHP_IP:9000;
            include fastcgi_params;
            fastcgi_param SCRIPT_FILENAME \$document_root\$fastcgi_script_name;
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

```bash
# Reconstruction et redémarrage du container nginx
docker stop web
docker build -t web .
docker run -p 80:80 --name web --rm -d --mount type=bind,source=$(pwd)/html,target=/var/www/html/ web

# Vérification que le script PHP fonctionne
curl -H "Host: www.m1-3.ephec-ti.be" http://localhost/products.php | head -n 20
```

### 3.3 Connexion entre l'application web et la base de données

```bash
# Mise à jour du script PHP pour se connecter à la DB
cat > ~/web/html/www/products.php << EOF
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
\$dbname = 'woodytoys';
\$dbuser = 'root';
\$dbpass = 'mypass';
\$dbhost = '$DB_IP';
\$connect = mysqli_connect(\$dbhost, \$dbuser, \$dbpass) or die("Unable to connect to '\$dbhost'");
mysqli_select_db(\$connect,\$dbname) or die("Could not open the database '\$dbname'");
\$result = mysqli_query(\$connect,"SELECT id, product_name, product_price FROM products");
?>

<table>
<tr>
    <th>Numéro de produit</th>
    <th>Descriptif</th> 
    <th>Prix</th>
</tr>

<?php
while (\$row = mysqli_fetch_array(\$result)) {
    printf("<tr><th>%s</th> <th>%s</th> <th>%s</th></tr>", \$row[0], \$row[1],\$row[2]);
}
?>

</table>
</body>
</html>
EOF
```

```bash
# Vérification du script de catalogue avec la DB
curl -H "Host: www.m1-3.ephec-ti.be" http://localhost/products.php
```

### 3.4 Docker Compose

```bash
# Arrêt des containers individuels
docker stop web php db

# Création du fichier docker-compose.yaml
cat > ~/web/docker-compose.yaml << 'EOF'
version: '3'

services:
  web:
    container_name: web
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "80:80"
    volumes:
      - ./html:/var/www/html
      - ./config:/etc/nginx/conf.d
    depends_on:
      - php
      - db
    restart: unless-stopped
    networks:
      - woodytoys-network

  php:
    container_name: php
    build:
      context: ./php
      dockerfile: Dockerfile
    volumes:
      - ./html/www:/var/www/html/www
    restart: unless-stopped
    networks:
      - woodytoys-network

  db:
    container_name: db
    image: mariadb
    environment:
      MYSQL_ROOT_PASSWORD: mypass
      MYSQL_DATABASE: woodytoys
    volumes:
      - db-data:/var/lib/mysql
      - ./woodytoys.sql:/docker-entrypoint-initdb.d/woodytoys.sql
    restart: unless-stopped
    networks:
      - woodytoys-network

networks:
  woodytoys-network:
    driver: bridge

volumes:
  db-data:
EOF
```

```bash
# Mise à jour de la configuration nginx pour utiliser les noms de services
cat > ~/web/config/nginx.conf << 'EOF'
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
        index index.html;
        root /var/www/html/www/;
        
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

```bash
# Mise à jour du script PHP pour utiliser le nom de service
cat > ~/web/html/www/products.php << 'EOF'
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
$dbname = 'woodytoys';
$dbuser = 'root';
$dbpass = 'mypass';
$dbhost = 'db';
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

```bash
# Démarrage des services avec Docker Compose
docker compose up -d

# Vérification de l'état des services
docker compose ps

# Vérification du fonctionnement des sites
curl -H "Host: www.m1-3.ephec-ti.be" http://localhost
curl -H "Host: blog.m1-3.ephec-ti.be" http://localhost
curl -H "Host: www.m1-3.ephec-ti.be" http://localhost/products.php
```

## 4. Vérification finale

```bash
# Vérification complète des services
docker compose ps
docker compose logs -f

# Test d'accès externe (remplacer par votre domaine)
curl http://www.m1-3.ephec-ti.be
curl http://blog.m1-3.ephec-ti.be
curl http://www.m1-3.ephec-ti.be/products.php
```
