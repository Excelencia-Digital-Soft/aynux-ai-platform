#!/usr/bin/env python3
"""
Script para probar el servicio LangGraph directamente sin WhatsApp
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Añadir el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.models.message import Contact, TextMessage, WhatsAppMessage
from app.services.langgraph_chatbot_service import LangGraphChatbotService


class LangGraphTester:
    """Clase para probar el servicio LangGraph directamente"""

    def __init__(self):
        self.service = None
        self.conversation_history = []
        self.user_number = "5491234567890"  # Número de prueba
        self.user_name = "Usuario de Prueba"

        # Configurar logging
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        """Inicializa el servicio LangGraph"""
        print("🤖 Inicializando servicio LangGraph...")

        try:
            self.service = LangGraphChatbotService()
            await self.service.initialize()
            print("✅ Servicio LangGraph inicializado")
            return True
        except Exception as e:
            print(f"❌ Error al inicializar servicio LangGraph: {e}")
            return False

    def create_message(self, text: str) -> WhatsAppMessage:
        """Crea un mensaje de WhatsApp para pruebas"""
        return WhatsAppMessage(
            id=f"msg_{datetime.now().timestamp()}",
            from_number=self.user_number,
            timestamp=str(int(datetime.now().timestamp())),
            type="text",
            text=TextMessage(body=text),
        )

    def create_contact(self) -> Contact:
        """Crea un contacto para pruebas"""
        return Contact(
            profile={"name": self.user_name},
            wa_id=self.user_number,
        )

    async def send_message(self, text: str) -> Dict:
        """Envía un mensaje y recibe la respuesta"""
        if not self.service:
            raise RuntimeError("Servicio no inicializado")

        print(f"\n👤 Usuario: {text}")
        start_time = datetime.now()

        try:
            message = self.create_message(text)
            contact = self.create_contact()

            # Procesar mensaje
            response = await self.service.process_webhook_message(message, contact)
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds()

            # Mostrar respuesta
            if hasattr(response, "text"):
                bot_response = response.text  # type: ignore
            else:
                bot_response = str(response)

            print(f"🤖 Bot: {bot_response}")
            print(f"⏱️  Tiempo: {response_time:.2f}s")

            # Guardar en historial
            self.conversation_history.append(
                {
                    "timestamp": start_time.isoformat(),
                    "user_message": text,
                    "bot_response": bot_response,
                    "response_time": response_time,
                    "success": True,
                }
            )

            return {
                "success": True,
                "response": bot_response,
                "response_time": response_time,
            }

        except Exception as e:
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds()
            error_msg = f"Error: {str(e)}"

            print(f"❌ {error_msg}")
            print(f"⏱️  Tiempo: {response_time:.2f}s")

            # Guardar error en historial
            self.conversation_history.append(
                {
                    "timestamp": start_time.isoformat(),
                    "user_message": text,
                    "bot_response": error_msg,
                    "response_time": response_time,
                    "success": False,
                    "error": str(e),
                }
            )

            return {
                "success": False,
                "error": str(e),
                "response_time": response_time,
            }

    async def run_conversation(self, messages: List[str], conversation_name: str = "test"):
        """Ejecuta una conversación completa"""
        print(f"\n🎯 Iniciando conversación: {conversation_name}")
        print("=" * 50)

        start_time = datetime.now()
        success_count = 0

        for message in messages:
            result = await self.send_message(message)
            if result["success"]:
                success_count += 1
            await asyncio.sleep(0.5)  # Pausa entre mensajes

        end_time = datetime.now()

        # Estadísticas
        total_time = (end_time - start_time).total_seconds()
        avg_response_time = sum(h["response_time"] for h in self.conversation_history) / len(self.conversation_history)
        success_rate = (success_count / len(messages)) * 100

        print(f"\n📊 ESTADÍSTICAS DE {conversation_name.upper()}")
        print("=" * 40)
        print(f"📱 Mensajes totales: {len(messages)}")
        print(f"✅ Éxito: {success_count}/{len(messages)} ({success_rate:.1f}%)")
        print(f"⏱️  Tiempo promedio: {avg_response_time:.2f}s")
        print(f"🕐 Duración total: {total_time:.2f}s")

        return {
            "conversation_name": conversation_name,
            "total_messages": len(messages),
            "success_count": success_count,
            "success_rate": success_rate,
            "average_response_time": avg_response_time,
            "conversation_duration": total_time,
        }

    def generate_conversation_summary(self):
        """Genera un resumen de la conversación"""
        if not self.conversation_history:
            return {}

        total_messages = len(self.conversation_history)
        successful_messages = sum(1 for h in self.conversation_history if h["success"])
        failed_messages = total_messages - successful_messages

        return {
            "total_messages": total_messages,
            "successful_messages": successful_messages,
            "failed_messages": failed_messages,
            "success_rate": (successful_messages / total_messages) * 100 if total_messages > 0 else 0,
            "average_response_time": sum(h["response_time"] for h in self.conversation_history) / total_messages
            if total_messages > 0
            else 0,
            "total_conversation_time": sum(h["response_time"] for h in self.conversation_history),
            "conversation_duration": (
                datetime.fromisoformat(self.conversation_history[-1]["timestamp"])
                - datetime.fromisoformat(self.conversation_history[0]["timestamp"])
            ).total_seconds(),
        }

    def save_conversation_log(self, filename: str = None):
        """Guarda el log de la conversación"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Create logs directory in the project root
            logs_dir = Path(__file__).parent.parent.parent / "logs"
            logs_dir.mkdir(exist_ok=True)

            filename = str(logs_dir / f"langgraph_test_{timestamp}.json")

        log_data = {
            "test_info": {
                "service_type": "langgraph",
                "user_number": self.user_number,
                "user_name": self.user_name,
                "test_timestamp": datetime.now().isoformat(),
            },
            "conversation_history": self.conversation_history,
            "summary": self.generate_conversation_summary(),
        }

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

        print(f"💾 Log guardado en: {filename}")
        return str(filename)

    async def cleanup(self):
        """Limpia recursos"""
        if self.service and hasattr(self.service, "cleanup"):
            cleanup_method = self.service.cleanup
            if asyncio.iscoroutinefunction(cleanup_method):
                await cleanup_method()
            else:
                await cleanup_method()
        print("🧹 Recursos limpiados")


# Conversaciones de prueba predefinidas
TEST_CONVERSATIONS = {
    "saludo_basico": ["Hola", "¿Qué productos tienen?", "Gracias, hasta luego"],
    "consulta_laptops": [
        "Hola, buenos días",
        "Necesito una laptop para gaming",
        "¿Cuáles tienen en stock?",
        "¿Cuál me recomiendan?",
        "¿Cuál es el precio?",
        "Perfecto, muchas gracias",
    ],
    "seguimiento_pedido": [
        "Hola",
        "Quiero hacer seguimiento de mi pedido",
        "Mi número de orden es ORD-2024-001",
        "¿Cuándo llega?",
        "Gracias por la información",
    ],
    "soporte_tecnico": [
        "Hola, tengo un problema",
        "Mi laptop se apaga sola",
        "¿Qué puedo hacer?",
        "¿Tienen servicio técnico?",
        "¿Cuánto cuesta la revisión?",
        "Perfecto, gracias",
    ],
    "consulta_categorias": [
        "Hola",
        "¿Qué categorías de productos manejan?",
        "Muéstrame laptops",
        "Ahora muéstrame smartphones",
        "¿Tienen accesorios?",
        "Gracias por la información",
    ],
}


async def interactive_mode():
    """Modo interactivo para probar el chatbot"""
    tester = LangGraphTester()

    if not await tester.initialize():
        return

    print("\n🎮 MODO INTERACTIVO")
    print("Escribe 'salir' para terminar")
    print("=" * 40)

    try:
        while True:
            user_input = input("\n👤 Tú: ").strip()

            if user_input.lower() in ["salir", "exit", "quit"]:
                break

            if not user_input:
                continue

            await tester.send_message(user_input)

    except KeyboardInterrupt:
        print("\n\n👋 Interrupción del usuario")
    finally:
        await tester.cleanup()
        tester.save_conversation_log()


async def test_conversation(conversation_name: str):
    """Prueba una conversación específica"""
    if conversation_name not in TEST_CONVERSATIONS:
        print(f"❌ Conversación '{conversation_name}' no encontrada")
        print(f"📋 Conversaciones disponibles: {list(TEST_CONVERSATIONS.keys())}")
        return None

    tester = LangGraphTester()

    if not await tester.initialize():
        return None

    try:
        messages = TEST_CONVERSATIONS[conversation_name]
        result = await tester.run_conversation(messages, conversation_name)
        tester.save_conversation_log()
        return result
    finally:
        await tester.cleanup()


async def main():
    """Función principal"""
    if len(sys.argv) < 2:
        print("🤖 ConversaShop - Tester LangGraph")
        print("\nUso:")
        print("  python test_chatbot_direct.py interactive")
        print("  python test_chatbot_direct.py test <conversacion>")
        print("  python test_chatbot_direct.py list")
        print("\nConversaciones disponibles:")
        for name, messages in TEST_CONVERSATIONS.items():
            print(f"  - {name}: {len(messages)} mensajes")
        return

    command = sys.argv[1].lower()

    if command == "interactive":
        await interactive_mode()
    elif command == "list":
        print("📋 Conversaciones disponibles:")
        for name, messages in TEST_CONVERSATIONS.items():
            print(f"  - {name}: {len(messages)} mensajes")
            for i, msg in enumerate(messages, 1):
                print(f"    {i}. {msg}")
            print()
    elif command == "test":
        if len(sys.argv) < 3:
            print("❌ Especifica el nombre de la conversación")
            print(f"📋 Disponibles: {list(TEST_CONVERSATIONS.keys())}")
            return

        conversation_name = sys.argv[2]
        result = await test_conversation(conversation_name)

        if result:
            print(f"\n✅ Test completado para: {conversation_name}")
    else:
        print(f"❌ Comando desconocido: {command}")


if __name__ == "__main__":
    asyncio.run(main())

