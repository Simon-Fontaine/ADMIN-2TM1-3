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