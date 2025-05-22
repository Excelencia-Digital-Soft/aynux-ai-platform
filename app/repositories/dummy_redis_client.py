import logging

logger = logging.getLogger(__name__)


class DummyRedisClient:
    """Cliente Redis dummy para manejar errores de conexión."""

    def __init__(self):
        self.local_storage = {}
        logger.warning("Utilizando almacenamiento local como fallback para Redis")

    def get(self, key):
        logger.debug(f"DummyRedis: get {key}")
        return self.local_storage.get(key)

    def set(self, key, value, ex=None, nx=False):
        logger.debug(f"DummyRedis: set {key}")
        if nx and key in self.local_storage:
            return False
        self.local_storage[key] = value
        return True

    def delete(self, key):
        logger.debug(f"DummyRedis: delete {key}")
        if key in self.local_storage:
            del self.local_storage[key]
            return 1
        return 0

    def exists(self, key):
        return key in self.local_storage

    def hset(self, name, key, value):
        if name not in self.local_storage:
            self.local_storage[name] = {}
        self.local_storage[name][key] = value
        return 1

    def hget(self, name, key):
        if name in self.local_storage and isinstance(self.local_storage[name], dict):
            return self.local_storage[name].get(key)
        return None

    def hgetall(self, name):
        if name in self.local_storage and isinstance(self.local_storage[name], dict):
            return self.local_storage[name]
        return {}

    def hdel(self, name, key):
        if name in self.local_storage and key in self.local_storage[name]:
            del self.local_storage[name][key]
            return 1
        return 0

    def ping(self):
        return True
