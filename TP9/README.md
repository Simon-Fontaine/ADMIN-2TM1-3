# TP9 : High Throughput sur WoodyToys

## 1. Préparation de l'environnement

### 1.1 Récupération du code source

```bash
# Créer un répertoire pour le projet
mkdir -p ~/high-throughput && cd ~/high-throughput

# Cloner le dépôt GitHub
git clone https://github.com/xavier-dubruille/woodytoys .
```

### 1.2 Test local initial

```bash
# Se placer dans le dossier des services
cd services

# Démarrer l'application avec Docker Compose
docker compose up -d

# Tester l'accès à l'application
curl http://localhost
curl http://localhost/api/misc/time

# Arrêter l'application locale
docker compose down
```

## 2. Adaptation pour Docker Swarm

### 2.1 Création du script de build

```bash
cd ~/high-throughput

# Créer un script de build personnalisé
cat > build_push.sh << 'EOF'
#!/bin/bash

set -e

username="simonschool"
version="1.0"

docker build -t $username/woody_api:$version services/api
docker build -t $username/woody_rp:$version services/reverse-proxy
docker build -t $username/woody_database:$version services/database
docker build -t $username/woody_front:$version services/front

docker tag $username/woody_api:$version $username/woody_api:latest
docker tag $username/woody_rp:$version $username/woody_rp:latest
docker tag $username/woody_database:$version $username/woody_database:latest
docker tag $username/woody_front:$version $username/woody_front:latest

docker login

docker push $username/woody_api:$version
docker push $username/woody_api:latest
docker push $username/woody_rp:$version
docker push $username/woody_rp:latest
docker push $username/woody_database:$version
docker push $username/woody_database:latest
docker push $username/woody_front:$version
docker push $username/woody_front:latest
EOF

chmod +x build_push.sh

# Exécuter le script
./build_push.sh
```

### 2.2 Création du fichier stack.yml

```bash
cat > stack.yml << 'EOF'
version: "3.9"

services:
  db:
    image: simonschool/woody_database:latest
    environment:
      - MYSQL_DATABASE=woody
      - MYSQL_ROOT_PASSWORD=pass
    volumes:
      - db-data:/var/lib/mysql
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      restart_policy:
        condition: on-failure

  api:
    image: simonschool/woody_api:latest
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/ping"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
      placement:
        constraints:
          - node.role == worker

  front:
    image: simonschool/woody_front:latest
    deploy:
      replicas: 2
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure

  reverse:
    image: simonschool/woody_rp:latest
    ports:
      - "80:8080"
    deploy:
      replicas: 2
      restart_policy:
        condition: on-failure
    depends_on:
      - front
      - api

networks:
  default:
    driver: overlay

volumes:
  db-data:
EOF
```

## 3. Déploiement sur Swarm et Mesures Initiales

### 3.1 Déploiement de la stack

```bash
# Sur le nœud manager
cd ~/high-throughput
docker stack deploy -c stack.yml woodytoys

# Vérifier le déploiement
docker stack services woodytoys
docker stack ps woodytoys

# Attendre que tous les services soient démarrés
sleep 60
```

### 3.2 Mesure des performances initiales

```bash
# Mesurer les temps de réponse
time wget -O - http://swarm.m1-3.ephec-ti.be > /dev/null
time curl http://swarm.m1-3.ephec-ti.be/api/misc/heavy?name=test
time curl http://swarm.m1-3.ephec-ti.be/api/products/last

# Mesurer le temps de chargement récursif
time wget -r -np -nH --cut-dirs=1 http://swarm.m1-3.ephec-ti.be
```

## 4. Scaling Horizontal

### 4.1 Augmentation du nombre de replicas

```bash
# Augmenter le nombre de replicas pour l'API
docker service scale woodytoys_api=5

# Vérifier le scaling
docker service ls
```

### 4.2 Mesure des performances après scaling

```bash
# Mesurer les temps de réponse après scaling
time wget -O - http://swarm.m1-3.ephec-ti.be > /dev/null
time curl http://swarm.m1-3.ephec-ti.be/api/misc/heavy?name=test
time curl http://swarm.m1-3.ephec-ti.be/api/products/last

# Test avec plusieurs requêtes en parallèle
for i in {1..5}; do
  curl -s http://swarm.m1-3.ephec-ti.be/api/misc/heavy?name=test$i &
done
wait
```

## 5. Mise en Cache avec Redis

### 5.1 Modification de l'API pour utiliser Redis

```bash
# Créer un dossier pour la version avec Redis
mkdir -p ~/high-throughput/api-redis && cd ~/high-throughput/api-redis

# Copier les fichiers de l'API originale
cp -r ~/high-throughput/services/api/* .

# Créer le wrapper Redis
cat > redis_wrapper.py << 'EOF'
import redis
import json
from functools import wraps

redis_client = redis.Redis(host='redis', port=6379, db=0)

def cache_result(ttl=60):
    """
    Décorateur pour mettre en cache les résultats d'une fonction
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Générer une clé unique basée sur le nom de la fonction et ses arguments
            key = f"{f.__name__}:{str(args)}:{str(kwargs)}"
            
            # Vérifier si le résultat est en cache
            cached_value = redis_client.get(key)
            if cached_value:
                print(f"Cache hit for {key}")
                return cached_value.decode('utf-8')
            
            # Si non, exécuter la fonction et mettre en cache le résultat
            print(f"Cache miss for {key}")
            result = f(*args, **kwargs)
            redis_client.setex(key, ttl, result)
            return result
        return decorated_function
    return decorator
EOF

# Modifier le fichier main.py pour utiliser Redis
cat > main.py << 'EOF'
import uuid
from datetime import datetime

from flask import Flask, request
from flask_cors import CORS

import woody
from redis_wrapper import cache_result
import redis

app = Flask('my_api')
cors = CORS(app)

redis_client = redis.Redis(host='redis', port=6379, db=0)

@app.get('/api/ping')
def ping():
    return 'ping'

@app.route('/api/misc/time', methods=['GET'])
def get_time():
    return f'misc: {datetime.now()}'

@app.route('/api/misc/heavy', methods=['GET'])
@cache_result(ttl=30)
def get_heavy():
    name = request.args.get('name')
    r = woody.make_some_heavy_computation(name)
    return f'{datetime.now()}: {r}'

@app.route('/api/products', methods=['GET'])
def add_product():
    product = request.args.get('product')
    woody.add_product(str(product))
    redis_client.delete('get_last_product:():{}')
    return str(product) or "none"

@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    return "not yet implemented"

@app.route('/api/products/last', methods=['GET'])
@cache_result(ttl=15)
def get_last_product():
    last_product = woody.get_last_product()
    return f'db: {datetime.now()} - {last_product}'

@app.route('/api/orders/do', methods=['GET'])
def create_order():
    product = request.args.get('order')
    order_id = str(uuid.uuid4())
    process_order(order_id, product)
    return f"Your process {order_id} has been created with this product : {product}"

@app.route('/api/orders/', methods=['GET'])
def get_order():
    order_id = request.args.get('order_id')
    status = woody.get_order(order_id)
    return f'order "{order_id}": {status}'

def process_order(order_id, order):
    status = woody.make_heavy_validation(order)
    woody.save_order(order_id, status, order)

if __name__ == "__main__":
    woody.launch_server(app, host='0.0.0.0', port=5000)
EOF
```

### 5.2 Build et déploiement de l'image avec Redis

```bash
# Construire et pousser l'image
docker build -t simonschool/woody_api:redis .
docker push simonschool/woody_api:redis

# Créer le fichier stack_redis.yml
cd ~/high-throughput
cat > stack_redis.yml << 'EOF'
version: "3.9"

services:
  db:
    image: simonschool/woody_database:latest
    environment:
      - MYSQL_DATABASE=woody
      - MYSQL_ROOT_PASSWORD=pass
    volumes:
      - db-data:/var/lib/mysql
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      restart_policy:
        condition: on-failure

  redis:
    image: redis:alpine
    deploy:
      replicas: 1
      restart_policy:
        condition: on-failure

  api:
    image: simonschool/woody_api:redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/ping"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    deploy:
      replicas: 5
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
      placement:
        constraints:
          - node.role == worker

  front:
    image: simonschool/woody_front:latest
    deploy:
      replicas: 2
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure

  reverse:
    image: simonschool/woody_rp:latest
    ports:
      - "80:8080"
    deploy:
      replicas: 2
      restart_policy:
        condition: on-failure
    depends_on:
      - front
      - api

networks:
  default:
    driver: overlay

volumes:
  db-data:
EOF

# Télécharger l'image Redis si nécessaire
docker pull redis:alpine

# Déployer la stack avec Redis
docker stack deploy -c stack_redis.yml woodytoys

# Attendre que tous les services soient démarrés
sleep 60
```

### 5.3 Mesure des performances avec Redis

```bash
# Premier appel (cache miss)
time curl http://swarm.m1-3.ephec-ti.be/api/misc/heavy?name=test

# Deuxième appel (cache hit)
time curl http://swarm.m1-3.ephec-ti.be/api/misc/heavy?name=test

# Premier appel à l'API produit (cache miss)
time curl http://swarm.m1-3.ephec-ti.be/api/products/last

# Deuxième appel à l'API produit (cache hit)
time curl http://swarm.m1-3.ephec-ti.be/api/products/last
```

## 6. Mise en place d'un CDN

### 6.1 Création d'un compte Gcore et configuration du CDN

1. Créez un compte sur [https://gcore.com/](https://gcore.com/)
2. Dans le dashboard, allez dans "CDN" > "Resources"
3. Créez une nouvelle ressource :
   - Origin URL: <http://swarm.m1-3.ephec-ti.be>
   - Nom de la ressource: woodytoys-cdn
   - CNAME personnalisé: cdn.m1-3.ephec-ti.be

### 6.2 Configuration DNS pour le CDN

```bash
# Sur le serveur DNS
cd ~/dns-public

# Modifier le fichier de zone pour ajouter le CNAME
echo "cdn   IN   CNAME   XXXXX.cdn.gcore.com." >> zone/m1-3.zone

# Incrémenter le serial dans le SOA

# Redémarrer le service DNS
docker restart dns

# Vérifier la résolution DNS
dig @localhost cdn.m1-3.ephec-ti.be
```

### 6.3 Modification du frontend pour utiliser le CDN

```bash
mkdir -p ~/high-throughput/front-cdn && cd ~/high-throughput/front-cdn

# Copier les fichiers du frontend
cp -r ~/high-throughput/services/front/* .

# Modifier l'index.html pour utiliser le CDN
# Changer l'URL de l'image dans index.html pour utiliser le CDN
# Remplacer /5mo.jpg par https://cdn.m1-3.ephec-ti.be/5mo.jpg

# Construire et pousser l'image
docker build -t simonschool/woody_front:cdn .
docker push simonschool/woody_front:cdn
```

### 6.4 Déploiement de la version avec CDN

```bash
cd ~/high-throughput
cat > stack_redis_cdn.yml << 'EOF'
version: "3.9"

services:
  db:
    image: simonschool/woody_database:latest
    environment:
      - MYSQL_DATABASE=woody
      - MYSQL_ROOT_PASSWORD=pass
    volumes:
      - db-data:/var/lib/mysql
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      restart_policy:
        condition: on-failure

  redis:
    image: redis:alpine
    deploy:
      replicas: 1
      restart_policy:
        condition: on-failure

  api:
    image: simonschool/woody_api:redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/ping"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    deploy:
      replicas: 5
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
      placement:
        constraints:
          - node.role == worker

  front:
    image: simonschool/woody_front:cdn
    deploy:
      replicas: 2
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure

  reverse:
    image: simonschool/woody_rp:latest
    ports:
      - "80:8080"
    deploy:
      replicas: 2
      restart_policy:
        condition: on-failure
    depends_on:
      - front
      - api

networks:
  default:
    driver: overlay

volumes:
  db-data:
EOF

# Déployer la stack avec CDN
docker stack deploy -c stack_redis_cdn.yml woodytoys

# Attendre que tous les services soient démarrés
sleep 60
```

### 6.5 Mesure des performances avec CDN

```bash
# Mesurer le temps de chargement de la page
time wget -O - http://swarm.m1-3.ephec-ti.be > /dev/null

# Mesurer le temps de chargement récursif
time wget -r -np -nH --cut-dirs=1 http://swarm.m1-3.ephec-ti.be
```

## 7. Résultats

### 7.1 Tableau comparatif des performances

| Configuration | Temps de chargement récursif | API lente | API DB |
|---------------|----------------------|-----------|--------|
| Initial       | 16.065 s               | 5.029 s    | 15.198 s |
| + Replicas    | 16.093 s               | 5.040 s    | 15.169 s |
| + Redis       | 16.102 s               | 5.058 s (miss) 0.021 S (hit) | 15.214 s (miss) 0.032 s (hit) |
| + CDN         | 0.030 s               | //    | // |

### 7.2 Observations

1. **Scaling horizontal** :
   - Impact sur l'API : Peu d'amélioration car le serveur Flask n'est pas multi-threadé
   - Impact sur les requêtes DB : Pas d'amélioration car la DB reste limitée à une connexion

2. **Cache Redis** :
   - Impact considérable sur les temps de réponse pour les appels répétés
   - Amélioration de 99.6% sur l'API lente et 99.8% sur l'API DB lors d'un cache hit

3. **CDN** :
   - Amélioration majeure du chargement des ressources statiques
   - Réduction de 99.8% du temps de chargement total

## 8. Solutions possibles pour la base de données

Pour améliorer les performances de la base de données, voici quelques solutions possibles :

### 8.1 Read-Write Splitting

Cette solution consiste à séparer les opérations de lecture et d'écriture :

- Un serveur principal (master) gère toutes les écritures
- Plusieurs serveurs secondaires (slaves) gèrent les lectures

Avantages :

- Meilleure scalabilité pour les lectures
- Répartition de la charge
- Haute disponibilité

### 8.2 CQRS (Command Query Responsibility Segregation)

Le pattern CQRS sépare :

- Le modèle de commande (écritures) : optimisé pour les transactions
- Le modèle de requête (lectures) : optimisé pour les lectures, potentiellement dénormalisé

Avantages :

- Meilleure performance des requêtes de lecture
- Modèles optimisés pour chaque cas d'usage
- Évolutivité indépendante

### 8.3 Sharding

Le sharding consiste à diviser les données sur plusieurs serveurs selon une clé de partitionnement.

Avantages :

- Scalabilité horizontale presque illimitée
- Meilleure distribution de la charge
- Améliore les performances pour des requêtes ciblées
