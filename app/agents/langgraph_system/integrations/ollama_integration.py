"""
Integración con Ollama para LLMs locales
"""

import asyncio
import logging
from typing import Optional

import httpx
from langchain_ollama import ChatOllama, OllamaEmbeddings

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class OllamaIntegration:
    """Gestiona la integración con Ollama para LLMs y embeddings"""

    def __init__(self, base_url: str = None, model_name: str = None):
        self.settings = get_settings()
        self.base_url = base_url or self.settings.OLLAMA_API_URL
        self.model_name = model_name or self.settings.OLLAMA_API_MODEL
        self.embedding_model = self.settings.OLLAMA_API_MODEL_EMBEDDING

        # Cache de modelos
        self._llm_cache = {}
        self._embedding_cache = None

    def get_llm(self, temperature: float = 0.7, model: Optional[str] = None, **kwargs) -> ChatOllama:
        """
        Obtiene una instancia de ChatOllama configurada

        Args:
            temperature: Nivel de creatividad (0.0 a 1.0)
            model: Modelo específico a usar
            **kwargs: Parámetros adicionales para ChatOllama
        """
        model_to_use = model or self.model_name
        cache_key = f"{model_to_use}_{temperature}"

        if cache_key not in self._llm_cache:
            default_params = {
                "model": model_to_use,
                "base_url": self.base_url,
                "temperature": temperature,
                "num_gpu": 1,
                "num_thread": 4,
                "repeat_penalty": 1.1,
                "top_k": 40,
                "top_p": 0.9,
                "request_timeout": 60.0,
                "keep_alive": "5m",
            }

            # Merge with custom parameters
            default_params.update(kwargs)

            self._llm_cache[cache_key] = ChatOllama(**default_params)
            logger.debug(f"Created new ChatOllama instance for {model_to_use}")

        return self._llm_cache[cache_key]

    def get_embeddings(self, model: Optional[str] = None) -> OllamaEmbeddings:
        """
        Obtiene una instancia de OllamaEmbeddings

        Args:
            model: Modelo de embeddings a usar
        """
        if self._embedding_cache is None:
            embedding_model = model or self.embedding_model

            self._embedding_cache = OllamaEmbeddings(model=embedding_model, base_url=self.base_url)
            logger.debug(f"Created new OllamaEmbeddings instance for {embedding_model}")

        return self._embedding_cache

    async def health_check(self) -> bool:
        """
        Verifica la disponibilidad del servicio Ollama

        Returns:
            True si el servicio está disponible
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")

                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])

                    # Verificar que nuestros modelos están disponibles
                    model_names = [m["name"] for m in models]

                    has_chat_model = any(self.model_name in name for name in model_names)
                    has_embedding_model = any(self.embedding_model in name for name in model_names)

                    if not has_chat_model:
                        logger.warning(f"Chat model {self.model_name} not found")

                    if not has_embedding_model:
                        logger.warning(f"Embedding model {self.embedding_model} not found")

                    return has_chat_model and has_embedding_model

                return False

        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    async def list_models(self) -> list:
        """
        Lista todos los modelos disponibles en Ollama

        Returns:
            Lista de modelos disponibles
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")

                if response.status_code == 200:
                    data = response.json()
                    return data.get("models", [])

                return []

        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []

    async def pull_model(self, model_name: str) -> bool:
        """
        Descarga un modelo en Ollama

        Args:
            model_name: Nombre del modelo a descargar

        Returns:
            True si se descargó correctamente
        """
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minutos timeout
                response = await client.post(f"{self.base_url}/api/pull", json={"name": model_name})

                return response.status_code == 200

        except Exception as e:
            logger.error(f"Error pulling model {model_name}: {e}")
            return False

    async def test_llm(self, test_prompt: str = "Hello, world!") -> bool:
        """
        Prueba la funcionalidad del LLM

        Args:
            test_prompt: Prompt de prueba

        Returns:
            True si la prueba es exitosa
        """
        try:
            llm = self.get_llm(temperature=0.1)
            response = await llm.ainvoke(test_prompt)

            return bool(response and response.content.strip())  # type: ignore

        except Exception as e:
            logger.error(f"LLM test failed: {e}")
            return False

    async def test_embeddings(self, test_text: str = "Hello, world!") -> bool:
        """
        Prueba la funcionalidad de embeddings

        Args:
            test_text: Texto de prueba

        Returns:
            True si la prueba es exitosa
        """
        try:
            embeddings = self.get_embeddings()
            vectors = await embeddings.aembed_query(test_text)

            return bool(vectors and len(vectors) > 0)

        except Exception as e:
            logger.error(f"Embeddings test failed: {e}")
            return False

    async def comprehensive_test(self) -> dict:
        """
        Ejecuta todas las pruebas de Ollama

        Returns:
            Diccionario con resultados de las pruebas
        """
        results = {
            "service_available": False,
            "models_available": False,
            "llm_working": False,
            "embeddings_working": False,
            "models_list": [],
        }

        # Test 1: Servicio disponible
        results["service_available"] = await self.health_check()

        if results["service_available"]:
            # Test 2: Listar modelos
            models = await self.list_models()
            results["models_list"] = models
            results["models_available"] = len(models) > 0

            # Test 3: Probar LLM
            results["llm_working"] = await self.test_llm()

            # Test 4: Probar embeddings
            results["embeddings_working"] = await self.test_embeddings()

        return results

    def clear_cache(self):
        """Limpia el cache de instancias"""
        self._llm_cache.clear()
        self._embedding_cache = None
        logger.debug("Ollama cache cleared")

    async def ensure_models_available(self) -> bool:
        """
        Asegura que los modelos necesarios estén disponibles

        Returns:
            True si todos los modelos están disponibles
        """
        models = await self.list_models()
        model_names = [m["name"] for m in models]

        missing_models = []

        # Verificar modelo de chat
        if not any(self.model_name in name for name in model_names):
            missing_models.append(self.model_name)

        # Verificar modelo de embeddings
        if not any(self.embedding_model in name for name in model_names):
            missing_models.append(self.embedding_model)

        # Intentar descargar modelos faltantes
        if missing_models:
            logger.info(f"Downloading missing models: {missing_models}")

            for model in missing_models:
                success = await self.pull_model(model)
                if not success:
                    logger.error(f"Failed to download model: {model}")
                    return False

        return True

    def get_retry_llm(self, max_retries: int = 3, backoff_factor: float = 1.0, **llm_kwargs):
        """
        Obtiene un LLM con capacidades de reintento

        Args:
            max_retries: Número máximo de reintentos
            backoff_factor: Factor de espera exponencial
            **llm_kwargs: Parámetros para el LLM
        """
        base_llm = self.get_llm(**llm_kwargs)

        class RetryLLM:
            def __init__(self, llm, max_retries, backoff_factor):
                self.llm = llm
                self.max_retries = max_retries
                self.backoff_factor = backoff_factor

            async def ainvoke(self, prompt, **kwargs):
                last_exception = None

                for attempt in range(self.max_retries):
                    try:
                        return await self.llm.ainvoke(prompt, **kwargs)
                    except Exception as e:
                        last_exception = e

                        if attempt < self.max_retries - 1:
                            wait_time = backoff_factor * (2**attempt)
                            logger.warning(
                                f"LLM call failed (attempt {attempt + 1}/{self.max_retries}), "
                                f"retrying in {wait_time}s: {e}"
                            )
                            await asyncio.sleep(wait_time)
                        else:
                            logger.error(f"LLM call failed after {self.max_retries} attempts: {e}")

                raise last_exception  # type: ignore

            def __getattr__(self, name):
                return getattr(self.llm, name)

        return RetryLLM(base_llm, max_retries, backoff_factor)

    async def generate_response(
        self, system_prompt: str, user_prompt: str, model: Optional[str] = None, temperature: float = 0.7
    ) -> str:
        """
        Genera una respuesta usando el LLM de Ollama

        Args:
            system_prompt: Prompt del sistema
            user_prompt: Prompt del usuario
            model: Modelo específico a usar
            temperature: Temperatura para la generación

        Returns:
            Respuesta del LLM
        """
        try:
            llm = self.get_llm(temperature=temperature, model=model)

            # Crear el prompt combinado
            full_prompt = f"{system_prompt}\n\nUsuario: {user_prompt}\n\nAsistente:"

            # Generar respuesta
            response = await llm.ainvoke(full_prompt)

            return response.content if hasattr(response, "content") else str(response)  # type: ignore

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Lo siento, no pude procesar tu solicitud en este momento."

    async def get_model_info(self, model_name: str) -> dict:
        """
        Obtiene información detallada de un modelo

        Args:
            model_name: Nombre del modelo

        Returns:
            Información del modelo
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(f"{self.base_url}/api/show", json={"name": model_name})

                if response.status_code == 200:
                    return response.json()

                return {}

        except Exception as e:
            logger.error(f"Error getting model info for {model_name}: {e}")
            return {}
