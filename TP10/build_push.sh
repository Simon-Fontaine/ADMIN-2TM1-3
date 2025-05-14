#!/bin/bash

set -e

username="simonschool"
version="1.0"

# Construction des images pour chaque service
docker build -t $username/woody_misc:$version services/misc-service
docker build -t $username/woody_product:$version services/product-service
docker build -t $username/woody_order:$version services/order-service
docker build -t $username/woody_order_worker:$version -f services/order-service/Dockerfile.worker services/order-service
docker build -t $username/woody_rp:$version services/reverse-proxy
docker build -t $username/woody_database:$version services/database
docker build -t $username/woody_front:$version services/front

# Créer les tags "latest"
docker tag $username/woody_misc:$version $username/woody_misc:latest
docker tag $username/woody_product:$version $username/woody_product:latest
docker tag $username/woody_order:$version $username/woody_order:latest
docker tag $username/woody_order_worker:$version $username/woody_order_worker:latest
docker tag $username/woody_rp:$version $username/woody_rp:latest
docker tag $username/woody_database:$version $username/woody_database:latest
docker tag $username/woody_front:$version $username/woody_front:latest

# Connexion à Docker Hub
docker login

# Publication des images
docker push $username/woody_misc:$version
docker push $username/woody_misc:latest
docker push $username/woody_product:$version
docker push $username/woody_product:latest
docker push $username/woody_order:$version
docker push $username/woody_order:latest
docker push $username/woody_order_worker:$version
docker push $username/woody_order_worker:latest
docker push $username/woody_rp:$version
docker push $username/woody_rp:latest
docker push $username/woody_database:$version
docker push $username/woody_database:latest
docker push $username/woody_front:$version
docker push $username/woody_front:latest