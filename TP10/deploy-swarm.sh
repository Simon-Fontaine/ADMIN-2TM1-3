#!/bin/bash

# Script pour automatiser le déploiement sur Docker Swarm

set -e  # Arrêter en cas d'erreur

echo "=== Déploiement sur Docker Swarm ==="

# 1. Construction et publication des images
echo "Construction et publication des images Docker..."
./build_push.sh

# 2. Déploiement de la stack
echo "Déploiement de la stack sur Docker Swarm..."
docker stack deploy -c stack.yml woodytoys

# 3. Vérification du déploiement
echo "Vérification des services déployés..."
docker stack services woodytoys

# 4. Attente que tous les services soient prêts
echo "Attente du déploiement complet des services..."
sleep 60

# 5. Vérification de l'état des services
echo "État des services:"
docker stack ps woodytoys

echo "=== Déploiement terminé ==="
echo "Pour accéder à l'application: http://swarm.m1-3.ephec-ti.be"
echo "Interface RabbitMQ: http://54.36.181.87:15672 (guest/guest)"