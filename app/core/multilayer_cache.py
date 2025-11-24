"""
Sistema de caché multicapa para optimizar respuestas comunes y embeddings
"""

import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class CacheLayer(Enum):
    """Capas del sistema de caché"""

    L1_RESPONSES = "l1_responses"  # Respuestas comunes y frecuentes
    L2_EMBEDDINGS = "l2_embeddings"  # Embeddings de productos y categorías
    L3_LLM_RESULTS = "l3_llm_results"  # Resultados de LLM cacheable


@dataclass
class CacheEntry:
    """Entrada de caché con metadatos"""

    key: str
    value: Any
    timestamp: float
    ttl: float
    layer: CacheLayer
    access_count: int = 0
    last_access: float = 0
    size_bytes: int = 0


class CacheBackend(ABC):
    """Interfaz abstracta para backends de caché"""

    @abstractmethod
    async def get(self, key: str) -> Optional[CacheEntry]:
        pass

    @abstractmethod
    async def set(self, key: str, entry: CacheEntry) -> bool:
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        pass

    @abstractmethod
    async def clear(self) -> int:
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        pass


class MemoryCacheBackend(CacheBackend):
    """Backend de caché en memoria con LRU"""

    def __init__(self, max_size: int = 10000, max_memory_mb: int = 100):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats: Dict[str, int] = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0,
            "current_size": 0,
            "current_memory_bytes": 0,
        }

    async def get(self, key: str) -> Optional[CacheEntry]:
        if key in self._cache:
            entry = self._cache.pop(key)  # Remove and re-insert (LRU)
            self._cache[key] = entry

            # Check TTL
            if time.time() - entry.timestamp > entry.ttl:
                await self.delete(key)
                self._stats["misses"] += 1
                return None

            # Update access stats
            entry.access_count += 1
            entry.last_access = time.time()
            self._stats["hits"] += 1
            return entry

        self._stats["misses"] += 1
        return None

    async def set(self, key: str, entry: CacheEntry) -> bool:
        # Calculate entry size
        entry.size_bytes = self._calculate_size(entry.value)

        # Check if we need to evict entries
        await self._evict_if_needed(entry.size_bytes)

        # Remove old entry if exists
        if key in self._cache:
            old_entry = self._cache[key]
            self._stats["current_memory_bytes"] -= old_entry.size_bytes

        # Add new entry
        self._cache[key] = entry
        self._stats["sets"] += 1
        self._stats["current_size"] = len(self._cache)
        self._stats["current_memory_bytes"] += entry.size_bytes

        return True

    async def delete(self, key: str) -> bool:
        if key in self._cache:
            entry = self._cache.pop(key)
            self._stats["deletes"] += 1
            self._stats["current_size"] = len(self._cache)
            self._stats["current_memory_bytes"] -= entry.size_bytes
            return True
        return False

    async def clear(self) -> int:
        count = len(self._cache)
        self._cache.clear()
        self._stats["current_size"] = 0
        self._stats["current_memory_bytes"] = 0
        return count

    def get_stats(self) -> Dict[str, Any]:
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / max(total_requests, 1)) * 100

        return {
            **self._stats,
            "hit_rate": f"{hit_rate:.1f}%",
            "memory_usage_mb": f"{self._stats['current_memory_bytes'] / 1024 / 1024:.1f}",
            "memory_limit_mb": f"{self.max_memory_bytes / 1024 / 1024:.1f}",
            "size_limit": self.max_size,
        }

    def _calculate_size(self, value: Any) -> int:
        """Calcular tamaño aproximado del valor"""
        try:
            if isinstance(value, str):
                return len(value.encode("utf-8"))
            elif isinstance(value, (list, dict)):
                return len(json.dumps(value).encode("utf-8"))
            else:
                return len(str(value).encode("utf-8"))
        except Exception:
            return 100  # Estimación por defecto

    async def _evict_if_needed(self, new_entry_size: int):
        """Evitar entradas si es necesario (LRU)"""
        while (
            len(self._cache) >= self.max_size
            or self._stats["current_memory_bytes"] + new_entry_size > self.max_memory_bytes
        ):
            if not self._cache:
                break

            # Evict least recently used
            oldest_key = next(iter(self._cache))
            oldest_entry = self._cache.pop(oldest_key)
            self._stats["evictions"] += 1
            self._stats["current_memory_bytes"] -= oldest_entry.size_bytes

        self._stats["current_size"] = len(self._cache)


class MultiLayerCache:
    """
    Sistema de caché multicapa optimizado para bot multi-dominio.

    L1 (Responses): Respuestas comunes frecuentes (TTL corto, alta velocidad)
    L2 (Embeddings): Embeddings de productos/categorías (TTL largo, alto costo computacional)
    L3 (LLM Results): Resultados de LLM cacheables (TTL medio, costo medio)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        # Configuración por capa
        self.layer_config = {
            CacheLayer.L1_RESPONSES: {
                "ttl": self.config.get("l1_ttl", 300),  # 5 minutos
                "max_size": self.config.get("l1_size", 1000),
                "max_memory_mb": self.config.get("l1_memory", 10),
            },
            CacheLayer.L2_EMBEDDINGS: {
                "ttl": self.config.get("l2_ttl", 86400),  # 24 horas
                "max_size": self.config.get("l2_size", 5000),
                "max_memory_mb": self.config.get("l2_memory", 50),
            },
            CacheLayer.L3_LLM_RESULTS: {
                "ttl": self.config.get("l3_ttl", 3600),  # 1 hora
                "max_size": self.config.get("l3_size", 2000),
                "max_memory_mb": self.config.get("l3_memory", 20),
            },
        }

        # Inicializar backends por capa
        self.backends = {}
        for layer in CacheLayer:
            config = self.layer_config[layer]
            self.backends[layer] = MemoryCacheBackend(
                max_size=config["max_size"], max_memory_mb=config["max_memory_mb"]
            )

        # Estadísticas globales
        self._global_stats: Dict[str, Union[int, Dict[str, Any]]] = {
            "total_hits": 0,
            "total_misses": 0,
            "total_sets": 0,
            "layer_performance": {},
        }

        logger.info("MultiLayerCache initialized with 3 layers")

    async def get(self, key: str, layer: CacheLayer) -> Optional[Any]:
        """
        Obtener valor del caché.

        Args:
            key: Clave del caché
            layer: Capa específica

        Returns:
            Valor del caché o None si no existe/expiró
        """
        backend = self.backends[layer]
        entry = await backend.get(key)

        if entry:
            hits = self._global_stats["total_hits"]
            assert isinstance(hits, int)
            self._global_stats["total_hits"] = hits + 1
            return entry.value

        misses = self._global_stats["total_misses"]
        assert isinstance(misses, int)
        self._global_stats["total_misses"] = misses + 1
        return None

    async def set(self, key: str, value: Any, layer: CacheLayer, ttl: Optional[float] = None) -> bool:
        """
        Almacenar valor en el caché.

        Args:
            key: Clave del caché
            value: Valor a almacenar
            layer: Capa específica
            ttl: TTL personalizado (opcional)

        Returns:
            True si se almacenó exitosamente
        """
        backend = self.backends[layer]
        config = self.layer_config[layer]

        entry = CacheEntry(key=key, value=value, timestamp=time.time(), ttl=ttl or config["ttl"], layer=layer)

        success = await backend.set(key, entry)
        if success:
            sets = self._global_stats["total_sets"]
            assert isinstance(sets, int)
            self._global_stats["total_sets"] = sets + 1

        return success

    async def get_response(self, key: str) -> Optional[str]:
        """Obtener respuesta común del caché L1"""
        return await self.get(key, CacheLayer.L1_RESPONSES)

    async def set_response(self, key: str, response: str, ttl: Optional[float] = None) -> bool:
        """Almacenar respuesta común en caché L1"""
        return await self.set(key, response, CacheLayer.L1_RESPONSES, ttl)

    async def get_embedding(self, key: str) -> Optional[List[float]]:
        """Obtener embedding del caché L2"""
        return await self.get(key, CacheLayer.L2_EMBEDDINGS)

    async def set_embedding(self, key: str, embedding: List[float], ttl: Optional[float] = None) -> bool:
        """Almacenar embedding en caché L2"""
        return await self.set(key, embedding, CacheLayer.L2_EMBEDDINGS, ttl)

    async def get_llm_result(self, key: str) -> Optional[Dict[str, Any]]:
        """Obtener resultado de LLM del caché L3"""
        return await self.get(key, CacheLayer.L3_LLM_RESULTS)

    async def set_llm_result(self, key: str, result: Dict[str, Any], ttl: Optional[float] = None) -> bool:
        """Almacenar resultado de LLM en caché L3"""
        return await self.set(key, result, CacheLayer.L3_LLM_RESULTS, ttl)

    def generate_key(self, *components: Union[str, int, float]) -> str:
        """
        Generar clave de caché consistente a partir de componentes.

        Args:
            *components: Componentes para la clave

        Returns:
            Clave hash consistente
        """
        key_string = "|".join(str(c) for c in components)
        return hashlib.md5(key_string.encode()).hexdigest()

    async def invalidate_pattern(self, pattern: str, layer: Optional[CacheLayer] = None):
        """
        Invalidar entradas que coincidan con un patrón.

        Args:
            pattern: Patrón de clave (simple substring match)
            layer: Capa específica (opcional, si None invalida en todas)
        """
        layers_to_check = [layer] if layer else list(CacheLayer)
        invalidated_count = 0

        for cache_layer in layers_to_check:
            backend = self.backends[cache_layer]
            # Note: Esta implementación es básica - para producción se necesitaría
            # un backend más sofisticado que soporte pattern matching
            keys_to_delete = []

            # En memory backend, necesitamos iterar (no muy eficiente)
            for key in backend._cache.keys():
                if pattern in key:
                    keys_to_delete.append(key)

            for key in keys_to_delete:
                await backend.delete(key)
                invalidated_count += 1

        logger.info(f"Invalidated {invalidated_count} cache entries matching pattern '{pattern}'")
        return invalidated_count

    async def clear_layer(self, layer: CacheLayer) -> int:
        """Limpiar una capa específica del caché"""
        backend = self.backends[layer]
        count = await backend.clear()
        logger.info(f"Cleared {count} entries from cache layer {layer.value}")
        return count

    async def clear_all(self) -> Dict[CacheLayer, int]:
        """Limpiar todas las capas del caché"""
        results = {}
        for layer in CacheLayer:
            count = await self.clear_layer(layer)
            results[layer] = count
        return results

    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas completas del sistema de caché"""
        layer_stats = {}
        total_memory_mb = 0
        total_entries = 0

        for layer in CacheLayer:
            backend_stats = self.backends[layer].get_stats()
            layer_stats[layer.value] = backend_stats

            # Sumar métricas globales
            total_memory_mb += float(backend_stats["memory_usage_mb"])
            total_entries += backend_stats["current_size"]

        # Calcular hit rate global
        total_hits = self._global_stats["total_hits"]
        assert isinstance(total_hits, int)
        total_misses = self._global_stats["total_misses"]
        assert isinstance(total_misses, int)

        total_requests = total_hits + total_misses
        global_hit_rate = (total_hits / max(total_requests, 1)) * 100

        return {
            "global_stats": {
                **self._global_stats,
                "global_hit_rate": f"{global_hit_rate:.1f}%",
                "total_memory_mb": f"{total_memory_mb:.1f}",
                "total_entries": total_entries,
                "total_requests": total_requests,
            },
            "layer_stats": layer_stats,
            "configuration": self.layer_config,
        }

    async def health_check(self) -> Dict[str, Any]:
        """Verificar estado de salud del sistema de caché"""
        health: Dict[str, Any] = {"status": "healthy", "issues": []}

        for layer in CacheLayer:
            backend_stats = self.backends[layer].get_stats()

            # Verificar uso de memoria
            memory_usage = float(backend_stats["memory_usage_mb"])
            memory_limit = float(backend_stats["memory_limit_mb"])
            memory_percent = (memory_usage / memory_limit) * 100

            if memory_percent > 90:
                issues = health["issues"]
                assert isinstance(issues, list)
                issues.append(f"Layer {layer.value} memory usage high: {memory_percent:.1f}%")

            # Verificar hit rate
            hit_rate = float(backend_stats["hit_rate"].rstrip("%"))
            if hit_rate < 20:  # Hit rate muy bajo
                issues = health["issues"]
                assert isinstance(issues, list)
                issues.append(f"Layer {layer.value} hit rate low: {hit_rate:.1f}%")

        if health["issues"]:
            health["status"] = "degraded"

        return health


# Clase de conveniencia para respuestas comunes de e-commerce
class AynuxResponseCache:
    """Cache especializado para respuestas comunes de e-commerce"""

    def __init__(self, multilayer_cache: MultiLayerCache):
        self.cache = multilayer_cache

        # Respuestas pre-cacheadas comunes
        self.common_responses = {
            "greeting": "¡Hola! Bienvenido a nuestra tienda. ¿En qué puedo ayudarte hoy?",
            "categories": "Tenemos estas categorías: Smartphones, Laptops, Tablets, Audio y Accesorios.",
            "shipping_info": "Realizamos envíos a todo el país. El tiempo de entrega es de 2-5 días hábiles.",
            "payment_methods": "Aceptamos tarjeta de crédito, débito, transferencia bancaria y efectivo.",
            "warranty": "Todos nuestros productos tienen garantía oficial del fabricante.",
            "support_hours": "Nuestro horario de atención es de lunes a viernes de 9:00 a 18:00.",
        }

    async def initialize_common_responses(self):
        """Precargar respuestas comunes en el caché"""
        for key, response in self.common_responses.items():
            await self.cache.set_response(key, response, ttl=86400)  # 24 horas

        logger.info(f"Initialized {len(self.common_responses)} common responses in cache")

    async def get_common_response(self, intent: str, _: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Obtener respuesta común basada en intención"""
        cache_key = self.cache.generate_key("common_response", intent)
        return await self.cache.get_response(cache_key)

    async def cache_product_response(self, product_query: str, response: str, ttl: int = 1800):
        """Cachear respuesta de producto específico"""
        cache_key = self.cache.generate_key("product_response", product_query.lower())
        await self.cache.set_response(cache_key, response, ttl)

