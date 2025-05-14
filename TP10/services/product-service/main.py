from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import woody
import redis
from redis_wrapper import cache_result

app = Flask('product_service')
cors = CORS(app)

# Utilisation du client redis depuis redis_wrapper
from redis_wrapper import redis_client

@app.get('/api/ping')
def ping():
    return 'ping'

@app.route('/api/products', methods=['GET'])
def add_product():
    try:
        product = request.args.get('product')
        if not product:
            return "Product name is required", 400
            
        woody.add_product(str(product))
        
        # Invalider le cache pour get_last_product
        try:
            if redis_client:
                redis_client.delete('get_last_product:():{}')
                print("Cache invalidé pour get_last_product")
            else:
                print("Redis non disponible, pas d'invalidation du cache")
        except Exception as e:
            print(f"Warning: Failed to invalidate cache: {e}")
            
        return str(product)
    except Exception as e:
        print(f"Error adding product: {e}")
        return f"Error adding product: {str(e)}", 500

@app.route('/api/products/<int:product_id>', methods=['GET'])
def get_product(product_id):
    return "not yet implemented"

@app.route('/api/products/last', methods=['GET'])
@cache_result(ttl=15)
def get_last_product():
    last_product = woody.get_last_product()
    return f'db: {datetime.now()} - {last_product}'

if __name__ == "__main__":
    print("Starting product service...")
    woody.launch_server(app, host='0.0.0.0', port=5000)