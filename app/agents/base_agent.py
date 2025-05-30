from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAgent(ABC):
    """Clase base para todos los agentes del chatbot"""
    
    def __init__(self, ai_service, product_service, customer_service):
        self.ai_service = ai_service
        self.product_service = product_service
        self.customer_service = customer_service
    
    @abstractmethod
    async def process(self, customer: Dict[str, Any], message_text: str, historial: str) -> str:
        """
        Procesa el mensaje y genera una respuesta
        
        Args:
            customer: Diccionario con información del cliente
            message_text: Texto del mensaje del usuario
            historial: Historial de la conversación
            
        Returns:
            Respuesta generada por el agente
        """
        pass
    
    def _build_context(self, customer: Dict[str, Any], additional_info: Dict[str, Any] = None) -> str:
        """
        Construye el contexto para el prompt
        
        Args:
            customer: Información del cliente
            additional_info: Información adicional específica del agente
            
        Returns:
            Contexto formateado como string
        """
        context = f"Cliente: {customer['profile_name'] or customer['phone_number']}\n"
        context += f"Total interacciones: {customer['total_interactions']}\n"
        
        if customer.get('interests'):
            context += f"Intereses previos: {', '.join(customer['interests'])}\n"
        
        if additional_info:
            for key, value in additional_info.items():
                context += f"{key}: {value}\n"
        
        return context