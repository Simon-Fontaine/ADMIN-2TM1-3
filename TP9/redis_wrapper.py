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