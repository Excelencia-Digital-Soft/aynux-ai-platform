"""
Gestor optimizado para agentes de WhatsApp con lazy loading y gestión inteligente de memoria
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Callable, Any
from contextlib import asynccontextmanager

from app.agents.langgraph_system.react_agents import ReactAgentManager
from app.agents.langgraph_system.integrations.ollama_integration import OllamaIntegration

logger = logging.getLogger(__name__)


class OptimizedWhatsAppAgentManager:
    """
    Gestor optimizado para agentes de WhatsApp con lazy loading.
    
    Características:
    - Carga diferida de agentes (solo cuando se necesitan)
    - Liberación automática de agentes inactivos
    - Gestión inteligente de memoria
    - Métricas de uso y performance
    """

    def __init__(self, max_idle_time: int = 300, cleanup_interval: int = 60, ollama_integration: Optional[OllamaIntegration] = None):
        self._agents: Dict[str, Optional[Any]] = {}
        self._agent_factories: Dict[str, Callable] = {}
        self._last_used: Dict[str, float] = {}
        self._agent_stats: Dict[str, Dict[str, Any]] = {}
        
        self.max_idle_time = max_idle_time  # 5 minutos por defecto
        self.cleanup_interval = cleanup_interval  # 1 minuto por defecto
        
        # Integración con ReAct agents
        self.ollama_integration = ollama_integration
        self._react_manager: Optional[ReactAgentManager] = None
        
        # Iniciar limpieza automática
        self._cleanup_task = None
        self._start_cleanup_worker()
        
        logger.info(f"OptimizedWhatsAppAgentManager initialized - max_idle: {max_idle_time}s, cleanup: {cleanup_interval}s")

    def register_agent_factory(self, agent_type: str, factory: Callable):
        """
        Registrar factory para creación on-demand de agentes.
        
        Args:
            agent_type: Tipo de agente (product_agent, support_agent, etc.)
            factory: Función async que retorna el agente inicializado
        """
        logger.info(f"Registering agent factory for: {agent_type}")
        self._agent_factories[agent_type] = factory
        self._agents[agent_type] = None
        self._agent_stats[agent_type] = {
            "created_count": 0,
            "usage_count": 0,
            "total_response_time": 0.0,
            "last_created": None,
            "avg_response_time": 0.0
        }

    async def get_agent(self, agent_type: str, user_id: str = None) -> Any:
        """
        Obtener agente con carga diferida y gestión de contexto de usuario.
        
        Args:
            agent_type: Tipo de agente solicitado
            user_id: ID del usuario (para métricas y logging)
            
        Returns:
            Instancia del agente solicitado
        """
        if agent_type not in self._agent_factories:
            raise ValueError(f"Agent type '{agent_type}' not registered")

        # Crear agente si no existe
        if self._agents[agent_type] is None:
            logger.info(f"Lazy loading agent '{agent_type}' for user {user_id}")
            start_time = time.time()
            
            try:
                self._agents[agent_type] = await self._agent_factories[agent_type]()
                creation_time = time.time() - start_time
                
                # Actualizar estadísticas
                stats = self._agent_stats[agent_type]
                stats["created_count"] += 1
                stats["last_created"] = time.time()
                
                logger.info(f"Agent '{agent_type}' created successfully in {creation_time:.3f}s")
                
            except Exception as e:
                logger.error(f"Failed to create agent '{agent_type}': {e}")
                raise

        # Actualizar tiempo de último uso
        self._last_used[agent_type] = time.time()
        self._agent_stats[agent_type]["usage_count"] += 1
        
        return self._agents[agent_type]

    @asynccontextmanager
    async def use_agent(self, agent_type: str, user_id: str = None):
        """
        Context manager para uso de agentes con métricas automáticas.
        
        Args:
            agent_type: Tipo de agente
            user_id: ID del usuario
            
        Yields:
            Instancia del agente
        """
        start_time = time.time()
        agent = await self.get_agent(agent_type, user_id)
        
        try:
            yield agent
        finally:
            # Registrar tiempo de uso
            response_time = time.time() - start_time
            stats = self._agent_stats[agent_type]
            stats["total_response_time"] += response_time
            stats["avg_response_time"] = stats["total_response_time"] / stats["usage_count"]

    async def cleanup_idle_agents(self):
        """Limpieza automática de agentes inactivos"""
        current_time = time.time()
        cleaned_agents = []

        for agent_type, last_used in list(self._last_used.items()):
            if current_time - last_used > self.max_idle_time:
                if self._agents[agent_type] is not None:
                    logger.info(f"Cleaning up idle agent: {agent_type} (idle for {current_time - last_used:.1f}s)")
                    
                    # Intentar cerrar el agente si tiene método cleanup
                    try:
                        agent = self._agents[agent_type]
                        if hasattr(agent, 'cleanup'):
                            await agent.cleanup()
                    except Exception as e:
                        logger.warning(f"Error during agent cleanup for {agent_type}: {e}")
                    
                    # Remover referencias
                    self._agents[agent_type] = None
                    del self._last_used[agent_type]
                    cleaned_agents.append(agent_type)

        if cleaned_agents:
            logger.info(f"Cleaned up {len(cleaned_agents)} idle agents: {cleaned_agents}")
            
        return len(cleaned_agents)

    def _start_cleanup_worker(self):
        """Iniciar worker de limpieza automática"""
        async def cleanup_worker():
            while True:
                try:
                    await asyncio.sleep(self.cleanup_interval)
                    await self.cleanup_idle_agents()
                except Exception as e:
                    logger.error(f"Error in cleanup worker: {e}")

        self._cleanup_task = asyncio.create_task(cleanup_worker())
        logger.info("Cleanup worker started")

    async def reload_agent(self, agent_type: str):
        """
        Recargar un agente específico (útil para hot-reload en desarrollo).
        
        Args:
            agent_type: Tipo de agente a recargar
        """
        if agent_type not in self._agent_factories:
            raise ValueError(f"Agent type '{agent_type}' not registered")

        logger.info(f"Reloading agent: {agent_type}")
        
        # Limpiar agente actual
        if self._agents[agent_type] is not None:
            try:
                agent = self._agents[agent_type]
                if hasattr(agent, 'cleanup'):
                    await agent.cleanup()
            except Exception as e:
                logger.warning(f"Error during agent cleanup for reload: {e}")
            
            self._agents[agent_type] = None

        # Remover de last_used para forzar recreación
        if agent_type in self._last_used:
            del self._last_used[agent_type]

        # Reset stats de creación
        self._agent_stats[agent_type]["created_count"] = 0
        
        logger.info(f"Agent '{agent_type}' marked for reload")

    def get_agent_stats(self) -> Dict[str, Dict[str, Any]]:
        """Obtener estadísticas de uso de agentes"""
        current_time = time.time()
        stats = {}
        
        for agent_type, agent_stats in self._agent_stats.items():
            is_loaded = self._agents[agent_type] is not None
            last_used = self._last_used.get(agent_type)
            
            stats[agent_type] = {
                **agent_stats,
                "is_loaded": is_loaded,
                "last_used": last_used,
                "idle_time": (current_time - last_used) if last_used else None,
                "memory_status": "active" if is_loaded else "unloaded"
            }
            
        return stats

    def get_system_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas generales del sistema"""
        agent_stats = self.get_agent_stats()
        
        total_agents = len(self._agent_factories)
        loaded_agents = sum(1 for stats in agent_stats.values() if stats["is_loaded"])
        total_usage = sum(stats["usage_count"] for stats in agent_stats.values())
        avg_response_time = sum(
            stats["avg_response_time"] * stats["usage_count"] 
            for stats in agent_stats.values() if stats["usage_count"] > 0
        ) / max(total_usage, 1)
        
        return {
            "total_registered_agents": total_agents,
            "currently_loaded_agents": loaded_agents,
            "memory_efficiency": f"{((total_agents - loaded_agents) / total_agents * 100):.1f}%",
            "total_usage_count": total_usage,
            "average_response_time": avg_response_time,
            "cleanup_interval": self.cleanup_interval,
            "max_idle_time": self.max_idle_time
        }

    async def shutdown(self):
        """Cerrar el manager y limpiar todos los recursos"""
        logger.info("Shutting down OptimizedWhatsAppAgentManager...")
        
        # Cancelar worker de limpieza
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Limpiar todos los agentes
        for agent_type, agent in self._agents.items():
            if agent is not None:
                try:
                    if hasattr(agent, 'cleanup'):
                        await agent.cleanup()
                except Exception as e:
                    logger.warning(f"Error cleaning up agent {agent_type}: {e}")

        # Limpiar referencias
        self._agents.clear()
        self._last_used.clear()
        
        logger.info("OptimizedWhatsAppAgentManager shutdown complete")

    async def get_react_manager(self) -> ReactAgentManager:
        """Obtiene el manager de agentes ReAct con lazy loading"""
        if self._react_manager is None:
            if self.ollama_integration is None:
                self.ollama_integration = OllamaIntegration()
            
            self._react_manager = ReactAgentManager(self.ollama_integration)
            logger.info("ReactAgentManager initialized")
        
        return self._react_manager

    async def execute_react_agent(self, agent_type: str, user_input: str, user_id: str = None, **kwargs) -> Dict[str, Any]:
        """
        Ejecuta un agente ReAct con manejo de errores y métricas integradas.
        
        Args:
            agent_type: Tipo de agente ReAct (product, support, ecommerce, tracking, general)
            user_input: Entrada del usuario
            user_id: ID del usuario para métricas
            **kwargs: Argumentos adicionales para el agente
            
        Returns:
            Resultado de la ejecución del agente
        """
        start_time = time.time()
        
        try:
            react_manager = await self.get_react_manager()
            result = await react_manager.execute_agent(agent_type, user_input, **kwargs)
            
            # Registrar métricas
            execution_time = time.time() - start_time
            self._update_react_stats(agent_type, execution_time, True, user_id)
            
            logger.info(f"ReAct agent '{agent_type}' executed successfully for user {user_id} in {execution_time:.3f}s")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            self._update_react_stats(agent_type, execution_time, False, user_id)
            
            logger.error(f"ReAct agent '{agent_type}' failed for user {user_id}: {e}")
            return {
                "success": False,
                "agent_type": agent_type,
                "error": f"Error executing ReAct agent: {str(e)}",
                "user_input": user_input,
                "execution_time": execution_time
            }

    def _update_react_stats(self, agent_type: str, execution_time: float, success: bool, user_id: str = None):
        """Actualiza estadísticas para agentes ReAct"""
        react_key = f"react_{agent_type}"
        
        if react_key not in self._agent_stats:
            self._agent_stats[react_key] = {
                "created_count": 0,
                "usage_count": 0,
                "total_response_time": 0.0,
                "last_created": None,
                "avg_response_time": 0.0,
                "success_count": 0,
                "error_count": 0,
                "success_rate": 0.0
            }
        
        stats = self._agent_stats[react_key]
        stats["usage_count"] += 1
        stats["total_response_time"] += execution_time
        stats["avg_response_time"] = stats["total_response_time"] / stats["usage_count"]
        
        if success:
            stats["success_count"] += 1
        else:
            stats["error_count"] += 1
        
        stats["success_rate"] = (stats["success_count"] / stats["usage_count"]) * 100

    def get_react_agent_types(self) -> list:
        """Obtiene los tipos de agentes ReAct disponibles"""
        return ["product", "support", "ecommerce", "tracking", "general"]

    def __del__(self):
        """Destructor - asegurar limpieza"""
        if self._cleanup_task and not self._cleanup_task.done():
            logger.warning("AgentManager destroyed without proper shutdown")