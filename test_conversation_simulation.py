#!/usr/bin/env python3
"""
Script para simular conversaciones reales con el sistema LangGraph
Simula mensajes de WhatsApp y verifica el comportamiento de los agentes
"""

import asyncio
import json
import logging
from typing import Dict, Any, List

from app.agents.langgraph_system.graph import EcommerceAssistantGraph
from app.config.langgraph_config import get_langgraph_config

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ConversationSimulator:
    """Simulador de conversaciones para testing del sistema LangGraph"""
    
    def __init__(self):
        self.config = get_langgraph_config()
        self.graph = EcommerceAssistantGraph(self.config.model_dump())
        self.conversation_history = []
        
    async def initialize(self):
        """Inicializa el sistema de forma asíncrona"""
        await self.graph.initialize()
        logger.info("Sistema LangGraph inicializado correctamente")
    
    async def simulate_whatsapp_message(
        self, 
        message: str, 
        phone_number: str = "+5491234567890",
        customer_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Simula un mensaje entrante de WhatsApp
        
        Args:
            message: Contenido del mensaje
            phone_number: Número de teléfono del usuario
            customer_data: Datos del cliente (opcional)
        
        Returns:
            Respuesta del sistema
        """
        logger.info(f"📱 Usuario ({phone_number}): {message}")
        
        # Datos de cliente por defecto
        if customer_data is None:
            customer_data = {
                "customer_id": phone_number,
                "phone": phone_number,
                "name": "Cliente Test",
                "tier": "basic",
                "purchase_history": []
            }
        
        # Procesar mensaje con LangGraph
        try:
            result = await self.graph.process_message(
                message=message,
                customer_data=customer_data,
                conversation_id=phone_number,
                session_config={"max_turns": 10}
            )
            
            response_text = result.get("response", "Lo siento, no pude procesar tu mensaje.")
            agent_used = result.get("agent_used", "unknown")
            
            logger.info(f"🤖 Asistente (vía {agent_used}): {response_text}")
            
            # Guardar en historial
            self.conversation_history.append({
                "user_message": message,
                "assistant_response": response_text,
                "agent_used": agent_used,
                "requires_human": result.get("requires_human", False),
                "is_complete": result.get("is_complete", False)
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error procesando mensaje: {str(e)}")
            error_response = "Disculpa, ocurrió un error técnico. Por favor intenta de nuevo."
            
            self.conversation_history.append({
                "user_message": message,
                "assistant_response": error_response,
                "agent_used": "error_handler",
                "error": str(e)
            })
            
            return {
                "response": error_response,
                "error": str(e),
                "agent_used": "error_handler"
            }
    
    async def run_conversation_scenario(self, scenario_name: str, messages: List[str]):
        """
        Ejecuta un escenario completo de conversación
        
        Args:
            scenario_name: Nombre del escenario
            messages: Lista de mensajes del usuario
        """
        print(f"\n{'='*60}")
        print(f"🎬 ESCENARIO: {scenario_name}")
        print(f"{'='*60}")
        
        phone_number = f"+549{hash(scenario_name) % 10000000000}"
        
        for i, message in enumerate(messages):
            print(f"\n--- Turno {i+1} ---")
            
            result = await self.simulate_whatsapp_message(message, phone_number)
            
            # Verificar si necesita intervención humana
            if result.get("requires_human"):
                print("⚠️  El sistema solicita intervención humana")
                break
                
            # Verificar si la conversación está completa
            if result.get("is_complete"):
                print("✅ Conversación marcada como completa")
                
            # Pequeña pausa para simular tiempo real
            await asyncio.sleep(0.5)
    
    def print_conversation_summary(self):
        """Imprime un resumen de todas las conversaciones"""
        print(f"\n{'='*60}")
        print("📊 RESUMEN DE CONVERSACIONES")
        print(f"{'='*60}")
        
        agent_usage = {}
        total_messages = len(self.conversation_history)
        errors = 0
        
        for entry in self.conversation_history:
            agent = entry.get("agent_used", "unknown")
            agent_usage[agent] = agent_usage.get(agent, 0) + 1
            
            if "error" in entry:
                errors += 1
        
        print(f"Total de mensajes procesados: {total_messages}")
        print(f"Errores encontrados: {errors}")
        print(f"Tasa de éxito: {((total_messages - errors) / total_messages * 100):.1f}%")
        
        print("\nUso de agentes:")
        for agent, count in sorted(agent_usage.items()):
            percentage = (count / total_messages) * 100
            print(f"  {agent}: {count} mensajes ({percentage:.1f}%)")


async def main():
    """Función principal que ejecuta las simulaciones"""
    
    # Crear simulador
    simulator = ConversationSimulator()
    await simulator.initialize()
    
    # Escenario 1: Consulta general de productos
    await simulator.run_conversation_scenario(
        "Consulta General de Productos",
        [
            "Hola, ¿qué productos ofreces?",
            "Me interesan las laptops",
            "¿Cuáles son las especificaciones de la más cara?"
        ]
    )
    
    # Escenario 2: Proceso de compra completo
    await simulator.run_conversation_scenario(
        "Proceso de Compra Completo", 
        [
            "Hola, ¿cuánto cuesta una laptop gaming?",
            "Sí, quiero 2 laptops",
            "Solo factura por favor",
            "¿Cuándo llega el pedido?"
        ]
    )
    
    # Escenario 3: Consulta de promociones
    await simulator.run_conversation_scenario(
        "Consulta de Promociones",
        [
            "¿Tienen ofertas o descuentos disponibles?",
            "Me interesa el descuento para estudiantes",
            "¿Cómo aplico el cupón?"
        ]
    )
    
    # Escenario 4: Soporte técnico
    await simulator.run_conversation_scenario(
        "Soporte Técnico",
        [
            "Tengo un problema con mi laptop, no enciende",
            "La compré hace 2 semanas",
            "¿Puedo hacer una devolución?"
        ]
    )
    
    # Escenario 5: Seguimiento de pedido
    await simulator.run_conversation_scenario(
        "Seguimiento de Pedido",
        [
            "¿Dónde está mi pedido #123456?",
            "¿Cuándo va a llegar?",
            "Necesito cambiar la dirección de entrega"
        ]
    )
    
    # Escenario 6: Consulta de facturación
    await simulator.run_conversation_scenario(
        "Consulta de Facturación",
        [
            "Necesito la factura del pedido #789012",
            "¿Puedo pagar con tarjeta de crédito?",
            "¿Aceptan transferencia bancaria?"
        ]
    )
    
    # Escenario 7: Conversación compleja multi-agente
    await simulator.run_conversation_scenario(
        "Conversación Compleja Multi-Agente",
        [
            "Hola, busco una laptop para diseño gráfico",
            "¿Tienen descuentos en esa categoría?", 
            "Perfecto, quiero comprar una",
            "¿Cómo hago el seguimiento del envío?",
            "¿Y la factura cuándo me llega?"
        ]
    )
    
    # Mostrar resumen
    simulator.print_conversation_summary()
    
    print(f"\n{'='*60}")
    print("🎯 ANÁLISIS DE RESULTADOS")
    print(f"{'='*60}")
    
    # Verificar que no hay respuestas hardcodeadas
    hardcoded_responses = [
        "Lo siento, no entiendo",
        "Por favor contacta soporte", 
        "Función no disponible"
    ]
    
    hardcoded_found = False
    for entry in simulator.conversation_history:
        response = entry.get("assistant_response", "")
        for hardcoded in hardcoded_responses:
            if hardcoded.lower() in response.lower():
                print(f"⚠️  Respuesta hardcodeada detectada: {hardcoded}")
                hardcoded_found = True
    
    if not hardcoded_found:
        print("✅ No se detectaron respuestas hardcodeadas")
    
    # Verificar variedad de agentes
    agents_used = set()
    for entry in simulator.conversation_history:
        agent = entry.get("agent_used")
        if agent and agent != "error_handler":
            agents_used.add(agent)
    
    print(f"✅ Agentes utilizados: {len(agents_used)} de 6 disponibles")
    print(f"   Agentes activos: {', '.join(sorted(agents_used))}")
    
    if len(agents_used) >= 4:
        print("✅ Buena cobertura de agentes - El sistema es dinámico")
    else:
        print("⚠️  Pocos agentes utilizados - Revisar routing")
    
    print(f"\n{'='*60}")
    print("🏁 SIMULACIÓN COMPLETADA")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())