import redis
import json
from functools import wraps
import os

redis_host = os.environ.get('REDIS_HOST', 'redis')

# Connexion à Redis avec retry
def get_redis_client():
    retries = 5
    while retries > 0:
        try:
            client = redis.Redis(host=redis_host, port=6379, db=0, socket_timeout=5)
            client.ping()  # Vérifier la connexion
            return client
        except redis.exceptions.ConnectionError:
            retries -= 1
            if retries == 0:
                print("Impossible de se connecter à Redis après plusieurs tentatives")
                return None
            print(f"Tentative de reconnexion à Redis dans 1 seconde... ({retries} restantes)")
            import time
            time.sleep(1)

# Initialisation globale
redis_client = get_redis_client()

def cache_result(ttl=60):
    """
    Décorateur pour mettre en cache les résultats d'une fonction
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Si Redis n'est pas disponible, exécuter la fonction sans cache
            if redis_client is None:
                print("Redis non disponible, exécution sans cache")
                return f(*args, **kwargs)
            
            # Générer une clé unique basée sur le nom de la fonction et ses arguments
            key = f"{f.__name__}:{str(args)}:{str(kwargs)}"
            
            try:
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
            except Exception as e:
                print(f"Erreur avec Redis: {e}")
                # En cas d'erreur, exécuter la fonction sans cache
                return f(*args, **kwargs)
                
        return decorated_function
    return decorator