# TP8 : Haute disponibilité avec Docker Swarm

## 1. Introduction et préparation de l'environnement

### 1.1 Configuration des noms d'hôtes

Pour faciliter la gestion des machines du cluster, configurez des noms d'hôtes explicites:

```bash
# Sur le premier VPS (54.36.181.87)
sudo hostnamectl set-hostname swarm-manager-1
sudo nano /etc/hosts
# Ajouter/modifier la ligne:
127.0.1.1 swarm-manager-1 vps-1234567.vps.ovh.net vps-1234567

# Sur le deuxième VPS (54.36.182.168)
sudo hostnamectl set-hostname swarm-manager-2
sudo nano /etc/hosts
# Ajouter/modifier la ligne:
127.0.1.1 swarm-manager-2 vps-1234567.vps.ovh.net vps-1234567

# Sur le troisième VPS (54.36.181.115)
sudo hostnamectl set-hostname swarm-worker-1
sudo nano /etc/hosts
# Ajouter/modifier la ligne:
127.0.1.1 swarm-worker-1 vps-1234567.vps.ovh.net vps-1234567
```

### 1.2 Ouverture des ports nécessaires

Docker Swarm nécessite l'ouverture de certains ports pour fonctionner correctement:

```bash
# Ouvrir les ports pour Docker Swarm
sudo ufw allow 2377/tcp  # Port de gestion du swarm
sudo ufw allow 7946/tcp  # Communication entre les nœuds (control plane)
sudo ufw allow 7946/udp  # Communication entre les nœuds (control plane) 
sudo ufw allow 4789/udp  # Trafic réseau overlay (VXLAN)
sudo ufw allow 8080/tcp  # Pour notre service web
```

## 2. Publication d'une image Docker sur DockerHub

Pour ce TP, nous allons créer une image personnalisée et la publier sur DockerHub afin qu'elle soit accessible par tous les nœuds du cluster.

### 2.1 Création d'une image Docker personnalisée

Nous allons créer une page web simple qui affichera des informations sur le conteneur qui la sert:

```bash
# Sur votre machine de développement ou un des VPS
mkdir -p ~/swarm-demo && cd ~/swarm-demo

# Création d'une page d'accueil personnalisée
cat > index.html << 'EOF'
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WoodyToys - Swarm Demo</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      text-align: center;
      margin: 50px;
      background-color: #f5f5f5;
    }
    h1 {
      color: #2c3e50;
    }
    .container {
      background-color: white;
      border-radius: 8px;
      padding: 20px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      max-width: 800px;
      margin: 0 auto;
    }
    .server-info {
      background-color: #f8f9fa;
      border-radius: 4px;
      padding: 10px;
      margin-top: 20px;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>WoodyToys - Docker Swarm Demo</h1>
    <p>Cette page est servie depuis un conteneur dans un cluster Docker Swarm.</p>
    <div class="server-info">
      <p>Nom du conteneur: <strong><?php echo gethostname(); ?></strong></p>
      <p>Adresse IP: <strong><?php echo $_SERVER['SERVER_ADDR']; ?></strong></p>
      <p>Date et heure: <strong><?php echo date('Y-m-d H:i:s'); ?></strong></p>
    </div>
  </div>
</body>
</html>
EOF

# Création du Dockerfile
cat > Dockerfile << 'EOF'
FROM php:8.3-apache

COPY index.html /var/www/html/index.php
EXPOSE 80

# Ajout d'un healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost/ || exit 1
EOF
```

### 2.2 Construction et publication de l'image

```bash
# Construction de l'image
docker build -t simonschool/woodytoys-swarm:1.0 .

# Connexion à Docker Hub
docker login
# Entrez vos identifiants Docker Hub

# Publication de l'image
docker push simonschool/woodytoys-swarm:1.0
```

### 2.3 Vérification de l'image publiée

Assurez-vous que votre image fonctionne correctement avant de la déployer sur le Swarm:

```bash
# Test rapide de l'image
docker run -d -p 8080:80 --name test-swarm simonschool/woodytoys-swarm:1.0

# Vérification de l'accès
curl http://localhost:8080

# Nettoyage
docker stop test-swarm && docker rm test-swarm
```

## 3. Mise en place de Docker Swarm

### 3.1 Initialisation du Swarm

Initialisez le cluster Swarm sur le premier nœud manager:

```bash
# Sur le premier VPS (swarm-manager-1)
docker swarm init --advertise-addr 54.36.181.87
```

Cette commande vous fournira deux tokens:

- Un token pour ajouter d'autres managers
- Un token pour ajouter des workers

Notez ces tokens, ils seront nécessaires pour les étapes suivantes.

### 3.2 Ajout des autres nœuds

Ajoutez les autres VPS au cluster:

```bash
# Pour obtenir le token manager si vous l'avez perdu
docker swarm join-token manager

# Pour obtenir le token worker si vous l'avez perdu
docker swarm join-token worker

# Sur le deuxième VPS (swarm-manager-2)
docker swarm join --token SWMTKN-1-xxxxxxxxxxxx-manager 54.36.181.87:2377

# Sur le troisième VPS (swarm-worker-1)
docker swarm join --token SWMTKN-1-xxxxxxxxxxxx-worker 54.36.181.87:2377
```

### 3.3 Vérification de la configuration

Vérifiez que tous les nœuds ont bien rejoint le cluster:

```bash
# Sur n'importe quel nœud manager
docker node ls
```

Si le deuxième nœud a été ajouté en tant que worker mais que vous souhaitez le promouvoir en manager:

```bash
# Identifier l'ID du nœud
docker node ls

# Promouvoir le nœud en manager
docker node promote NODE_ID
```

## 4. Déploiement d'un service sur le Swarm

### 4.1 Création du service

Créez un service répliqué qui utilisera l'image que vous avez publiée:

```bash
# Sur un nœud manager
docker service create \
  --name woodytoys-web \
  --publish 8080:80 \
  --replicas 3 \
  --update-delay 10s \
  --update-parallelism 1 \
  simonschool/woodytoys-swarm:1.0

# Vérification du service
docker service ls
docker service ps woodytoys-web
```

### 4.2 Test du service et de sa haute disponibilité

Vérifiez que le service est accessible et testez sa résilience:

```bash
# Vérification de l'accès depuis n'importe quel nœud
curl http://localhost:8080

# Test d'accès via le DNS (si configuré)
curl http://swarm.m1-3.ephec-ti.be:8080

# Test de résilience - arrêtez Docker sur un des nœuds
# Sur un nœud qui exécute un conteneur du service (de préférence un worker)
sudo systemctl stop docker

# Vérifiez que le service continue de fonctionner
curl http://swarm.m1-3.ephec-ti.be:8080

# Sur un nœud manager, vérifiez l'état du service
docker service ps woodytoys-web
```

Vous devriez constater que Docker Swarm a automatiquement redéployé les conteneurs manquants sur les nœuds disponibles.

### 4.3 Mise à jour du service

Modifiez l'application et mettez à jour le service sans interruption:

```bash
# Modification de la page web (par exemple, changez le titre)
cd ~/swarm-demo
nano index.html
# Modifiez le contenu comme souhaité

# Construction de la nouvelle version
docker build -t simonschool/woodytoys-swarm:1.1 .
docker push simonschool/woodytoys-swarm:1.1

# Mise à jour du service
docker service update --image simonschool/woodytoys-swarm:1.1 woodytoys-web

# Surveillance du déploiement
docker service ps woodytoys-web
```

### 4.4 Scaling du service

Ajustez le nombre de réplicas selon vos besoins:

```bash
# Augmentation du nombre de réplicas
docker service scale woodytoys-web=5

# Vérification du scaling
docker service ps woodytoys-web
```

## 5. Configuration DNS pour la haute disponibilité

Pour une meilleure haute disponibilité, configurez un enregistrement DNS Round-Robin pointant vers tous les nœuds du Swarm:

```zone
; Dans votre fichier de zone DNS
; Round-robin pour le service swarm
swarm   IN      A       54.36.181.87 
swarm   IN      A       54.36.182.168
swarm   IN      A       54.36.181.115
```

Vérifiez que la résolution DNS fonctionne correctement:

```bash
# Vérification de la résolution DNS
dig @localhost swarm.m1-3.ephec-ti.be

# Test d'accès via le nom DNS
curl http://swarm.m1-3.ephec-ti.be:8080
```

Cette configuration permet de répartir les requêtes entre les différents nœuds du Swarm, même si l'un d'eux devient indisponible.

## 6. Pour aller plus loin

### 6.1 Sécurisation du Swarm

Pour une production réelle, il est recommandé de sécuriser le trafic entre les nœuds du Swarm:

```bash
# Sur tous les nœuds
docker swarm leave --force

# Sur le premier nœud, initialisez un nouveau Swarm avec chiffrement
docker swarm init --advertise-addr 54.36.181.87 \
  --data-path-addr 54.36.181.87 \
  --default-addr-pool 10.10.0.0/16

# Rotation régulière des tokens (bonne pratique de sécurité)
docker swarm join-token --rotate worker
docker swarm join-token --rotate manager
```

### 6.2 Utilisation des configs Docker

Docker Swarm permet de gérer les configurations sans avoir à reconstruire les images:

```bash
# Création d'une config pour la page web
docker config create webpage index.html

# Utilisation de la config dans le service
docker service update \
  --config-add source=webpage,target=/var/www/html/index.php \
  woodytoys-web
```

### 6.3 Déploiement d'un stack complet avec Docker Compose

Vous pouvez utiliser Docker Compose pour déployer des applications multi-conteneurs:

```bash
# Création d'un fichier docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  web:
    image: simonschool/woodytoys-swarm:1.1
    ports:
      - "8080:80"
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure

networks:
  default:
    driver: overlay
EOF

# Déploiement du stack
docker stack deploy -c docker-compose.yml woodytoys
```

## 7. Nettoyage (après le TP)

Une fois le TP terminé, vous pouvez nettoyer l'environnement:

```bash
# Suppression du service
docker service rm woodytoys-web

# Suppression du stack (si déployé)
docker stack rm woodytoys

# Quitter le Swarm
# Sur les nœuds workers:
docker swarm leave

# Sur les nœuds managers:
docker swarm leave --force
```
