# TP10 : Haute Scalabilité avec WoodyToys

## 1. Architecture des microservices

### 1.1. Division en microservices

L'application monolithique a été divisée en trois services principaux:

```bash
# Structure des microservices
services/
  ├── misc-service/        # Service pour les opérations diverses
  ├── product-service/     # Service de gestion des produits
  ├── order-service/       # Service de traitement des commandes
  ├── database/            # Service de base de données
  ├── reverse-proxy/       # API Gateway avec Nginx
  └── front/               # Frontend statique
```

Chaque service possède sa propre logique métier et peut être déployé et mis à l'échelle indépendamment:

- **misc-service**: Gère les calculs et opérations diverses
- **product-service**: Gère les produits (ajout, consultation)
- **order-service**: Gère les commandes et leur traitement

### 1.2. Configuration Docker

Chaque service est conteneurisé avec son propre Dockerfile:

```bash
# Exemple de Dockerfile pour un service
FROM python:3.12.3-bookworm

RUN pip install -U pip setuptools wheel

WORKDIR /project

COPY requirements.txt ./
RUN pip install -r requirements.txt --no-cache-dir

COPY . .

CMD [ "python", "main.py" ]
```

Une configuration Docker Compose et Docker Swarm a été mise en place pour orchesher l'ensemble:

```bash
# Construction et publication des images
./build_push.sh

# Déploiement sur Docker Swarm
docker stack deploy -c stack.yml woodytoys
```

## 2. Communication asynchrone avec RabbitMQ

### 2.1. Mise en place de RabbitMQ

RabbitMQ a été configuré comme Message Broker pour permettre une communication asynchrone entre les services:

```yaml
# Extrait du stack.yml
rabbitmq:
  image: rabbitmq:3-management
  volumes:
    - rabbitmq-data:/var/lib/rabbitmq
  ports:
    - "15672:15672"
  deploy:
    replicas: 1
    placement:
      constraints:
        - node.role == manager
    restart_policy:
      condition: on-failure
  healthcheck:
    test: ["CMD", "rabbitmqctl", "status"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 30s
```

### 2.2. Traitement asynchrone des commandes

Le processus de commande a été transformé pour utiliser un modèle asynchrone:

1. **Service order-service**: Reçoit la demande client et publie un message dans la file d'attente RabbitMQ

   ```python
   # Extrait du code de publication
   channel.queue_declare(queue='order_processing', durable=True)
   message = json.dumps({'order_id': order_id, 'product': product})
   channel.basic_publish(
       exchange='',
       routing_key='order_processing',
       body=message,
       properties=pika.BasicProperties(
           delivery_mode=2,  # Message persistant
       ))
   ```

2. **Service order-worker**: Consomme les messages et traite les commandes en arrière-plan

   ```python
   # Extrait du code de consommation
   channel.queue_declare(queue='order_processing', durable=True)
   channel.basic_qos(prefetch_count=1)
   channel.basic_consume(queue='order_processing', on_message_callback=callback)
   ```

3. **Fonction de traitement**:

   ```python
   def callback(ch, method, properties, body):
       # Parse le message
       message = json.loads(body)
       order_id = message['order_id']
       product = message['product']
       
       # Traitement de la commande
       status = woody.make_heavy_validation(product)
       woody.save_order(order_id, status, product)
       
       # Acquittement du message
       ch.basic_ack(delivery_tag=method.delivery_tag)
   ```

### 2.3. Avantages du traitement asynchrone

Cette approche offre plusieurs avantages:

- **Découplage**: Les services sont indépendants
- **Résilience**: La file d'attente conserve les messages même si le service de traitement est indisponible
- **Scalabilité**: Possibilité d'ajouter des workers sans modifier le service principal
- **Gestion des pics de charge**: La file d'attente absorbe les variations de charge

## 3. Configuration de l'API Gateway avec Nginx

### 3.1. Routing vers les microservices

Nginx a été configuré pour rediriger les requêtes vers les services appropriés en fonction des URL:

```nginx
# Extrait de la configuration Nginx
# Service misc
location ~ ^/api/misc {
    proxy_pass http://misc-service:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # Protection contre les abus
    limit_req zone=api_limit burst=20 nodelay;
    
    # Timeout augmenté pour les requêtes lourdes
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
}

# Service product
location ~ ^/api/products {
    proxy_pass http://product-service:5000;
    # Headers et timeout...
}

# Service order
location ~ ^/api/orders {
    proxy_pass http://order-service:5000;
    # Headers et timeout...
}
```

### 3.2. Protection contre les abus (Rate Limiting)

Une protection contre les abus a été mise en place pour limiter le nombre de requêtes par minute:

```nginx
# Configuration du rate limiting
# Dans http context
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

# Dans les locations
location ~ ^/api/misc {
    # ...
    limit_req zone=api_limit burst=20 nodelay;
}

location ~ ^/api/products {
    # ...
    limit_req zone=api_limit burst=5 nodelay;
}

location ~ ^/api/orders {
    # ...
    limit_req zone=api_limit burst=2 nodelay;
}

# Page d'erreur personnalisée pour le rate limiting
error_page 503 /rate_limit_exceeded.html;
location = /rate_limit_exceeded.html {
    return 503 '{"error": "Rate limit exceeded", "message": "Too many requests", "status": 503}';
    default_type application/json;
}
```

Cette configuration:

- Limite à 10 requêtes par seconde, par adresse IP
- Permet des bursts temporaires variables selon le type de service
- Retourne une erreur 503 avec un message JSON pour les dépassements de limite

## 4. Déploiement et Scaling

### 4.1. Configuration Docker Swarm

La configuration Docker Swarm permet de déployer l'application avec un scaling approprié pour chaque service:

```yaml
# Extrait du stack.yml - Configuration des réplicas
misc-service:
  # ...
  deploy:
    replicas: 3
    # ...

product-service:
  # ...
  deploy:
    replicas: 3
    # ...

order-service:
  # ...
  deploy:
    replicas: 2
    # ...

order-worker:
  # ...
  deploy:
    replicas: 5
    # ...
```

### 4.2. Stratégie de déploiement

La stratégie de déploiement mise en place garantit:

- Mise à jour progressive (rolling updates)
- Contraintes de placement (managers/workers)
- Politique de redémarrage en cas d'échec
- Healthchecks pour surveiller l'état des services

```yaml
# Exemple de configuration de déploiement pour un service
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
```

## 5. Tests et validation

### 5.1. Script de test des services

Un script a été créé pour tester rapidement tous les services:

```bash
#!/bin/bash

# Script pour tester rapidement tous les services

echo "=== Test des services WoodyToys ==="

echo -e "\n1. Test du service misc..."
curl -s http://localhost/api/misc/time
echo

echo -e "\n2. Test du service misc avec cache..."
echo "Premier appel (sans cache):"
time curl -s http://localhost/api/misc/heavy?name=test
echo -e "\nDeuxième appel (avec cache):"
time curl -s http://localhost/api/misc/heavy?name=test

echo -e "\n3. Test du service product..."
echo "Ajout d'un produit:"
curl -s -X GET "http://localhost/api/products?product=TestProduct$(date +%s)"
echo -e "\nRécupération du dernier produit:"
curl -s http://localhost/api/products/last

echo -e "\n4. Test du service order avec RabbitMQ..."
echo "Création d'une commande:"
ORDER_ID=$(curl -s http://localhost/api/orders/do?order=TestProduct | grep -o '[0-9a-f]\{8\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{4\}-[0-9a-f]\{12\}')
echo "Order ID: $ORDER_ID"

echo -e "\nAttente du traitement asynchrone..."
sleep 10

echo "Vérification du statut de la commande:"
curl -s http://localhost/api/orders/?order_id=$ORDER_ID

echo -e "\n5. Test du rate limiting..."
echo "Envoi de 30 requêtes rapides:"
for i in {1..30}; do
    response=$(curl -s -w "%{http_code}" -o /dev/null http://localhost/api/misc/time)
    echo "Requête $i: $response"
    sleep 0.1
done

echo -e "\n6. Test accès à l'interface de gestion RabbitMQ..."
echo "Vérifier si l'interface est accessible à http://54.36.181.87:15672 (guest/guest)"

echo -e "\n=== Tests terminés ==="
```

## 6. Scripts de déploiement et de test

```bash
# Construction et publication des images
./build_push.sh

# Déploiement sur Docker Swarm
./deploy-swarm.sh

# Test des services
./test-services.sh
```
