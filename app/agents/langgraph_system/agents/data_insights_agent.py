"""
Data Insights Agent - Agente especializado en consultas dinámicas de datos.

Este agente puede:
1. Entender intenciones de consultas de datos del usuario
2. Generar consultas SQL dinámicamente usando AI
3. Ejecutar consultas de forma segura
4. Convertir resultados en embeddings para contexto
5. Proporcionar respuestas inteligentes basadas en datos
"""

import json
import logging
from typing import Any, Dict, List, Optional

from ..integrations.ollama_integration import OllamaIntegration
from ..integrations.ai_data_integration import AgentDataContext
from ..tools.dynamic_sql_tool import DynamicSQLTool, SQLExecutionResult
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class DataInsightsAgent(BaseAgent):
    """
    Agente especializado en análisis dinámico de datos usando SQL generado por AI.
    
    Capacidades:
    - Procesamiento de consultas en lenguaje natural
    - Generación automática de SQL usando AI
    - Ejecución segura de consultas
    - Generación de embeddings contextuales
    - Respuestas inteligentes basadas en datos reales
    """

    def __init__(self, ollama=None, postgres=None, config: Optional[Dict[str, Any]] = None):
        super().__init__("data_insights_agent", config or {}, ollama=ollama, postgres=postgres)
        
        # Configuración específica del agente
        self.max_query_results = self.config.get("max_query_results", 100)
        self.enable_caching = self.config.get("enable_caching", True)
        self.safe_mode = self.config.get("safe_mode", True)
        self.include_embeddings = self.config.get("include_embeddings", True)
        
        # Inicializar herramientas
        self.ollama = ollama or OllamaIntegration()
        self.sql_tool = DynamicSQLTool(self.ollama)
        self.data_context = AgentDataContext()
        
        # Patrones de consultas que puede manejar
        self.supported_patterns = {
            "analytics": ["cuántos", "cuántas", "total", "suma", "promedio", "estadísticas"],
            "search": ["muestra", "busca", "encuentra", "lista", "qué", "cuál"],
            "comparison": ["mejor", "peor", "mayor", "menor", "comparar", "vs"],
            "trends": ["tendencia", "últimos", "semana", "mes", "año", "crecimiento"],
            "user_specific": ["mis", "mi", "personal", "propio", "historial"]
        }

    async def _process_internal(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa consultas de datos usando AI dinámico.

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
            
            # 3. Asegurar que los datos del usuario estén disponibles
            if user_id and self.include_embeddings:
                await self.data_context.ensure_user_data_ready(user_id)

            # 4. Ejecutar consulta SQL dinámica
            sql_result = await self._execute_dynamic_query(message, user_id, state_dict)

            # 5. Generar respuesta inteligente basada en resultados
            if sql_result.success:
                ai_response = await self._generate_intelligent_response(
                    message, sql_result, user_id, state_dict
                )
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
                    "data_summary": sql_result.embedding_context
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
        """Determina si la consulta es apropiada para análisis de datos."""
        
        analysis_prompt = f"""# CLASIFICACIÓN DE CONSULTA

MENSAJE: "{message}"

¿Esta consulta requiere análisis de datos, estadísticas, búsquedas en base de datos o información histórica?

Ejemplos de consultas de datos:
- "¿Cuántos pedidos se hicieron esta semana?"
- "¿Cuántos productos tenemos en total?"
- "Muestra mis últimas compras"
- "¿Cuál es el producto más vendido?"
- "Estadísticas de ventas del mes pasado"
- "Total de clientes registrados"
- "Productos con más stock"

Ejemplos de consultas NO de datos:
- "Hola, ¿cómo estás?"
- "Ayúdame con mi factura"
- "Tengo un problema técnico"

IMPORTANTE: Si la consulta contiene palabras como "cuántos", "total", "estadísticas", "últimos", "más", es probable que sea una consulta de datos.

Responde EXACTAMENTE: "SI" o "NO"
"""

        try:
            response = await self.ollama.generate_response(
                system_prompt="Eres un clasificador de consultas que determina si requieren análisis de datos.",
                user_prompt=analysis_prompt,
                temperature=0.1
            )
            
            response_clean = response.strip().upper().replace(".", "").replace("Í", "I")
            return response_clean in ["SI", "SÍ", "YES", "Y"]
            
        except Exception as e:
            logger.warning(f"Error classifying query: {e}")
            # Fallback: usar patrones de palabras clave
            return self._fallback_query_classification(message)

    def _fallback_query_classification(self, message: str) -> bool:
        """Clasificación de respaldo usando patrones de palabras clave."""
        message_lower = message.lower()
        
        # Palabras clave que indican consultas de datos
        data_keywords = [
            "cuántos", "cuántas", "total", "suma", "promedio", "estadísticas",
            "muestra", "lista", "encuentra", "busca", "datos", "información",
            "últimos", "semana", "mes", "año", "historial", "tendencia",
            "mayor", "menor", "mejor", "peor", "top", "ranking"
        ]
        
        return any(keyword in message_lower for keyword in data_keywords)

    async def _execute_dynamic_query(
        self, message: str, user_id: Optional[str], state_dict: Dict[str, Any]
    ) -> SQLExecutionResult:
        """Ejecuta consulta SQL dinámica basada en el mensaje del usuario."""
        
        try:
            # Determinar restricciones de tabla basadas en el contexto
            table_constraints = self._infer_table_constraints(message, state_dict)
            
            # Ejecutar la herramienta SQL dinámica
            result = await self.sql_tool(
                user_query=message,
                user_id=user_id,
                table_constraints=table_constraints,
                max_results=self.max_query_results
            )
            
            logger.info(f"Dynamic SQL executed successfully: {result.row_count} rows returned")
            return result
            
        except Exception as e:
            logger.error(f"Error executing dynamic query: {e}")
            return SQLExecutionResult(
                success=False,
                error_message=str(e),
                generated_sql="",
                execution_time_ms=0.0
            )

    def _infer_table_constraints(self, message: str, state_dict: Dict[str, Any]) -> Optional[List[str]]:
        """Infiere qué tablas son relevantes basándose en el mensaje."""
        
        message_lower = message.lower()
        constraints = []
        
        # Mapear palabras clave a tablas
        table_keywords = {
            "orders": ["pedidos", "órdenes", "compras", "ventas", "transacciones"],
            "products": ["productos", "artículos", "items", "catálogo"],
            "customers": ["clientes", "usuarios", "compradores"],
            "categories": ["categorías", "secciones", "tipos"],
            "conversations": ["conversaciones", "mensajes", "chat", "historial"]
        }
        
        for table, keywords in table_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                constraints.append(table)
        
        # Si no hay restricciones específicas, permitir todas las tablas principales
        if not constraints:
            constraints = ["orders", "products", "customers"]
        
        return constraints

    async def _generate_intelligent_response(
        self,
        user_query: str,
        sql_result: SQLExecutionResult,
        user_id: Optional[str],
        state_dict: Dict[str, Any]
    ) -> str:
        """Genera respuesta inteligente basada en los resultados de la consulta."""
        
        if sql_result.row_count == 0:
            return await self._generate_no_results_response(user_query, sql_result)

        # Preparar contexto para la respuesta
        context_data = {
            "user_query": user_query,
            "row_count": sql_result.row_count,
            "execution_time": sql_result.execution_time_ms,
            "data_summary": sql_result.embedding_context,
            "sample_data": sql_result.data[:5] if sql_result.data else []
        }

        response_prompt = f"""# GENERACIÓN DE RESPUESTA INTELIGENTE

## CONSULTA DEL USUARIO:
"{user_query}"

## RESULTADOS DE LA CONSULTA:
- Registros encontrados: {sql_result.row_count}
- Tiempo de ejecución: {sql_result.execution_time_ms:.2f}ms
- SQL ejecutado: {sql_result.generated_sql}

## CONTEXTO DE DATOS:
{sql_result.embedding_context or "Datos disponibles"}

## MUESTRA DE DATOS:
{json.dumps(context_data["sample_data"], indent=2, default=str)}

## INSTRUCCIONES:
1. Responde de manera directa y útil a la pregunta del usuario
2. Incluye números específicos y datos relevantes
3. Proporciona insights adicionales cuando sea apropiado
4. Usa un tono conversacional y amigable
5. Si hay muchos resultados, resume los más importantes
6. Incluye sugerencias de seguimiento si es útil

Máximo 6 líneas de respuesta:
"""

        try:
            response = await self.ollama.generate_response(
                system_prompt="Eres un analista de datos experto que proporciona insights claros basados en consultas de base de datos.",
                user_prompt=response_prompt,
                temperature=0.6
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Error generating intelligent response: {e}")
            return self._generate_fallback_response(user_query, sql_result)

    async def _generate_no_results_response(
        self, user_query: str, sql_result: SQLExecutionResult
    ) -> str:
        """Genera respuesta cuando no hay resultados."""
        
        no_results_prompt = f"""La consulta "{user_query}" no arrojó resultados.

Genera una respuesta empática que:
1. Confirme que no se encontraron datos
2. Sugiera posibles alternativas o consultas relacionadas
3. Ofrezca ayuda adicional

Máximo 3 líneas:"""

        try:
            response = await self.ollama.generate_response(
                system_prompt="Eres un asistente útil que maneja consultas sin resultados de manera empática.",
                user_prompt=no_results_prompt,
                temperature=0.7
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Error generating no results response: {e}")
            return f"No encontré resultados para '{user_query}'. ¿Te gustaría intentar con una consulta diferente?"

    async def _handle_query_error(self, user_query: str, sql_result: SQLExecutionResult) -> str:
        """Maneja errores en la ejecución de consultas."""
        
        error_prompt = f"""La consulta "{user_query}" encontró un error: {sql_result.error_message}

Genera una respuesta que:
1. Explique que hubo un problema técnico (sin detalles técnicos)
2. Sugiera reformular la pregunta
3. Ofrezca ayuda alternativa

Máximo 2 líneas, tono amigable:"""

        try:
            response = await self.ollama.generate_response(
                system_prompt="Eres un asistente que maneja errores técnicos de manera amigable y útil.",
                user_prompt=error_prompt,
                temperature=0.5
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Error generating error response: {e}")
            return "Tuve un problema procesando tu consulta. ¿Podrías reformularla de otra manera?"

    async def _redirect_to_appropriate_agent(
        self, message: str, state_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Redirige a un agente más apropiado si la consulta no es de datos."""
        
        redirect_response = "Esta consulta parece ser más adecuada para otro tipo de asistencia. Te voy a derivar al agente apropiado."
        
        return {
            "messages": [{"role": "assistant", "content": redirect_response}],
            "current_agent": "fallback_agent",  # Redirigir al agente de fallback
            "agent_history": [self.name],
            "requires_handoff": True,
            "is_complete": False,
        }

    def _extract_user_id(self, state_dict: Dict[str, Any]) -> Optional[str]:
        """Extrae el ID del usuario del estado."""
        
        # Intentar diferentes formas de obtener el user_id
        user_contexts = [
            state_dict.get("customer", {}).get("phone_number"),
            state_dict.get("user_phone"),
            state_dict.get("conversation", {}).get("user_id"),
            state_dict.get("session_id", "").replace("whatsapp_", "") if state_dict.get("session_id") else None
        ]
        
        for user_id in user_contexts:
            if user_id:
                return str(user_id)
        
        return None

    def _generate_fallback_response(self, user_query: str, sql_result: SQLExecutionResult) -> str:
        """Genera respuesta de respaldo cuando falla la generación de IA."""
        
        if sql_result.row_count == 0:
            return f"No encontré resultados para tu consulta: '{user_query}'"
        
        summary = f"Encontré {sql_result.row_count} resultado(s) para tu consulta."
        
        if sql_result.data:
            # Mostrar algunos datos de ejemplo
            sample = sql_result.data[0]
            if isinstance(sample, dict) and sample:
                key_info = ", ".join([f"{k}: {v}" for k, v in list(sample.items())[:3]])
                summary += f" Ejemplo: {key_info}"
        
        return summary

    async def _generate_error_response(self, message: str, error: str) -> str:
        """Genera respuesta de error amigable."""
        
        return "Disculpa, tuve un problema procesando tu consulta de datos. ¿Podrías intentar reformularla?"