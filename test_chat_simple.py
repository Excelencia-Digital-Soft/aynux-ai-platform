#!/usr/bin/env python3
"""
Test simple del chatbot sin LangGraph para verificar funcionalidad básica
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.append(str(Path(__file__).parent))

from app.models.message import WhatsAppMessage, TextMessage, Contact, BotResponse
from app.services.chatbot_service import ChatbotService

class SimpleChatTest:
    """Test del servicio de chatbot tradicional"""
    
    def __init__(self):
        self.test_user = "5491234567890"
        self.test_name = "Usuario Test Simple"
        self.conversation_history = []
        self.service = None
    
    async def initialize(self):
        """Inicializar el servicio de chatbot tradicional"""
        try:
            print("🔧 Inicializando servicio de chatbot tradicional...")
            self.service = ChatbotService()
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
    
    async def run_basic_test(self):
        """Ejecutar prueba básica de funcionalidad"""
        print("💬 PRUEBA BÁSICA DE FUNCIONALIDAD")
        print("=" * 50)
        
        basic_messages = [
            "Hola",
            "¿Qué productos tienen?",
            "Busco una laptop",
            "¿Cuánto cuesta?",
            "Gracias"
        ]
        
        successful_responses = 0
        
        for i, message in enumerate(basic_messages, 1):
            print(f"\n--- Mensaje {i}/{len(basic_messages)} ---")
            
            try:
                response = await self.send_message(message)
                
                if response.status == "success":
                    successful_responses += 1
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"❌ Error en mensaje {i}: {e}")
                break
        
        print(f"\n📈 Resultados:")
        print(f"Mensajes exitosos: {successful_responses}/{len(basic_messages)}")
        print(f"Tasa de éxito: {(successful_responses/len(basic_messages)*100):.1f}%")
        
        return successful_responses > 0

async def main():
    """Función principal"""
    print("🤖 TEST SIMPLE DEL CHATBOT TRADICIONAL")
    print("=" * 60)
    
    test = SimpleChatTest()
    
    # Inicializar servicio
    if not await test.initialize():
        print("❌ No se pudo inicializar el servicio.")
        return
    
    try:
        # Prueba básica
        success = await test.run_basic_test()
        
        if success:
            print("\n✅ Funcionalidad básica del chatbot confirmada")
        else:
            print("\n❌ Problemas en la funcionalidad básica")
        
    except Exception as e:
        print(f"❌ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())