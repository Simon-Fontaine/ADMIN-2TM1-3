import os
import pika
import json
import time
import sys
import woody

def callback(ch, method, properties, body):
    print(f" [x] Received {body}")
    
    try:
        # Parse le message
        message = json.loads(body)
        order_id = message['order_id']
        product = message['product']
        
        # Traitement de la commande
        print(f" [x] Processing order {order_id} for product {product}")
        status = woody.make_heavy_validation(product)
        woody.save_order(order_id, status, product)
        
        print(f" [x] Done processing order {order_id}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"Error processing message: {e}")
        # Rejet du message pour qu'il soit retraité plus tard
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def main():
    # Attente que RabbitMQ soit prêt
    print("Waiting for RabbitMQ to be ready...")
    time.sleep(30)
    
    # Connection à RabbitMQ
    retries = 0
    max_retries = 10
    
    while retries < max_retries:
        try:
            print(f"Attempt {retries+1} to connect to RabbitMQ...")
            connection = pika.BlockingConnection(pika.ConnectionParameters(
                host="rabbitmq",
                heartbeat=600,
                blocked_connection_timeout=300
            ))
            
            channel = connection.channel()
            
            # Déclaration de la file d'attente
            channel.queue_declare(queue='order_processing', durable=True)
            
            # Configuration pour ne pas envoyer plus d'un message à la fois à un worker
            channel.basic_qos(prefetch_count=1)
            
            # Configuration du callback pour la consommation des messages
            channel.basic_consume(queue='order_processing', on_message_callback=callback)
            
            print(' [*] Waiting for messages. To exit press CTRL+C')
            channel.start_consuming()
            
            break
        except Exception as e:
            retries += 1
            print(f"Failed to connect to RabbitMQ: {e}")
            if retries < max_retries:
                wait_time = 5 * retries  # Backoff exponentiel
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("Max retries reached. Exiting.")
                sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        sys.exit(0)