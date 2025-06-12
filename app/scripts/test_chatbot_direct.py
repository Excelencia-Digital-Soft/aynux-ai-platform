#!/usr/bin/env python3
"""
Script para probar el servicio de chatbot directamente sin WhatsApp
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
from app.services.chatbot_service import ChatbotService
from app.services.langgraph_chatbot_service import LangGraphChatbotService


class ChatbotTester:
    """Clase para probar servicios de chatbot directamente"""

    def __init__(self, use_langgraph: bool = True):
        self.use_langgraph = use_langgraph
        self.service = None
        self.conversation_history = []
        self.user_number = "5491234567890"  # Número de prueba
        self.user_name = "Usuario de Prueba"

        # Configurar logging
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        """Inicializa el servicio de chatbot"""
        print(f"🤖 Inicializando servicio {'LangGraph' if self.use_langgraph else 'Traditional'}...")

        try:
            if self.use_langgraph:
                self.service = LangGraphChatbotService()
                await self.service.initialize()
                print("✅ Servicio LangGraph inicializado")
            else:
                self.service = ChatbotService()
                print("✅ Servicio Traditional inicializado")

            return True

        except Exception as e:
            print(f"❌ Error inicializando servicio: {e}")
            return False

    def create_test_message(self, text: str) -> tuple:
        """Crea un mensaje de prueba"""
        message = WhatsAppMessage(
            from_=self.user_number,
            id=f"test_msg_{len(self.conversation_history):03d}",
            type="text",
            timestamp=str(int(datetime.now().timestamp())),
            text=TextMessage(body=text),
        )

        contact = Contact(wa_id=self.user_number, profile={"name": self.user_name})

        return message, contact

    async def send_message(self, text: str) -> Dict:
        """Envía un mensaje al chatbot y obtiene la respuesta"""
        print(f"\n👤 Usuario: {text}")

        # Crear mensaje de prueba
        message, contact = self.create_test_message(text)

        # Procesar mensaje
        try:
            start_time = datetime.now()
            result = await self.service.process_webhook_message(message, contact)
            end_time = datetime.now()

            response_time = (end_time - start_time).total_seconds()

            print(f"🤖 Bot ({response_time:.2f}s): {result.message}")

            # Guardar en historial
            self.conversation_history.append(
                {
                    "timestamp": start_time.isoformat(),
                    "user_message": text,
                    "bot_response": result.message,
                    "status": result.status,
                    "response_time": response_time,
                }
            )

            return {
                "success": result.status == "success",
                "response": result.message,
                "response_time": response_time,
                "timestamp": start_time.isoformat(),
            }

        except Exception as e:
            print(f"❌ Error procesando mensaje: {e}")
            return {"success": False, "error": str(e), "timestamp": datetime.now().isoformat()}

    async def run_conversation_test(self, messages: List[str]):
        """Ejecuta una conversación de prueba completa"""
        print("🗣️  Iniciando conversación de prueba...")

        results = []
        for i, message in enumerate(messages, 1):
            print(f"\n--- Mensaje {i}/{len(messages)} ---")
            result = await self.send_message(message)
            results.append(result)

            # Pausa entre mensajes
            await asyncio.sleep(1)

        return results

    def generate_conversation_summary(self) -> Dict:
        """Genera un resumen de la conversación"""
        if not self.conversation_history:
            return {"error": "No conversation history"}

        total_messages = len(self.conversation_history)
        successful_responses = sum(1 for msg in self.conversation_history if msg.get("status") == "success")
        avg_response_time = sum(msg.get("response_time", 0) for msg in self.conversation_history) / total_messages

        return {
            "total_messages": total_messages,
            "successful_responses": successful_responses,
            "success_rate": (successful_responses / total_messages) * 100,
            "average_response_time": avg_response_time,
            "conversation_duration": (
                datetime.fromisoformat(self.conversation_history[-1]["timestamp"])
                - datetime.fromisoformat(self.conversation_history[0]["timestamp"])
            ).total_seconds(),
        }

    def save_conversation_log(self, filename: str = None):
        """Guarda el log de la conversación"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            service_type = "langgraph" if self.use_langgraph else "traditional"
            
            # Create logs directory in the project root
            logs_dir = Path(__file__).parent.parent.parent / "logs"
            logs_dir.mkdir(exist_ok=True)
            
            filename = logs_dir / f"conversation_test_{service_type}_{timestamp}.json"

        log_data = {
            "test_info": {
                "service_type": "langgraph" if self.use_langgraph else "traditional",
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
            await self.service.cleanup()
        print("🧹 Recursos limpiados")


# Conversaciones de prueba predefinidas
TEST_CONVERSATIONS = {
    "saludo_basico": ["Hola", "¿Qué productos tienen?", "Gracias, hasta luego"],
    "consulta_laptops": [
        "Hola, buenos días",
        "Necesito una laptop para gaming",
        "¿Cuáles tienen en stock?",
        "¿Cuál es el precio de la más económica?",
        "¿Tienen garantía?",
        "Perfecto, muchas gracias",
    ],
    "consulta_componentes": [
        "Hola",
        "Estoy armando una PC gamer",
        "¿Qué procesadores Ryzen tienen?",
        "¿Y tarjetas de video RTX?",
        "¿Cuál es el precio del combo más recomendado?",
        "¿Hacen descuento por cantidad?",
        "Gracias por la información",
    ],
    "consulta_stock": [
        "Buenos días",
        "¿Tienen stock de laptops Asus?",
        "¿Y de la marca HP?",
        "¿Cuándo les llega mercadería nueva?",
        "Perfecto, los contacto más tarde",
    ],
    "conversacion_compleja": [
        "Hola, ¿cómo están?",
        "Necesito equipar una oficina con 5 computadoras",
        "Debe ser para trabajo de oficina, nada muy exigente",
        "¿Cuál sería el presupuesto aproximado?",
        "¿Incluye monitor, teclado y mouse?",
        "¿Qué garantía tienen?",
        "¿Hacen instalación a domicilio?",
        "¿Aceptan pago en cuotas?",
        "Perfecto, me paso por el local mañana",
        "Muchas gracias por toda la información",
    ],
}


async def main():
    """Función principal"""
    print("🧪 CHATBOT DIRECT TESTER")
    print("=" * 50)

    # Menú de opciones
    print("Opciones disponibles:")
    print("1. Conversación interactiva")
    print("2. Test con conversación predefinida")
    print("3. Test de performance (múltiples conversaciones)")
    print("4. Comparar servicios (LangGraph vs Traditional)")

    choice = input("\nSelecciona una opción (1-4): ").strip()

    if choice == "1":
        await interactive_conversation()
    elif choice == "2":
        await predefined_conversation_test()
    elif choice == "3":
        await performance_test()
    elif choice == "4":
        await compare_services()
    else:
        print("❌ Opción no válida")


async def interactive_conversation():
    """Conversación interactiva con el usuario"""
    use_langgraph = input("¿Usar LangGraph? (y/n): ").lower().startswith("y")

    tester = ChatbotTester(use_langgraph=use_langgraph)

    if not await tester.initialize():
        return

    print("\n💬 Conversación interactiva iniciada")
    print("Escribe 'quit' para terminar")

    try:
        while True:
            user_input = input("\n👤 Tu mensaje: ").strip()

            if user_input.lower() in ["quit", "exit", "salir"]:
                break

            if user_input:
                await tester.send_message(user_input)

        # Mostrar resumen
        summary = tester.generate_conversation_summary()
        print("\n📊 Resumen de la conversación:")
        print(f"  • Mensajes totales: {summary['total_messages']}")
        print(f"  • Tasa de éxito: {summary['success_rate']:.1f}%")
        print(f"  • Tiempo promedio: {summary['average_response_time']:.2f}s")

        # Guardar log
        filename = tester.save_conversation_log()
        print(f"  • Log guardado: {filename}")

    finally:
        await tester.cleanup()


async def predefined_conversation_test():
    """Test con conversaciones predefinidas"""
    print("\nConversaciones disponibles:")
    for i, name in enumerate(TEST_CONVERSATIONS.keys(), 1):
        print(f"{i}. {name}")

    choice = input("\nSelecciona una conversación (número): ").strip()

    try:
        conversation_name = list(TEST_CONVERSATIONS.keys())[int(choice) - 1]
        messages = TEST_CONVERSATIONS[conversation_name]
    except (ValueError, IndexError):
        print("❌ Selección no válida")
        return

    use_langgraph = input("¿Usar LangGraph? (y/n): ").lower().startswith("y")

    tester = ChatbotTester(use_langgraph=use_langgraph)

    if not await tester.initialize():
        return

    print(f"\n🎭 Ejecutando conversación: {conversation_name}")

    try:
        results = await tester.run_conversation_test(messages)

        # Mostrar resumen
        summary = tester.generate_conversation_summary()
        print("\n📊 Resultados del test:")
        print(f"  • Conversación: {conversation_name}")
        print(f"  • Servicio: {'LangGraph' if use_langgraph else 'Traditional'}")
        print(f"  • Mensajes procesados: {summary['total_messages']}")
        print(f"  • Tasa de éxito: {summary['success_rate']:.1f}%")
        print(f"  • Tiempo promedio: {summary['average_response_time']:.2f}s")
        print(f"  • Duración total: {summary['conversation_duration']:.2f}s")

        # Guardar log
        filename = tester.save_conversation_log()

    finally:
        await tester.cleanup()


async def performance_test():
    """Test de performance con múltiples conversaciones"""
    use_langgraph = input("¿Usar LangGraph? (y/n): ").lower().startswith("y")

    print(f"\n⚡ Test de performance con servicio {'LangGraph' if use_langgraph else 'Traditional'}")

    all_results = []

    for conversation_name, messages in TEST_CONVERSATIONS.items():
        print(f"\n🔄 Procesando: {conversation_name}")

        tester = ChatbotTester(use_langgraph=use_langgraph)

        if not await tester.initialize():
            continue

        try:
            results = await tester.run_conversation_test(messages)
            summary = tester.generate_conversation_summary()

            all_results.append(
                {"conversation": conversation_name, "summary": summary, "details": tester.conversation_history}
            )

            print(
                f"  ✅ Completado - {summary['success_rate']:.1f}% éxito, {summary['average_response_time']:.2f}s promedio"
            )

        finally:
            await tester.cleanup()

    # Resumen general
    print("\n📈 RESUMEN GENERAL DE PERFORMANCE")
    print("=" * 50)

    total_messages = sum(r["summary"]["total_messages"] for r in all_results)
    avg_success_rate = sum(r["summary"]["success_rate"] for r in all_results) / len(all_results)
    avg_response_time = sum(r["summary"]["average_response_time"] for r in all_results) / len(all_results)

    print(f"🎯 Conversaciones procesadas: {len(all_results)}")
    print(f"📝 Mensajes totales: {total_messages}")
    print(f"✅ Tasa de éxito promedio: {avg_success_rate:.1f}%")
    print(f"⚡ Tiempo de respuesta promedio: {avg_response_time:.2f}s")

    # Guardar resultados
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    service_type = "langgraph" if use_langgraph else "traditional"
    
    # Create logs directory in the project root
    logs_dir = Path(__file__).parent.parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    filename = logs_dir / f"performance_test_{service_type}_{timestamp}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(
            {
                "test_info": {
                    "service_type": service_type,
                    "test_timestamp": datetime.now().isoformat(),
                    "conversations_count": len(all_results),
                    "total_messages": total_messages,
                },
                "summary": {"average_success_rate": avg_success_rate, "average_response_time": avg_response_time},
                "detailed_results": all_results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"💾 Resultados guardados en: {filename}")


async def compare_services():
    """Compara el rendimiento entre servicios"""
    print("\n🔍 COMPARACIÓN DE SERVICIOS")
    print("=" * 50)

    # Seleccionar conversación para comparar
    print("Conversaciones disponibles:")
    for i, name in enumerate(TEST_CONVERSATIONS.keys(), 1):
        print(f"{i}. {name}")

    choice = input("\nSelecciona una conversación para comparar (número): ").strip()

    try:
        conversation_name = list(TEST_CONVERSATIONS.keys())[int(choice) - 1]
        messages = TEST_CONVERSATIONS[conversation_name]
    except (ValueError, IndexError):
        print("❌ Selección no válida")
        return

    results = {}

    # Test con ambos servicios
    for service_name, use_langgraph in [("Traditional", False), ("LangGraph", True)]:
        print(f"\n🧪 Probando con {service_name}...")

        tester = ChatbotTester(use_langgraph=use_langgraph)

        if not await tester.initialize():
            print(f"❌ No se pudo inicializar {service_name}")
            continue

        try:
            await tester.run_conversation_test(messages)
            summary = tester.generate_conversation_summary()
            results[service_name] = summary

            print(
                f"  ✅ {service_name}: {summary['success_rate']:.1f}% éxito, {summary['average_response_time']:.2f}s promedio"
            )

        finally:
            await tester.cleanup()

    # Mostrar comparación
    if len(results) == 2:
        print("\n📊 COMPARACIÓN DETALLADA")
        print("=" * 50)

        for metric in ["total_messages", "success_rate", "average_response_time", "conversation_duration"]:
            print(f"\n{metric.replace('_', ' ').title()}:")
            for service, data in results.items():
                value = data[metric]
                if "rate" in metric:
                    print(f"  {service}: {value:.1f}%")
                elif "time" in metric:
                    print(f"  {service}: {value:.2f}s")
                else:
                    print(f"  {service}: {value}")

        # Determinar ganador
        langgraph_time = results.get("LangGraph", {}).get("average_response_time", float("inf"))
        traditional_time = results.get("Traditional", {}).get("average_response_time", float("inf"))

        if langgraph_time < traditional_time:
            print(f"\n🏆 LangGraph es {((traditional_time / langgraph_time - 1) * 100):.1f}% más rápido")
        else:
            print(f"\n🏆 Traditional es {((langgraph_time / traditional_time - 1) * 100):.1f}% más rápido")

        # Guardar comparación
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create logs directory in the project root
        logs_dir = Path(__file__).parent.parent.parent / "logs"
        logs_dir.mkdir(exist_ok=True)
        
        filename = logs_dir / f"service_comparison_{timestamp}.json"

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "comparison_info": {"conversation": conversation_name, "timestamp": datetime.now().isoformat()},
                    "results": results,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        print(f"💾 Comparación guardada en: {filename}")


if __name__ == "__main__":
    asyncio.run(main())
