"""
System monitoring and health checking for LangGraph chatbot service
"""

import logging
from typing import Any, Dict

from app.core.graph import AynuxGraph
from app.core.schemas import AgentType
from app.services.langgraph.security_validator import SecurityValidator

logger = logging.getLogger(__name__)


class SystemMonitor:
    """Handles system health monitoring and conversation statistics"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.security_validator = SecurityValidator()

    async def get_conversation_history_langgraph(
        self, graph_system: AynuxGraph, user_number: str, limit: int = 50
    ) -> Dict[str, Any]:
        """
        Obtiene el historial de conversación para un usuario usando LangGraph

        Args:
            graph_system: Sistema de graph LangGraph
            user_number: Número de teléfono del usuario
            limit: Límite de mensajes a obtener

        Returns:
            Dict con el historial de conversación
        """
        try:
            if not graph_system or not graph_system.app:
                return {"error": "LangGraph system not initialized", "user_number": user_number, "messages": []}

            # Intentar obtener el estado de la conversación
            config = {"configurable": {"thread_id": user_number}}

            try:
                current_state = await graph_system.app.aget_state(config)

                if current_state and current_state.values:
                    messages = current_state.values.get("messages", [])

                    # Limitar los mensajes
                    limited_messages = messages[-limit:] if len(messages) > limit else messages

                    # Convertir mensajes a formato serializable
                    serialized_messages = []
                    for msg in limited_messages:
                        try:
                            if hasattr(msg, "content"):
                                serialized_messages.append(
                                    {
                                        "type": getattr(msg, "type", "unknown"),
                                        "content": msg.content,
                                        "timestamp": getattr(msg, "timestamp", None),
                                    }
                                )
                            else:
                                serialized_messages.append({"type": "unknown", "content": str(msg), "timestamp": None})
                        except Exception as e:
                            self.logger.warning(f"Error serializing message: {e}")
                            continue

                    return {
                        "user_number": user_number,
                        "messages": serialized_messages,
                        "total_messages": len(messages),
                        "limited_to": limit,
                        "conversation_state": {
                            "current_agent": current_state.values.get("current_agent"),
                            "is_complete": current_state.values.get("is_complete", False),
                            "requires_human": current_state.values.get("requires_human", False),
                        },
                    }
                else:
                    return {
                        "user_number": user_number,
                        "messages": [],
                        "total_messages": 0,
                        "note": "No conversation history found",
                    }

            except Exception as e:
                self.logger.warning(f"Could not retrieve conversation state: {e}")
                return {
                    "user_number": user_number,
                    "messages": [],
                    "total_messages": 0,
                    "error": f"Could not retrieve conversation: {str(e)}",
                }

        except Exception as e:
            self.logger.error(f"Error getting conversation history: {e}")
            return {
                "error": f"Error retrieving conversation history: {str(e)}",
                "user_number": user_number,
                "messages": [],
            }

    async def get_conversation_stats(self, graph_system: AynuxGraph, user_number: str) -> Dict[str, Any]:
        """
        Obtiene estadísticas de conversación para un usuario

        Args:
            graph_system: Sistema de graph LangGraph
            user_number: Número de teléfono del usuario

        Returns:
            Dict con estadísticas de la conversación
        """
        try:
            if not graph_system or not graph_system.app:
                return {"error": "LangGraph system not initialized", "user_number": user_number}

            config = {"configurable": {"thread_id": user_number}}

            try:
                current_state = await graph_system.app.aget_state(config)

                if current_state and current_state.values:
                    state_values = current_state.values
                    messages = state_values.get("messages", [])

                    # Contar tipos de mensajes
                    human_messages = len([m for m in messages if hasattr(m, "type") and m.type == "human"])
                    ai_messages = len([m for m in messages if hasattr(m, "type") and m.type == "ai"])

                    # Obtener agentes utilizados
                    agent_history = state_values.get("agent_history", [])

                    return {
                        "user_number": user_number,
                        "total_messages": len(messages),
                        "human_messages": human_messages,
                        "ai_messages": ai_messages,
                        "current_agent": state_values.get("current_agent"),
                        "agents_used": list(set(agent_history)) if agent_history else [],
                        "agents_used_count": len(set(agent_history)) if agent_history else 0,
                        "is_complete": state_values.get("is_complete", False),
                        "requires_human": state_values.get("requires_human", False),
                        "error_count": state_values.get("error_count", 0),
                        "conversation_active": len(messages) > 0,
                        "last_intent": (
                            state_values.get("current_intent", {}).get("primary_intent")
                            if state_values.get("current_intent")
                            else None
                        ),
                    }
                else:
                    return {
                        "user_number": user_number,
                        "total_messages": 0,
                        "conversation_active": False,
                        "note": "No conversation found",
                    }

            except Exception as e:
                self.logger.warning(f"Could not retrieve conversation state for stats: {e}")
                return {
                    "user_number": user_number,
                    "error": f"Could not retrieve stats: {str(e)}",
                    "conversation_active": False,
                }

        except Exception as e:
            self.logger.error(f"Error getting conversation stats: {e}")
            return {"error": f"Error retrieving conversation stats: {str(e)}", "user_number": user_number}

    async def get_system_health(self, initialized: bool, graph_system: AynuxGraph) -> Dict[str, Any]:
        """
        Obtiene el estado de salud del sistema LangGraph.

        Args:
            initialized: Si el servicio está inicializado
            graph_system: Sistema de graph LangGraph

        Returns:
            Diccionario con información del estado de salud
        """
        try:
            components: Dict[str, Any] = {}

            # Check integrations
            if graph_system:
                components["ollama"] = hasattr(graph_system, "ollama") and graph_system.ollama is not None
                components["postgres"] = hasattr(graph_system, "postgres") and graph_system.postgres is not None
                components["supervisor_agent"] = graph_system.agents.get(AgentType.SUPERVISOR.value) is not None

            health_status: Dict[str, Any] = {
                "service": "langgraph_chatbot",
                "initialized": initialized,
                "graph_system": graph_system is not None,
                "components": components,
            }

            # Check database health
            health_status["database"] = await self.security_validator.check_database_health()

            # Overall status
            if initialized and graph_system and health_status["database"]:
                health_status["overall_status"] = "healthy"
            elif initialized and graph_system:
                health_status["overall_status"] = "degraded"
            else:
                health_status["overall_status"] = "unhealthy"

            return health_status

        except Exception as e:
            self.logger.error(f"Error checking system health: {e}")
            return {"service": "langgraph_chatbot", "overall_status": "unhealthy", "error": str(e)}
