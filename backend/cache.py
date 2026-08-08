import socket
from flask_caching import Cache

cache = Cache()


def redis_available():
    try:
        with socket.create_connection(("127.0.0.1", 6379), timeout=0.25):
            return True
    except OSError:
        return False


def clear_cache():
    try:
        cache.clear()
    except Exception:
        pass
