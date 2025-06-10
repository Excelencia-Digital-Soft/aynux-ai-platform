import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.models.message import Message
from app.models.vectorial import VectorDBConfig, VectorDocument, VectorQueryResult
from app.services.ai_service import AIService
from app.services.vector_service import VectorDatabaseService

logger = logging.getLogger(__name__)


class CategoryVectorService:
    """
    Servicio para manejar información vectorial de categorías por APP.

    Este servicio se encarga de:
    1. Recuperar información vectorial de categorías desde la base de datos vectorial
    2. Actualizar vectores de categorías de forma automática o manual
    3. Proporcionar búsquedas semánticas sobre categorías
    """

    def __init__(self):
        self.ai_service = AIService()
        self.vector_service = VectorDatabaseService()

        # Configuración para actualizaciones automáticas
        self.update_scheduler = None
        self.is_scheduler_running = False

    async def get_app_categories(self, app_id: str) -> List[Dict[str, Any]]:
        """
        Recupera las categorías disponibles para una APP desde la base de datos vectorial.

        Args:
            app_id: ID de la APP

        Returns:
            Lista de categorías con su información
        """
        try:
            # Configurar consulta para recuperar categorías
            config = VectorDBConfig(user_id=app_id, collection_name=f"app_{app_id}_categories")

            # Buscar todas las categorías de la APP
            results = await self.vector_service.query_user_data(
                config=config,
                query="categorías disponibles",
                k=100,  # Recuperar todas las categorías posibles
                filter_dict={"type": "category"},
            )

            # Extraer información de categorías
            categories = []
            for result in results:
                if isinstance(result.content, str):
                    try:
                        category_data = json.loads(result.content)
                    except json.JSONDecodeError:
                        category_data = {"name": result.content}
                else:
                    category_data = result.content

                categories.append(category_data)

            logger.info(f"Retrieved {len(categories)} categories for APP {app_id}")
            return categories

        except Exception as e:
            logger.error(f"Error retrieving categories for APP {app_id}: {str(e)}")
            return []

    async def determine_search_category(
        self, app_id: str, user_message: str, conversation_history: List[Message]
    ) -> Dict[str, Any]:
        """
        Determina la categoría de búsqueda basándose en el mensaje del usuario
        y las categorías disponibles en la APP.

        Args:
            app_id: ID de la APP
            user_message: Mensaje actual del usuario
            conversation_history: Historial de conversación

        Returns:
            Diccionario con la categoría determinada e información adicional
        """
        try:
            # Obtener categorías disponibles para la APP
            categories = await self.get_app_categories(app_id)

            if not categories:
                logger.warning(f"No categories found for APP {app_id}")
                return {
                    "category": "all_products",
                    "subcategory": None,
                    "confidence": 0.5,
                    "reasoning": "No hay categorías disponibles en el sistema",
                }

            # Construir contexto de conversación
            context = "\n".join([f"{msg.role}: {msg.content}" for msg in conversation_history[-5:]])

            # Formatear categorías para el prompt
            categories_info = json.dumps(categories, ensure_ascii=False, indent=2)

            prompt = f"""Analiza el siguiente mensaje del usuario y el contexto de la conversación
para determinar qué categoría de productos está buscando.

Contexto de conversación:
{context}

Mensaje actual del usuario: {user_message}

Categorías disponibles en el sistema:
{categories_info}

Responde ÚNICAMENTE con un JSON en el siguiente formato:
{{
    "category": "nombre_categoria",
    "subcategory": "nombre_subcategoria o null",
    "category_id": "id_de_categoria o null",
    "confidence": 0.95,
    "reasoning": "breve explicación"
}}

Si no puedes determinar una categoría específica con confianza, usa "all_products".
"""

            response = await self.ai_service.generate_response(prompt, temperature=0.1)
            result = json.loads(response.strip())

            # Validar respuesta
            if "category" not in result:
                result = {
                    "category": "all_products",
                    "subcategory": None,
                    "category_id": None,
                    "confidence": 0.5,
                    "reasoning": "No se pudo determinar categoría específica",
                }

            return result

        except Exception as e:
            logger.error(f"Error determining search category: {str(e)}")
            return {
                "category": "all_products",
                "subcategory": None,
                "category_id": None,
                "confidence": 0.5,
                "reasoning": f"Error en determinación: {str(e)}",
            }

    async def search_category_products(
        self, app_id: str, category: str, subcategory: Optional[str] = None, filters: Optional[Dict[str, Any]] = None
    ) -> List[VectorQueryResult]:
        """
        Busca productos dentro de una categoría específica usando búsqueda vectorial.

        Args:
            app_id: ID de la APP
            category: Categoría principal
            subcategory: Subcategoría opcional
            filters: Filtros adicionales

        Returns:
            Lista de productos encontrados
        """
        try:
            config = VectorDBConfig(user_id=app_id, collection_name=f"app_{app_id}_products")

            # Construir query de búsqueda
            search_query = f"productos de categoría {category}"
            if subcategory:
                search_query += f" subcategoría {subcategory}"

            # Preparar filtros
            search_filters = {"type": "product", "category": category}
            if subcategory:
                search_filters["subcategory"] = subcategory
            if filters:
                search_filters.update(filters)

            # Realizar búsqueda
            results = await self.vector_service.query_user_data(
                config=config, query=search_query, k=20, filter_dict=search_filters
            )

            logger.info(f"Found {len(results)} products in category {category}")
            return results

        except Exception as e:
            logger.error(f"Error searching category products: {str(e)}")
            return []

    async def update_category_vectors(
        self, app_id: str, categories_data: List[Dict[str, Any]], update_type: str = "manual"
    ) -> Tuple[bool, str]:
        """
        Actualiza los vectores de categorías para una APP.

        Args:
            app_id: ID de la APP
            categories_data: Datos de categorías a actualizar
            update_type: Tipo de actualización ("manual" o "automatic")

        Returns:
            Tupla (éxito, mensaje)
        """
        try:
            logger.info(f"Starting {update_type} category vector update for APP {app_id}")

            # Preparar documentos vectoriales
            vector_documents = []
            for category in categories_data:
                # Generar contenido enriquecido con AI
                enriched_content = await self._enrich_category_content(category)

                vector_doc = VectorDocument(
                    content=enriched_content,
                    metadata={
                        "type": "category",
                        "category_id": category.get("id", ""),
                        "category_name": category.get("name", ""),
                        "app_id": app_id,
                        "update_type": update_type,
                        "updated_at": datetime.now().isoformat(),
                    },
                )
                vector_documents.append(vector_doc)

            # Configurar base de datos vectorial
            config = VectorDBConfig(user_id=app_id, collection_name=f"app_{app_id}_categories")

            # Actualizar vectores
            success, doc_ids = await self.vector_service.add_user_data(config=config, data=vector_documents)

            if success:
                message = f"Successfully updated {len(doc_ids)} category vectors"
                logger.info(message)
            else:
                message = "Failed to update category vectors"
                logger.error(message)

            return success, message

        except Exception as e:
            error_msg = f"Error updating category vectors: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    async def _enrich_category_content(self, category: Dict[str, Any]) -> str:
        """
        Enriquece el contenido de una categoría usando AI para mejorar
        la búsqueda semántica.

        Args:
            category: Datos de la categoría

        Returns:
            Contenido enriquecido como string JSON
        """
        try:
            category_name = category.get("name", "")
            category_description = category.get("description", "")

            prompt = f"""Genera una descripción enriquecida para la siguiente categoría de productos.
Incluye sinónimos, términos relacionados y características típicas de productos en esta categoría.

Categoría: {category_name}
Descripción original: {category_description}

Responde con un JSON que contenga:
{{
    "name": "{category_name}",
    "description": "descripción mejorada",
    "keywords": ["lista", "de", "palabras", "clave"],
    "related_terms": ["términos", "relacionados"],
    "typical_features": ["características", "típicas"]
}}
"""

            response = await self.ai_service.generate_response(prompt, temperature=0.3)
            enriched_data = json.loads(response.strip())

            # Combinar con datos originales
            enriched_category = {**category, **enriched_data, "original_data": category}

            return json.dumps(enriched_category, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Error enriching category content: {str(e)}")
            # Fallback: retornar datos originales
            return json.dumps(category, ensure_ascii=False)

    async def start_automatic_updates(self, app_id: str, interval_hours: int = 24) -> bool:
        """
        Inicia actualizaciones automáticas de categorías para una APP.

        Args:
            app_id: ID de la APP
            interval_hours: Intervalo entre actualizaciones en horas

        Returns:
            True si se inició correctamente
        """
        try:
            if self.is_scheduler_running:
                logger.warning("Scheduler already running")
                return False

            self.is_scheduler_running = True

            async def update_task():
                while self.is_scheduler_running:
                    try:
                        # Aquí se debería obtener las categorías desde la BD principal
                        # Por ahora simulamos con un placeholder
                        logger.info(f"Running automatic category update for APP {app_id}")

                        # TODO: Implementar obtención de categorías desde BD principal
                        # categories = await self.get_categories_from_main_db(app_id)
                        # await self.update_category_vectors(app_id, categories, "automatic")

                    except Exception as e:
                        logger.error(f"Error in automatic update: {str(e)}")

                    # Esperar hasta la próxima actualización
                    await asyncio.sleep(interval_hours * 3600)

            # Iniciar tarea en background
            self.update_scheduler = asyncio.create_task(update_task())
            logger.info(f"Started automatic updates for APP {app_id} every {interval_hours} hours")
            return True

        except Exception as e:
            logger.error(f"Error starting automatic updates: {str(e)}")
            return False

    async def stop_automatic_updates(self) -> bool:
        """
        Detiene las actualizaciones automáticas.

        Returns:
            True si se detuvo correctamente
        """
        try:
            self.is_scheduler_running = False

            if self.update_scheduler:
                self.update_scheduler.cancel()
                try:
                    await self.update_scheduler
                except asyncio.CancelledError:
                    pass

            logger.info("Stopped automatic updates")
            return True

        except Exception as e:
            logger.error(f"Error stopping automatic updates: {str(e)}")
            return False

    async def enhance_search_query(self, app_id: str, user_message: str, category: str) -> str:
        """
        Mejora la consulta de búsqueda basándose en el contexto de la categoría
        y las características específicas de la APP.

        Args:
            app_id: ID de la APP
            user_message: Mensaje original del usuario
            category: Categoría determinada

        Returns:
            Consulta mejorada
        """
        try:
            # Obtener información de la categoría
            config = VectorDBConfig(user_id=app_id, collection_name=f"app_{app_id}_categories")

            category_results = await self.vector_service.query_user_data(
                config=config, query=category, k=1, filter_dict={"type": "category", "category_name": category}
            )

            category_context = ""
            if category_results:
                category_data = category_results[0].content
                if isinstance(category_data, str):
                    try:
                        category_data = json.loads(category_data)
                    except:  # noqa: E722
                        pass

                if isinstance(category_data, dict):
                    keywords = category_data.get("keywords", [])
                    related_terms = category_data.get("related_terms", [])
                    category_context = (
                        f"Palabras clave: {', '.join(keywords)}. Términos relacionados: {', '.join(related_terms)}"
                    )

            prompt = f"""Mejora la siguiente consulta de búsqueda para la categoría '{category}'.
Expande la consulta con sinónimos y términos relacionados relevantes para mejorar la búsqueda semántica.

Consulta original: {user_message}
Categoría: {category}
{category_context}

Responde SOLO con la consulta mejorada, sin explicaciones adicionales.
La consulta debe ser natural y enfocada en encontrar productos relevantes.
"""

            enhanced_query = await self.ai_service.generate_response(prompt, temperature=0.3)
            return enhanced_query.strip()

        except Exception as e:
            logger.error(f"Error enhancing search query: {str(e)}")
            return user_message

