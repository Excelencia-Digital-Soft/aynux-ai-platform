"""
Implementación de agentes ReAct usando create_react_agent de LangGraph
"""

import logging
from typing import Dict, List, Any, Optional
from langchain.agents import create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import BaseTool

from app.agents.langgraph_system.integrations.ollama_integration import OllamaIntegration
# TODO: Import actual tools when they are implemented
# from app.agents.langgraph_system.tools import (
#     search_products_tool,
#     get_product_details_tool,
#     check_stock_tool,
#     compare_products_tool,
#     get_categories_tool,
#     get_promotions_tool,
#     calculate_shipping_tool,
#     get_payment_methods_tool,
#     search_faq_tool,
#     create_ticket_tool,
#     get_warranty_info_tool,
#     track_order_tool,
#     get_delivery_info_tool,
#     update_shipping_address_tool
# )

# Placeholder tools for now
search_products_tool = None
get_product_details_tool = None
check_stock_tool = None
compare_products_tool = None
get_categories_tool = None
get_promotions_tool = None
calculate_shipping_tool = None
get_payment_methods_tool = None
search_faq_tool = None
create_ticket_tool = None
get_warranty_info_tool = None
track_order_tool = None
get_delivery_info_tool = None
update_shipping_address_tool = None

logger = logging.getLogger(__name__)


class ReactAgentFactory:
    """Factory para crear agentes ReAct especializados"""
    
    def __init__(self, ollama_integration: OllamaIntegration):
        self.ollama = ollama_integration
        
    def _create_base_prompt(self, agent_role: str, tools_description: str) -> PromptTemplate:
        """Crea el prompt base para agentes ReAct"""
        template = f"""Eres un {agent_role} especializado en e-commerce conversacional para WhatsApp.

PERSONALIDAD:
- Amigable, profesional y servicial
- Respuestas concisas pero completas
- Proactivo en sugerir soluciones
- Empático con las necesidades del cliente

HERRAMIENTAS DISPONIBLES:
{tools_description}

INSTRUCCIONES:
1. Analiza cuidadosamente la consulta del usuario
2. Usa las herramientas apropiadas para obtener información precisa
3. Proporciona respuestas útiles y orientadas a la acción
4. Si necesitas información adicional, pregunta de forma específica
5. Mantén el tono conversacional apropiado para WhatsApp

Responde SIEMPRE en español y adapta tu lenguaje al contexto de WhatsApp.

Pregunta del usuario: {{input}}

Razonamiento paso a paso:
{{agent_scratchpad}}"""
        
        return PromptTemplate(
            input_variables=["input", "agent_scratchpad"],
            template=template
        )
    
    def create_product_agent(self) -> Any:
        """Crea un agente especializado en productos"""
        tools = [
            search_products_tool,
            get_product_details_tool,
            check_stock_tool,
            compare_products_tool,
            get_categories_tool,
            get_promotions_tool
        ]
        
        tools_description = """
- search_products_tool: Busca productos por consulta, categoría y filtros de precio
- get_product_details_tool: Obtiene especificaciones completas de un producto
- check_stock_tool: Verifica disponibilidad de stock
- compare_products_tool: Compara múltiples productos lado a lado
- get_categories_tool: Obtiene categorías disponibles
- get_promotions_tool: Consulta ofertas y descuentos activos
"""
        
        prompt = self._create_base_prompt(
            "asistente de productos especializado",
            tools_description
        )
        
        llm = self.ollama.get_llm(temperature=0.3)
        
        return create_react_agent(
            llm=llm,
            tools=tools,
            prompt=prompt
        )
    
    def create_support_agent(self) -> Any:
        """Crea un agente especializado en soporte"""
        tools = [
            search_faq_tool,
            create_ticket_tool,
            get_warranty_info_tool,
            track_order_tool
        ]
        
        tools_description = """
- search_faq_tool: Busca respuestas en preguntas frecuentes
- create_ticket_tool: Crea tickets de soporte para problemas complejos
- get_warranty_info_tool: Consulta información de garantía de productos
- track_order_tool: Rastrea el estado de órdenes
"""
        
        prompt = self._create_base_prompt(
            "agente de soporte al cliente",
            tools_description
        )
        
        llm = self.ollama.get_llm(temperature=0.2)  # Más determinístico para soporte
        
        return create_react_agent(
            llm=llm,
            tools=tools,
            prompt=prompt
        )
    
    def create_ecommerce_agent(self) -> Any:
        """Crea un agente especializado en operaciones de e-commerce"""
        tools = [
            get_categories_tool,
            get_promotions_tool,
            calculate_shipping_tool,
            get_payment_methods_tool,
            search_products_tool
        ]
        
        tools_description = """
- get_categories_tool: Obtiene categorías y estructura del catálogo
- get_promotions_tool: Consulta promociones y ofertas disponibles
- calculate_shipping_tool: Calcula costos y tiempos de envío
- get_payment_methods_tool: Muestra métodos de pago disponibles
- search_products_tool: Búsqueda general de productos
"""
        
        prompt = self._create_base_prompt(
            "especialista en operaciones de e-commerce",
            tools_description
        )
        
        llm = self.ollama.get_llm(temperature=0.4)
        
        return create_react_agent(
            llm=llm,
            tools=tools,
            prompt=prompt
        )
    
    def create_tracking_agent(self) -> Any:
        """Crea un agente especializado en seguimiento y entrega"""
        tools = [
            track_order_tool,
            get_delivery_info_tool,
            update_shipping_address_tool
        ]
        
        tools_description = """
- track_order_tool: Rastrea el estado actual de órdenes
- get_delivery_info_tool: Obtiene información detallada de entrega
- update_shipping_address_tool: Actualiza direcciones de envío
"""
        
        prompt = self._create_base_prompt(
            "especialista en seguimiento y entregas",
            tools_description
        )
        
        llm = self.ollama.get_llm(temperature=0.1)  # Muy determinístico para tracking
        
        return create_react_agent(
            llm=llm,
            tools=tools,
            prompt=prompt
        )
    
    def create_general_agent(self) -> Any:
        """Crea un agente general con acceso a todas las herramientas"""
        all_tools = [
            # Productos
            search_products_tool,
            get_product_details_tool,
            check_stock_tool,
            compare_products_tool,
            # E-commerce
            get_categories_tool,
            get_promotions_tool,
            calculate_shipping_tool,
            get_payment_methods_tool,
            # Soporte
            search_faq_tool,
            create_ticket_tool,
            get_warranty_info_tool,
            # Tracking
            track_order_tool,
            get_delivery_info_tool,
            update_shipping_address_tool
        ]
        
        tools_description = """
HERRAMIENTAS DE PRODUCTOS:
- search_products_tool: Busca productos por consulta y filtros
- get_product_details_tool: Detalles completos de productos
- check_stock_tool: Verificación de disponibilidad
- compare_products_tool: Comparación entre productos

HERRAMIENTAS DE E-COMMERCE:
- get_categories_tool: Estructura del catálogo
- get_promotions_tool: Ofertas y descuentos
- calculate_shipping_tool: Costos de envío
- get_payment_methods_tool: Métodos de pago

HERRAMIENTAS DE SOPORTE:
- search_faq_tool: Preguntas frecuentes
- create_ticket_tool: Crear tickets de soporte
- get_warranty_info_tool: Información de garantía

HERRAMIENTAS DE SEGUIMIENTO:
- track_order_tool: Rastreo de órdenes
- get_delivery_info_tool: Información de entrega
- update_shipping_address_tool: Actualizar direcciones
"""
        
        prompt = self._create_base_prompt(
            "asistente integral de e-commerce",
            tools_description
        )
        
        llm = self.ollama.get_llm(temperature=0.5)
        
        return create_react_agent(
            llm=llm,
            tools=all_tools,
            prompt=prompt
        )


class ReactAgentManager:
    """Gestiona instancias de agentes ReAct con lazy loading"""
    
    def __init__(self, ollama_integration: OllamaIntegration):
        self.factory = ReactAgentFactory(ollama_integration)
        self._agents_cache: Dict[str, Any] = {}
        
    async def get_agent(self, agent_type: str) -> Any:
        """Obtiene un agente ReAct del tipo especificado"""
        if agent_type not in self._agents_cache:
            self._agents_cache[agent_type] = self._create_agent(agent_type)
        
        return self._agents_cache[agent_type]
    
    def _create_agent(self, agent_type: str) -> Any:
        """Crea un agente según el tipo especificado"""
        creators = {
            "product": self.factory.create_product_agent,
            "support": self.factory.create_support_agent,
            "ecommerce": self.factory.create_ecommerce_agent,
            "tracking": self.factory.create_tracking_agent,
            "general": self.factory.create_general_agent
        }
        
        creator = creators.get(agent_type)
        if not creator:
            logger.warning(f"Agent type '{agent_type}' not found, using general agent")
            creator = self.factory.create_general_agent
        
        logger.info(f"Creating ReAct agent: {agent_type}")
        return creator()
    
    def clear_cache(self):
        """Limpia la caché de agentes"""
        self._agents_cache.clear()
        logger.info("ReAct agents cache cleared")
    
    def get_available_agents(self) -> List[str]:
        """Retorna la lista de tipos de agentes disponibles"""
        return ["product", "support", "ecommerce", "tracking", "general"]
    
    async def execute_agent(self, agent_type: str, user_input: str, **kwargs) -> Dict[str, Any]:
        """Ejecuta un agente con la entrada del usuario"""
        try:
            agent = await self.get_agent(agent_type)
            
            # Ejecutar el agente con la entrada
            result = await agent.arun(input=user_input, **kwargs)
            
            return {
                "success": True,
                "agent_type": agent_type,
                "response": result,
                "user_input": user_input
            }
            
        except Exception as e:
            logger.error(f"Error executing ReAct agent {agent_type}: {e}")
            return {
                "success": False,
                "agent_type": agent_type,
                "error": str(e),
                "user_input": user_input
            }


# Instancia global para reutilización
_react_manager: Optional[ReactAgentManager] = None


def get_react_agent_manager(ollama_integration: OllamaIntegration) -> ReactAgentManager:
    """Obtiene la instancia global del manager de agentes ReAct"""
    global _react_manager
    
    if _react_manager is None:
        _react_manager = ReactAgentManager(ollama_integration)
    
    return _react_manager


async def execute_react_agent(
    agent_type: str,
    user_input: str,
    ollama_integration: OllamaIntegration,
    **kwargs
) -> Dict[str, Any]:
    """Función de conveniencia para ejecutar agentes ReAct"""
    manager = get_react_agent_manager(ollama_integration)
    return await manager.execute_agent(agent_type, user_input, **kwargs)