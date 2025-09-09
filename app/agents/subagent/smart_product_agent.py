"""
Smart Product Agent - Agente inteligente para búsquedas de productos usando lenguaje natural.

Este agente puede:
1. Interpretar consultas complejas en lenguaje natural
2. Usar búsqueda semántica y SQL dinámico
3. Entender relaciones entre categorías, marcas, características
4. Generar respuestas contextuales usando AI
5. Adaptarse dinámicamente sin lógica hardcodeada
"""

import json
import logging
from typing import Any, Dict, List, Optional

from ..integrations.ai_data_integration import AgentDataContext
from ..integrations.ollama_integration import OllamaIntegration
from ..tools.product_sql_generator import ProductSQLGenerator
from ..tools.smart_product_search_tool import SmartProductSearchTool
from ..utils.tracing import trace_async_method
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class SmartProductAgent(BaseAgent):
    """
    Agente inteligente para búsquedas avanzadas de productos usando AI.

    Capacidades:
    - Interpretación de lenguaje natural sin reglas hardcodeadas
    - Búsqueda semántica usando embeddings
    - Generación dinámica de SQL para consultas complejas
    - Respuestas contextuales e inteligentes
    - Manejo de relaciones entre productos, categorías y marcas
    """

    def __init__(self, ollama=None, postgres=None, config: Optional[Dict[str, Any]] = None):
        super().__init__("smart_product_agent", config or {}, ollama=ollama, postgres=postgres)

        # Configuración específica del agente
        self.max_results = self.config.get("max_results", 10)
        self.enable_semantic_search = self.config.get("enable_semantic_search", True)
        self.enable_dynamic_sql = self.config.get("enable_dynamic_sql", True)
        self.response_style = self.config.get("response_style", "conversational")
        self.include_suggestions = self.config.get("include_suggestions", True)

        # Inicializar componentes
        self.ollama = ollama or OllamaIntegration()
        self.data_context = AgentDataContext()
        self.search_tool = SmartProductSearchTool(self.ollama, postgres)
        self.sql_generator = ProductSQLGenerator(self.ollama, postgres)

        # Tipos de consultas que puede manejar (para análisis, no para hardcoding)
        self.query_patterns = {
            "product_search": ["busca", "muestra", "quiero", "necesito", "encuentrame"],
            "comparison": ["compara", "diferencia", "mejor", "vs", "versus"],
            "availability": ["stock", "disponible", "hay", "tienen"],
            "specifications": ["características", "specs", "especificaciones"],
            "price_range": ["precio", "cuesta", "vale", "barato", "caro"],
            "recommendations": ["recomienda", "sugiere", "que me aconsejas"],
            "category_browse": ["categoría", "tipo", "clase", "sección"],
        }

    @trace_async_method(
        name="smart_product_agent_process",
        run_type="chain",
        metadata={"agent_type": "smart_product", "ai_search": "semantic_sql"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa consultas de productos usando AI avanzado.

        Args:
            message: Mensaje del usuario
            state_dict: Estado actual como diccionario

        Returns:
            Diccionario con actualizaciones para el estado
        """
        try:
            # 1. Análisis inteligente de la intención del usuario
            intent_analysis = await self._analyze_user_intent(message, state_dict)

            # 2. Ejecutar búsqueda inteligente basada en la intención
            search_results = await self._execute_intelligent_search(message, intent_analysis, state_dict)

            # 3. Generar respuesta contextual e inteligente
            if search_results.get("success", False):
                ai_response = await self._generate_intelligent_response(
                    message, intent_analysis, search_results, state_dict
                )
            else:
                ai_response = await self._handle_no_results(message, intent_analysis, search_results)

            return {
                "messages": [{"role": "assistant", "content": ai_response}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "retrieved_data": {
                    "intent": intent_analysis,
                    "search_method": search_results.get("method", "unknown"),
                    "results_count": search_results.get("count", 0),
                    "products": search_results.get("products", []),
                },
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in smart product agent: {str(e)}")
            error_response = await self._generate_error_response(message, str(e))

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    async def _analyze_user_intent(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analiza la intención del usuario usando AI avanzado.

        No usa reglas hardcodeadas, sino que permite que la AI interprete libremente.
        """

        # Obtener contexto del usuario si está disponible
        user_id = self._extract_user_id(state_dict)
        user_context = ""

        if user_id and self.data_context:
            try:
                user_context = await self.data_context.get_user_product_preferences(user_id)
            except Exception as e:
                logger.warning(f"Could not get user context: {e}")

        intent_prompt = f"""# ANÁLISIS DE INTENCIÓN DE PRODUCTO

## MENSAJE DEL USUARIO:
"{message}"

## CONTEXTO DEL USUARIO:
{user_context if user_context else "No hay contexto previo disponible"}

## INSTRUCCIONES:
Analiza la intención del usuario y responde en JSON con la siguiente estructura:

{{
  "intent_type": "search_general|search_specific|comparison|availability_check|price_inquiry|category_browse
    |recommendation_request|specification_inquiry",
  
  "search_params": {{
    "keywords": ["lista", "de", "palabras", "clave"],
    "product_name": "nombre específico si lo hay|null",
    "brand": "marca específica|null", 
    "category": "categoría|null",
    "model": "modelo específico|null"
  }},
  
  "filters": {{
    "price_range": {{"min": float|null, "max": float|null}},
    "characteristics": ["característica1", "característica2"],
    "availability_required": bool,
    "color": "color|null",
    "size": "tamaño|null"
  }},
  
  "query_complexity": "simple|medium|complex",
  "semantic_search_recommended": bool,
  "sql_generation_needed": bool,
  "user_emotion": "neutral|excited|frustrated|urgent|curious",
  "response_style_preference": "brief|detailed|technical|conversational"
}}

IMPORTANTE: 
- No uses reglas fijas, interpreta el lenguaje naturalmente
- Considera sinónimos y variaciones del español
- Detecta características implícitas (ej: "para gaming" implica alta performance)
- Si hay ambigüedad, favorece la interpretación más probable
"""

        try:
            response = await self.ollama.generate_response(
                system_prompt="Eres un experto analista de intenciones para e-commerce que interpreta consultas\
                    de productos en lenguaje natural.",
                user_prompt=intent_prompt,
                temperature=0.3,
            )

            # Intentar parsear como JSON
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                logger.warning("Could not parse intent analysis as JSON, using fallback")
                return self._create_fallback_intent(message)

        except Exception as e:
            logger.error(f"Error in intent analysis: {e}")
            return self._create_fallback_intent(message)

    def _create_fallback_intent(self, message: str) -> Dict[str, Any]:
        """Crea un análisis de intención básico como fallback."""
        words = message.lower().split()

        return {
            "intent_type": "search_general",
            "search_params": {"keywords": words, "product_name": None, "brand": None, "category": None, "model": None},
            "filters": {
                "price_range": {"min": None, "max": None},
                "characteristics": [],
                "availability_required": True,
                "color": None,
                "size": None,
            },
            "query_complexity": "simple",
            "semantic_search_recommended": True,
            "sql_generation_needed": False,
            "user_emotion": "neutral",
            "response_style_preference": "conversational",
        }

    async def _execute_intelligent_search(
        self, message: str, intent_analysis: Dict[str, Any], state_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ejecuta búsqueda inteligente usando múltiples estrategias.
        """

        print("Executing intelligent search using multiple strategies", state_dict)
        try:
            # Estrategia 1: Búsqueda semántica si está recomendada
            if intent_analysis.get("semantic_search_recommended", False) and self.enable_semantic_search:
                semantic_results = await self.search_tool.semantic_search(
                    query=message, intent=intent_analysis, limit=self.max_results
                )

                if semantic_results.get("success") and semantic_results.get("products"):
                    return {
                        "success": True,
                        "method": "semantic_search",
                        "products": semantic_results["products"],
                        "count": len(semantic_results["products"]),
                        "metadata": semantic_results.get("metadata", {}),
                    }

            # Estrategia 2: SQL dinámico si es necesario
            if intent_analysis.get("sql_generation_needed", False) and self.enable_dynamic_sql:
                sql_results = await self.sql_generator.generate_and_execute(
                    user_query=message, intent=intent_analysis, max_results=self.max_results
                )

                if sql_results.success and sql_results.data:
                    return {
                        "success": True,
                        "method": "dynamic_sql",
                        "products": sql_results.data,
                        "count": sql_results.row_count,
                        "metadata": {
                            "sql_query": sql_results.generated_sql,
                            "execution_time": sql_results.execution_time_ms,
                        },
                    }

            # Estrategia 3: Búsqueda tradicional estructurada
            structured_results = await self.search_tool.structured_search(
                intent=intent_analysis, limit=self.max_results
            )

            return {
                "success": structured_results.get("success", False),
                "method": "structured_search",
                "products": structured_results.get("products", []),
                "count": len(structured_results.get("products", [])),
                "metadata": structured_results.get("metadata", {}),
            }

        except Exception as e:
            logger.error(f"Error in intelligent search: {e}")
            return {"success": False, "method": "error", "products": [], "count": 0, "error": str(e)}

    async def _generate_intelligent_response(
        self,
        user_message: str,
        intent_analysis: Dict[str, Any],
        search_results: Dict[str, Any],
        _: Dict[str, Any],
    ) -> str:
        """
        Genera respuesta inteligente y contextual basada en los resultados.
        """
        products = search_results.get("products", [])
        count = search_results.get("count", 0)
        method = search_results.get("method", "unknown")

        # Preparar información de productos para la AI
        products_summary = self._prepare_products_for_ai(products[:5])  # Top 5 para contexto

        # Determinar estilo de respuesta basado en la intención
        response_style = intent_analysis.get("response_style_preference", "conversational")
        user_emotion = intent_analysis.get("user_emotion", "neutral")

        response_prompt = f"""# GENERACIÓN DE RESPUESTA INTELIGENTE

## CONSULTA ORIGINAL:
"{user_message}"

## ANÁLISIS DE INTENCIÓN:
- Tipo: {intent_analysis.get("intent_type", "search_general")}
- Emoción del usuario: {user_emotion}
- Estilo preferido: {response_style}
- Complejidad: {intent_analysis.get("query_complexity", "simple")}

## RESULTADOS ENCONTRADOS:
- Total de productos: {count}
- Método de búsqueda: {method}
- Productos principales:
{products_summary}

## INSTRUCCIONES:
1. Responde de manera {response_style} y adaptada a la emoción {user_emotion}
2. Destaca los productos más relevantes para la consulta
3. Incluye información clave como precios, disponibilidad y características
4. Si hay muchos resultados, agrupa por categorías o características
5. Sugiere próximos pasos útiles para el usuario
6. Usa emojis apropiados para WhatsApp pero sin exceso
7. Máximo 6 líneas de respuesta, sé conciso pero informativo

TONO: Amigable, profesional, orientado a la acción.
"""

        try:
            response = await self.ollama.generate_response(
                system_prompt="Eres un experto asistente de ventas de e-commerce que ayuda a clientes a encontrar\
                    productos perfectos.",
                user_prompt=response_prompt,
                temperature=0.7,
            )

            # Post-procesar la respuesta si es necesario
            processed_response = self._post_process_response(response, intent_analysis, products)

            return processed_response

        except Exception as e:
            logger.error(f"Error generating intelligent response: {e}")
            return self._generate_fallback_response(user_message, products, count)

    def _prepare_products_for_ai(self, products: List[Dict[str, Any]]) -> str:
        """Prepara información de productos para el contexto de AI."""
        if not products:
            return "No se encontraron productos."

        products_text = []
        for i, product in enumerate(products, 1):
            name = product.get("name", "Producto sin nombre")
            price = product.get("price", 0)
            stock = product.get("stock", 0)
            brand = product.get("brand", {}).get("name", "")
            category = product.get("category", {}).get("display_name", "")

            product_line = f"{i}. {name}"
            if brand:
                product_line += f" ({brand})"
            product_line += f" - ${price:,.2f}"

            if stock > 0:
                product_line += f" ✅ Stock: {stock}"
            else:
                product_line += " ❌ Sin stock"

            if category:
                product_line += f" | {category}"

            products_text.append(product_line)

        return "\n".join(products_text)

    def _post_process_response(
        self, response: str, intent_analysis: Dict[str, Any], products: List[Dict[str, Any]]
    ) -> str:
        """Post-procesa la respuesta para optimización final."""

        # Asegurar que no exceda límites de líneas
        lines = response.split("\n")
        if len(lines) > 6:
            response = "\n".join(lines[:6])

        # Agregar sugerencias si están habilitadas
        if self.include_suggestions and len(products) > 1:
            intent_type = intent_analysis.get("intent_type", "")

            if intent_type == "search_general" and len(products) > 3:
                response += "\n\n¿Te interesa alguno en particular? Puedo darte más detalles."
            elif intent_type == "comparison" and len(products) >= 2:
                response += "\n\n¿Quieres que compare algunos de estos productos?"

        return response.strip()

    async def _handle_no_results(self, message: str, intent_analysis: Dict[str, Any], _: Dict[str, Any]) -> str:
        """Maneja el caso cuando no se encuentran resultados."""

        no_results_prompt = f"""# NO HAY RESULTADOS

## CONSULTA:
"{message}"

## INTENCIÓN DETECTADA:
{json.dumps(intent_analysis, indent=2)}

## INSTRUCCIONES:
El usuario no obtuvo resultados para su búsqueda. Genera una respuesta que:

1. Sea empática y comprensiva
2. Ofrezca 2-3 alternativas específicas y útiles
3. Sugiera ampliar o modificar la búsqueda
4. Mantenga un tono positivo y servicial
5. Use máximo 4 líneas

Ejemplos de alternativas:
- Sugerir categorías relacionadas
- Proponer marcas similares
- Ofrecer productos con características parecidas
- Preguntar por más detalles específicos
"""

        try:
            response = await self.ollama.generate_response(
                system_prompt="Eres un asistente empático que ayuda cuando no hay resultados de búsqueda.",
                user_prompt=no_results_prompt,
                temperature=0.8,
            )

            return response.strip()

        except Exception as e:
            logger.error(f"Error generating no results response: {e}")
            return f"No encontré productos que coincidan con '{message}'. \
                ¿Podrías darme más detalles sobre lo que buscas? 🤔"

    async def _generate_error_response(self, message: str, _: str) -> str:
        """Genera respuesta amigable para errores."""

        error_responses = [
            "Disculpa, tuve un problema buscando productos. ¿Podrías intentar de nuevo?",
            "Hubo un pequeño inconveniente con la búsqueda. ¿Puedes reformular tu consulta?",
            "Mi sistema de búsqueda tuvo un contratiempo. ¿Intentamos con otras palabras?",
        ]

        try:
            # Usar AI para generar respuesta de error más contextual
            error_prompt = f"""El usuario buscó: "{message}"
            
Hubo un error técnico. Genera una respuesta breve y amigable que:
- Pida disculpas sin dar detalles técnicos
- Ofrezca intentar de nuevo
- Mantenga un tono positivo
- Máximo 2 líneas"""

            response = await self.ollama.generate_response(
                system_prompt="Eres un asistente que maneja errores de forma amigable.",
                user_prompt=error_prompt,
                temperature=0.5,
            )

            return response.strip()

        except Exception:
            # Fallback a respuesta predefinida
            import random

            return random.choice(error_responses)

    def _generate_fallback_response(self, message: str, products: List[Dict[str, Any]], count: int) -> str:
        """Genera respuesta de fallback sin AI."""

        if count == 0:
            return f"No encontré productos para '{message}'. ¿Podrías ser más específico?"
        elif count == 1:
            product = products[0]
            name = product.get("name", "Producto")
            price = product.get("price", 0)
            stock = product.get("stock", 0)

            response = f"Encontré: {name} - ${price:,.2f}"
            if stock > 0:
                response += f" ✅ ({stock} disponibles)"
            else:
                response += " ❌ Sin stock"

            return response
        else:
            return f"Encontré {count} productos que podrían interesarte. ¿Te muestro los detalles de alguno?"

    def _extract_user_id(self, state_dict: Dict[str, Any]) -> Optional[str]:
        """Extrae el ID del usuario del estado."""
        return state_dict.get("user_id") or state_dict.get("customer_id") or state_dict.get("phone_number")
