import uuid
import os
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import woody
import pika
import json
import time

app = Flask('order_service')
cors = CORS(app)

# Configuration de RabbitMQ
def get_rabbitmq_connection():
    retries = 5
    while retries > 0:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(
                host="rabbitmq",
                heartbeat=600,
                blocked_connection_timeout=300,
                socket_timeout=5
            ))
            return connection
        except Exception as e:
            retries -= 1
            if retries == 0:
                print(f"Impossible de se connecter à RabbitMQ après plusieurs tentatives: {e}")
                return None
            print(f"Tentative de reconnexion à RabbitMQ dans 1 seconde... ({retries} restantes)")
            time.sleep(1)

@app.get('/api/ping')
def ping():
    return 'ping'

@app.route('/api/orders/do', methods=['GET'])
def create_order():
    try:
        product = request.args.get('order')
        if not product:
            return "Order product is required", 400
            
        order_id = str(uuid.uuid4())
        
        # Envoi du message à RabbitMQ
        connection = get_rabbitmq_connection()
        if connection:
            try:
                channel = connection.channel()
                
                # Déclaration de la file d'attente
                channel.queue_declare(queue='order_processing', durable=True)
                
                # Envoi du message
                message = json.dumps({'order_id': order_id, 'product': product})
                channel.basic_publish(
                    exchange='',
                    routing_key='order_processing',
                    body=message,
                    properties=pika.BasicProperties(
                        delivery_mode=2,  # Rend le message persistant
                    ))
                
                connection.close()
                print(f"Message envoyé à RabbitMQ: {message}")
                return f"Your process {order_id} has been created with this product: {product}"
            except Exception as e:
                print(f"Erreur lors de l'envoi du message: {e}")
                # Fallback au traitement synchrone en cas d'erreur
                process_order(order_id, product)
                return f"Your process {order_id} has been created with this product: {product} (processed synchronously due to RabbitMQ error)"
        else:
            # Fallback au traitement synchrone si RabbitMQ n'est pas disponible
            process_order(order_id, product)
            return f"Your process {order_id} has been created with this product: {product} (processed synchronously)"
    except Exception as e:
        # Fallback au traitement synchrone en cas d'erreur
        try:
            process_order(order_id, product)
            return f"Your process {order_id} has been created with this product: {product} (processed synchronously due to: {str(e)})"
        except Exception as inner_e:
            return f"Error creating order: {str(inner_e)}", 500

@app.route('/api/orders', methods=['GET'])
def get_order():
    try:
        order_id = request.args.get('order_id')
        if not order_id:
            return "Order ID is required", 400
            
        status = woody.get_order(order_id)
        return f'order "{order_id}": {status}'
    except Exception as e:
        return f"Error retrieving order: {str(e)}", 500

# Fonction interne pour le traitement synchrone
def process_order(order_id, order):
    status = woody.make_heavy_validation(order)
    woody.save_order(order_id, status, order)

if __name__ == "__main__":
    print("Starting order service...")
    woody.launch_server(app, host='0.0.0.0', port=5000)