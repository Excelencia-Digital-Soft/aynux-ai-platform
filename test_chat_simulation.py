#!/usr/bin/env python3
"""
Simulación de conversación real para probar el flujo completo del chatbot
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.append(str(Path(__file__).parent))

from app.models.message import WhatsAppMessage, TextMessage, Contact, BotResponse
from app.services.langgraph_chatbot_service import LangGraphChatbotService

class ChatSimulator:
    """Simulador de conversación para testing"""
    
    def __init__(self):
        self.test_user = "5491234567890"
        self.test_name = "Usuario Test"
        self.conversation_history = []
        self.service = None
    
    async def initialize(self):
        """Inicializar el servicio de chatbot"""
        try:
            print("🔧 Inicializando servicio LangGraph...")
            self.service = LangGraphChatbotService()
            await self.service.initialize()
            print("✅ Servicio inicializado correctamente")
            return True
        except Exception as e:
            print(f"❌ Error inicializando servicio: {e}")
            return False
    
    def create_message(self, text: str) -> tuple[WhatsAppMessage, Contact]:
        """Crear mensaje de WhatsApp y contacto"""
        message = WhatsAppMessage(
            from_=self.test_user,
            id=f"msg_{len(self.conversation_history):03d}",
            type="text",
            timestamp=str(int(datetime.now().timestamp())),
            text=TextMessage(body=text)
        )
        
        contact = Contact(
            wa_id=self.test_user,
            profile={"name": self.test_name}
        )
        
        return message, contact
    
    async def send_message(self, text: str) -> BotResponse:
        """Enviar un mensaje y obtener respuesta"""
        if not self.service:
            raise Exception("Servicio no inicializado")
        
        message, contact = self.create_message(text)
        
        print(f"👤 Usuario: {text}")
        
        try:
            start_time = datetime.now()
            response = await self.service.procesar_mensaje(message, contact)
            end_time = datetime.now()
            
            response_time = (end_time - start_time).total_seconds()
            
            print(f"🤖 Bot ({response_time:.2f}s): {response.message}")
            print(f"📊 Estado: {response.status}")
            
            # Guardar en historial
            self.conversation_history.append({
                "user": text,
                "bot": response.message,
                "status": response.status,
                "response_time": response_time,
                "timestamp": datetime.now().isoformat()
            })
            
            return response
            
        except Exception as e:
            error_msg = f"Error procesando mensaje: {e}"
            print(f"❌ {error_msg}")
            
            self.conversation_history.append({
                "user": text,
                "bot": error_msg,
                "status": "error",
                "response_time": 0,
                "timestamp": datetime.now().isoformat()
            })
            
            return BotResponse(status="failure", message=error_msg)
    
    async def run_conversation_test(self):
        """Ejecutar una conversación de prueba completa"""
        print("💬 SIMULACIÓN DE CONVERSACIÓN COMPLETA")
        print("=" * 50)
        
        # Escenario de conversación típica
        conversation_flow = [
            "Hola, buenos días",
            "¿Qué laptops gaming tienen disponibles?",
            "Necesito algo para jugar Cyberpunk 2077 en ultra",
            "¿Cuál me recomiendas entre 150,000 y 200,000?",
            "¿Esa laptop tiene buena garantía?",
            "¿Tienen stock disponible?",
            "¿Qué formas de pago aceptan?",
            "¿Hacen envíos a toda Argentina?",
            "Perfecto, ¿cómo puedo hacer el pedido?",
            "Gracias por toda la información"
        ]
        
        successful_responses = 0
        
        for i, message in enumerate(conversation_flow, 1):
            print(f"\n--- Intercambio {i}/{len(conversation_flow)} ---")
            
            try:
                response = await self.send_message(message)
                
                if response.status == "success":
                    successful_responses += 1
                
                # Pausa pequeña entre mensajes
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ Error crítico en mensaje {i}: {e}")
                break
        
        # Mostrar estadísticas
        print(f"\n📈 ESTADÍSTICAS DE LA CONVERSACIÓN")
        print("=" * 50)
        print(f"Mensajes enviados: {len(conversation_flow)}")
        print(f"Respuestas exitosas: {successful_responses}")
        print(f"Tasa de éxito: {(successful_responses/len(conversation_flow)*100):.1f}%")
        
        # Calcular tiempo promedio de respuesta
        response_times = [h["response_time"] for h in self.conversation_history if h["response_time"] > 0]
        if response_times:
            avg_time = sum(response_times) / len(response_times)
            max_time = max(response_times)
            print(f"Tiempo promedio de respuesta: {avg_time:.2f}s")
            print(f"Tiempo máximo de respuesta: {max_time:.2f}s")
        
        return successful_responses == len(conversation_flow)
    
    async def test_error_handling(self):
        """Probar manejo de errores con mensajes problemáticos"""
        print(f"\n🛠️ PRUEBA DE MANEJO DE ERRORES")
        print("=" * 50)
        
        error_test_cases = [
            "",  # Mensaje vacío
            "   ",  # Solo espacios
            "a" * 1000,  # Mensaje muy largo
            "¿¿¿???",  # Caracteres especiales
            "🎮🎮🎮🎮🎮",  # Solo emojis
        ]
        
        for i, test_case in enumerate(error_test_cases, 1):
            print(f"\n--- Test de Error {i} ---")
            display_text = test_case if len(test_case) < 50 else f"{test_case[:47]}..."
            print(f"Probando: '{display_text}'")
            
            try:
                response = await self.send_message(test_case)
                # Verificar que el sistema maneje gracefully
                if response.status in ["success", "failure"]:
                    print("✅ Error manejado correctamente")
                else:
                    print("⚠️ Respuesta inesperada")
            except Exception as e:
                print(f"❌ Error no controlado: {e}")
    
    async def test_context_memory(self):
        """Probar si el sistema mantiene contexto entre mensajes"""
        print(f"\n🧠 PRUEBA DE MEMORIA DE CONTEXTO")
        print("=" * 50)
        
        context_flow = [
            "Estoy buscando una laptop",
            "Para gaming principalmente",
            "¿Cuál me recomiendas de esa marca?",  # Referencia a contexto anterior
            "¿Y el precio de esa?",  # Otra referencia
        ]
        
        for message in context_flow:
            await self.send_message(message)
            await asyncio.sleep(0.5)
    
    def save_conversation_log(self):
        """Guardar log detallado de la conversación"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"chat_simulation_log_{timestamp}.json"
        
        log_data = {
            "test_info": {
                "user": self.test_user,
                "name": self.test_name,
                "timestamp": timestamp,
                "total_messages": len(self.conversation_history)
            },
            "conversation": self.conversation_history,
            "summary": {
                "successful_responses": len([h for h in self.conversation_history if h["status"] == "success"]),
                "failed_responses": len([h for h in self.conversation_history if h["status"] != "success"]),
                "avg_response_time": sum(h["response_time"] for h in self.conversation_history) / len(self.conversation_history) if self.conversation_history else 0
            }
        }
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        
        print(f"📝 Log guardado en: {log_file}")
        return log_file

async def main():
    """Función principal"""
    print("🤖 SIMULADOR DE CHAT - CONVERSASHOP BOT")
    print("=" * 60)
    
    simulator = ChatSimulator()
    
    # Inicializar servicio
    if not await simulator.initialize():
        print("❌ No se pudo inicializar el servicio. Abortando pruebas.")
        return
    
    try:
        # 1. Conversación normal
        print("\n🎯 FASE 1: Conversación típica de usuario")
        conversation_success = await simulator.run_conversation_test()
        
        # 2. Pruebas de error
        print("\n🎯 FASE 2: Manejo de errores")
        await simulator.test_error_handling()
        
        # 3. Pruebas de contexto
        print("\n🎯 FASE 3: Memoria de contexto")
        await simulator.test_context_memory()
        
        # Guardar log
        log_file = simulator.save_conversation_log()
        
        # Resultado final
        print(f"\n🏁 RESULTADO FINAL")
        print("=" * 50)
        if conversation_success:
            print("✅ Conversación principal exitosa")
            print("🎉 El chatbot funciona correctamente para casos típicos")
        else:
            print("⚠️ Algunos problemas detectados en la conversación principal")
            print("🔍 Revisar el log para identificar errores específicos")
        
        print(f"📋 Log detallado disponible en: {log_file}")
        
    except Exception as e:
        print(f"❌ Error crítico durante las pruebas: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        try:
            if simulator.service:
                await simulator.service.cleanup()
                print("🧹 Cleanup completado")
        except Exception as e:
            print(f"⚠️ Error en cleanup: {e}")

if __name__ == "__main__":
    asyncio.run(main())