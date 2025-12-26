"""
Data Insights Agent - Agente especializado en consultas dinamicas de datos.

Este agente puede:
1. Entender intenciones de consultas de datos del usuario
2. Generar consultas SQL dinamicamente usando AI
3. Ejecutar consultas de forma segura
4. Convertir resultados en embeddings para contexto
5. Proporcionar respuestas inteligentes basadas en datos
"""

import json
import logging
from typing import Any

from app.core.agents import BaseAgent
from app.core.tools import DynamicSQLTool, SQLExecutionResult
from app.core.utils.tracing import trace_async_method
from app.integrations.llm import OllamaLLM
from app.integrations.llm.model_provider import ModelComplexity
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)


class DataInsightsAgent(BaseAgent):
    """
    Agente especializado en analisis dinamico de datos usando SQL generado por AI.

    Capacidades:
    - Procesamiento de consultas en lenguaje natural
    - Generacion automatica de SQL usando AI
    - Ejecucion segura de consultas
    - Generacion de embeddings contextuales
    - Respuestas inteligentes basadas en datos reales
    """

    def __init__(self, ollama=None, postgres=None, config: dict[str, Any] | None = None):
        super().__init__("data_insights_agent", config or {}, ollama=ollama, postgres=postgres)

        # Configuracion especifica del agente
        self.max_query_results = self.config.get("max_query_results", 100)
        self.enable_caching = self.config.get("enable_caching", True)
        self.safe_mode = self.config.get("safe_mode", True)
        self.include_embeddings = self.config.get("include_embeddings", True)

        # Inicializar herramientas
        self.ollama = ollama or OllamaLLM()
        self.sql_tool = DynamicSQLTool(self.ollama)

        # Initialize PromptManager for YAML-based prompts
        self.prompt_manager = PromptManager()

        # Patrones de consultas que puede manejar
        self.supported_patterns = {
            "analytics": ["cuantos", "cuantas", "total", "suma", "promedio", "estadisticas"],
            "search": ["muestra", "busca", "encuentra", "lista", "que", "cual"],
            "comparison": ["mejor", "peor", "mayor", "menor", "comparar", "vs"],
            "trends": ["tendencia", "ultimos", "semana", "mes", "ano", "crecimiento"],
            "user_specific": ["mis", "mi", "personal", "propio", "historial"],
        }

    @trace_async_method(
        name="data_insights_agent_process",
        run_type="chain",
        metadata={"agent_type": "data_insights", "sql_generation": "ai_powered"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Procesa consultas de datos usando AI dinamico.

        Args:
            message: Mensaje del usuario
            state_dict: Estado actual como diccionario

        Returns:
            Diccionario con actualizaciones para el estado
        """
        try:
            # 1. Verificar si la consulta es adecuada para este agente
            is_data_query = await self._is_data_query(message)
            if not is_data_query:
                return await self._redirect_to_appropriate_agent(message, state_dict)

            # 2. Obtener contexto del usuario
            user_id = self._extract_user_id(state_dict)

            # 3. Ejecutar consulta SQL dinamica
            sql_result = await self._execute_dynamic_query(message, user_id, state_dict)

            # 5. Generar respuesta inteligente basada en resultados
            if sql_result.success:
                ai_response = await self._generate_intelligent_response(message, sql_result, user_id, state_dict)
            else:
                ai_response = await self._handle_query_error(message, sql_result)

            return {
                "messages": [{"role": "assistant", "content": ai_response}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "retrieved_data": {
                    "sql_query": sql_result.generated_sql,
                    "row_count": sql_result.row_count,
                    "execution_time": sql_result.execution_time_ms,
                    "data_summary": sql_result.embedding_context,
                },
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in data insights agent: {str(e)}")
            error_response = await self._generate_error_response(message, str(e))

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    async def _is_data_query(self, message: str) -> bool:
        """Determina si la consulta es apropiada para analisis de datos usando YAML prompt."""
        try:
            # Load prompt from YAML
            analysis_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.AGENTS_DATA_INSIGHTS_CLASSIFICATION,
                variables={"message": message},
            )

            # Load system prompt from YAML
            system_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.AGENTS_DATA_INSIGHTS_SYSTEM_CLASSIFIER,
            )

            response = await self.ollama.generate_response(
                system_prompt=system_prompt,
                user_prompt=analysis_prompt,
                complexity=ModelComplexity.SIMPLE,
                temperature=0.1,
            )

            response_clean = response.strip().upper().replace(".", "").replace("I", "I")
            return response_clean in ["SI", "SI", "YES", "Y"]

        except Exception as e:
            logger.warning(f"Error classifying query: {e}")
            # Fallback: usar patrones de palabras clave
            return self._fallback_query_classification(message)

    def _fallback_query_classification(self, message: str) -> bool:
        """Clasificacion de respaldo usando patrones de palabras clave."""
        message_lower = message.lower()

        # Palabras clave que indican consultas de datos
        data_keywords = [
            "cuantos",
            "cuantas",
            "total",
            "suma",
            "promedio",
            "estadisticas",
            "muestra",
            "lista",
            "encuentra",
            "busca",
            "datos",
            "informacion",
            "ultimos",
            "semana",
            "mes",
            "ano",
            "historial",
            "tendencia",
            "mayor",
            "menor",
            "mejor",
            "peor",
            "top",
            "ranking",
        ]

        return any(keyword in message_lower for keyword in data_keywords)

    async def _execute_dynamic_query(
        self, message: str, user_id: str | None, state_dict: dict[str, Any]
    ) -> SQLExecutionResult:
        """Ejecuta consulta SQL dinamica basada en el mensaje del usuario."""

        try:
            # Determinar restricciones de tabla basadas en el contexto
            table_constraints = self._infer_table_constraints(message, state_dict)

            # Ejecutar la herramienta SQL dinamica
            result = await self.sql_tool(
                user_query=message,
                user_id=user_id,
                table_constraints=table_constraints,
                max_results=self.max_query_results,
            )

            logger.info(f"Dynamic SQL executed successfully: {result.row_count} rows returned")
            return result

        except Exception as e:
            logger.error(f"Error executing dynamic query: {e}")
            return SQLExecutionResult(success=False, error_message=str(e), generated_sql="", execution_time_ms=0.0)

    def _infer_table_constraints(self, message: str, state_dict: dict[str, Any]) -> list[str] | None:
        """Infiere que tablas son relevantes basandose en el mensaje."""

        message_lower = message.lower()
        constraints = []

        # Mapear palabras clave a tablas
        logger.debug(f"infer table constraints: {state_dict}")
        table_keywords = {
            "orders": ["pedidos", "ordenes", "compras", "ventas", "transacciones"],
            "products": ["productos", "articulos", "items", "catalogo"],
            "customers": ["clientes", "usuarios", "compradores"],
            "categories": ["categorias", "secciones", "tipos"],
            "conversations": ["conversaciones", "mensajes", "chat", "historial"],
        }

        for table, keywords in table_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                constraints.append(table)

        # Si no hay restricciones especificas, permitir todas las tablas principales
        if not constraints:
            constraints = ["orders", "products", "customers"]

        return constraints

    async def _generate_intelligent_response(
        self, user_query: str, sql_result: SQLExecutionResult, user_id: str | None, state_dict: dict[str, Any]
    ) -> str:
        """Genera respuesta inteligente basada en los resultados de la consulta usando YAML."""

        logger.debug(f"Genera respuesta inteligente: user_id={user_id}, state={state_dict}")

        if sql_result.row_count == 0:
            return await self._generate_no_results_response(user_query, sql_result)

        # Preparar contexto para la respuesta
        sample_data = sql_result.data[:5] if sql_result.data else []

        try:
            # Load prompt from YAML
            response_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.AGENTS_DATA_INSIGHTS_RESPONSE,
                variables={
                    "user_query": user_query,
                    "row_count": sql_result.row_count,
                    "execution_time": f"{sql_result.execution_time_ms:.2f}",
                    "generated_sql": sql_result.generated_sql,
                    "embedding_context": sql_result.embedding_context or "Datos disponibles",
                    "sample_data": json.dumps(sample_data, indent=2, default=str),
                },
            )

            # Load system prompt from YAML
            system_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.AGENTS_DATA_INSIGHTS_SYSTEM_ANALYST,
            )

            response = await self.ollama.generate_response(
                system_prompt=system_prompt,
                user_prompt=response_prompt,
                complexity=ModelComplexity.COMPLEX,
                temperature=0.6,
            )

            return response.strip()

        except Exception as e:
            logger.error(f"Error generating intelligent response: {e}")
            return self._generate_fallback_response(user_query, sql_result)

    async def _generate_no_results_response(self, user_query: str, sql_result: SQLExecutionResult) -> str:
        """Genera respuesta cuando no hay resultados usando YAML."""
        logger.debug(f"sql_result: {sql_result}")

        try:
            # Load prompt from YAML
            no_results_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.AGENTS_DATA_INSIGHTS_NO_RESULTS,
                variables={"user_query": user_query},
            )

            # Load system prompt from YAML
            system_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.AGENTS_DATA_INSIGHTS_SYSTEM_NO_RESULTS,
            )

            response = await self.ollama.generate_response(
                system_prompt=system_prompt,
                user_prompt=no_results_prompt,
                complexity=ModelComplexity.SIMPLE,
                temperature=0.7,
            )

            return response.strip()

        except Exception as e:
            logger.error(f"Error generating no results response: {e}")
            return f"No encontre resultados para '{user_query}'. Te gustaria intentar con una consulta diferente?"

    async def _handle_query_error(self, user_query: str, sql_result: SQLExecutionResult) -> str:
        """Maneja errores en la ejecucion de consultas usando YAML."""
        try:
            # Load prompt from YAML
            error_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.AGENTS_DATA_INSIGHTS_ERROR,
                variables={
                    "user_query": user_query,
                    "error_message": sql_result.error_message or "Error desconocido",
                },
            )

            # Load system prompt from YAML
            system_prompt = await self.prompt_manager.get_prompt(
                PromptRegistry.AGENTS_DATA_INSIGHTS_SYSTEM_ERROR_HANDLER,
            )

            response = await self.ollama.generate_response(
                system_prompt=system_prompt,
                user_prompt=error_prompt,
                complexity=ModelComplexity.SIMPLE,
                temperature=0.5,
            )

            return response.strip()

        except Exception as e:
            logger.error(f"Error generating error response: {e}")
            return "Tuve un problema procesando tu consulta. Podrias reformularla de otra manera?"

    async def _redirect_to_appropriate_agent(self, message: str, _: dict[str, Any]) -> dict[str, Any]:
        """Redirige a un agente mas apropiado si la consulta no es de datos."""

        redirect_response = (
            "Esta consulta parece ser mas adecuada para otro tipo de asistencia. Te voy a derivar al agente apropiado."
            + message
        )

        return {
            "messages": [{"role": "assistant", "content": redirect_response}],
            "current_agent": "fallback_agent",  # Redirigir al agente de fallback
            "agent_history": [self.name],
            "requires_handoff": True,
            "is_complete": False,
        }

    def _extract_user_id(self, state_dict: dict[str, Any]) -> str | None:
        """Extrae el ID del usuario del estado."""

        # Intentar diferentes formas de obtener el user_id
        user_contexts = [
            state_dict.get("customer", {}).get("phone_number"),
            state_dict.get("user_phone"),
            state_dict.get("conversation", {}).get("user_id"),
            state_dict.get("session_id", "").replace("whatsapp_", "") if state_dict.get("session_id") else None,
        ]

        for user_id in user_contexts:
            if user_id:
                return str(user_id)

        return None

    def _generate_fallback_response(self, user_query: str, sql_result: SQLExecutionResult) -> str:
        """Genera respuesta de respaldo cuando falla la generacion de IA."""

        if sql_result.row_count == 0:
            return f"No encontre resultados para tu consulta: '{user_query}'"

        summary = f"Encontre {sql_result.row_count} resultado(s) para tu consulta."

        if sql_result.data:
            # Mostrar algunos datos de ejemplo
            sample = sql_result.data[0]
            if isinstance(sample, dict) and sample:
                key_info = ", ".join([f"{k}: {v}" for k, v in list(sample.items())[:3]])
                summary += f" Ejemplo: {key_info}"

        return summary

    async def _generate_error_response(self, message: str, error: str) -> str:
        """Genera respuesta de error amigable."""

        logger.debug(f"message: {message}, error: {error}")

        return "Disculpa, tuve un problema procesando tu consulta de datos. Podrias intentar reformularla?"
