from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import woody
from redis_wrapper import cache_result

app = Flask('misc_service')
cors = CORS(app)

@app.get('/api/ping')
def ping():
    return 'ping'

@app.route('/api/misc/time', methods=['GET'])
def get_time():
    return f'misc: {datetime.now()}'

@app.route('/api/misc/heavy', methods=['GET'])
@cache_result(ttl=30)
def get_heavy():
    try:
        name = request.args.get('name')
        r = woody.make_some_heavy_computation(name)
        return f'{datetime.now()}: {r}'
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("Starting misc service...")
    woody.launch_server(app, host='0.0.0.0', port=5000)