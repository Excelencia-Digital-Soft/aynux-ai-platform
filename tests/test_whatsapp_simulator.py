"""
WhatsApp Webhook Simulator for Testing

Este script simula mensajes de WhatsApp generando payloads válidos del webhook
y enviándolos al endpoint local para probar el sistema multi-dominio.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Dict, List
from uuid import uuid4

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

API_V1_STR = os.getenv("API_V1_STR", "/api/v1")

console = Console()


class WhatsAppSimulator:
    """Simulador de mensajes WhatsApp para testing"""

    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.webhook_url = f"{base_url}{API_V1_STR}/webhook/"
        self.message_count = 0

    def generate_whatsapp_payload(
        self,
        message: str,
        wa_id: str = "1234567890",
        name: str = "Test User",
        message_type: str = "text"
    ) -> Dict:
        """
        Genera un payload válido de WhatsApp webhook

        Args:
            message: Mensaje de texto
            wa_id: WhatsApp ID del usuario
            name: Nombre del usuario
            message_type: Tipo de mensaje (text, interactive, etc.)

        Returns:
            Dict con estructura completa del webhook de WhatsApp
        """
        timestamp = str(int(datetime.now().timestamp()))
        message_id = f"wamid.{uuid4().hex[:20]}"

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WHATSAPP_BUSINESS_ACCOUNT_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15551234567",
                                    "phone_number_id": "PHONE_NUMBER_ID",
                                },
                                "contacts": [
                                    {
                                        "profile": {"name": name},
                                        "wa_id": wa_id,
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": wa_id,
                                        "id": message_id,
                                        "timestamp": timestamp,
                                        "type": message_type,
                                        "text": {"body": message} if message_type == "text" else None,
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }

        return payload

    async def send_message(
        self,
        message: str,
        wa_id: str = "1234567890",
        name: str = "Test User"
    ) -> Dict:
        """
        Envía un mensaje al webhook de WhatsApp

        Args:
            message: Mensaje a enviar
            wa_id: WhatsApp ID del usuario
            name: Nombre del usuario

        Returns:
            Respuesta del servidor
        """
        self.message_count += 1

        # Generar payload
        payload = self.generate_whatsapp_payload(message, wa_id, name)

        # Mostrar payload si está en modo verbose
        console.print(f"\n[bold cyan]📱 Mensaje #{self.message_count}[/bold cyan]")
        console.print(f"[cyan]Usuario:[/cyan] {name} ({wa_id})")
        console.print(f"[cyan]Mensaje:[/cyan] {message}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    result = response.json()

                    # Mostrar respuesta
                    console.print("\n[bold green]✅ Respuesta del Bot:[/bold green]")

                    if "result" in result and isinstance(result["result"], dict):
                        bot_message = result["result"].get("message", "Sin respuesta")
                        domain = result.get("domain", "unknown")
                        method = result.get("method", "unknown")

                        console.print(Panel(bot_message, title=f"Bot Response - Domain: {domain}"))
                        console.print(f"[dim]Routing: {method}[/dim]")
                    else:
                        console.print(json.dumps(result, indent=2))

                    return result
                else:
                    console.print(f"[bold red]❌ Error {response.status_code}:[/bold red]")
                    console.print(response.text)
                    return {"status": "error", "code": response.status_code}

        except Exception as e:
            console.print(f"[bold red]❌ Exception:[/bold red] {str(e)}")
            return {"status": "error", "message": str(e)}

    async def run_scenario(self, scenario_name: str, messages: List[str], wa_id: str = "1234567890"):
        """
        Ejecuta un escenario de prueba completo

        Args:
            scenario_name: Nombre del escenario
            messages: Lista de mensajes a enviar
            wa_id: WhatsApp ID del usuario
        """
        console.print(Panel(f"[bold yellow]🎯 Ejecutando Escenario: {scenario_name}[/bold yellow]"))

        for i, message in enumerate(messages, 1):
            console.print(f"\n[bold]Paso {i}/{len(messages)}[/bold]")
            await self.send_message(message, wa_id=wa_id)

            if i < len(messages):
                await asyncio.sleep(1)  # Pausa entre mensajes

        console.print(f"\n[bold green]✅ Escenario '{scenario_name}' completado[/bold green]\n")

    def show_scenarios(self) -> Dict[str, Dict]:
        """Muestra los escenarios de prueba disponibles"""
        scenarios = {
            "1": {
                "name": "Consulta de Productos (E-commerce)",
                "messages": ["¿Qué laptops tienen disponibles?"],
                "wa_id": "5491112345678",  # Argentina (e-commerce)
            },
            "2": {
                "name": "Tracking de Pedido (E-commerce)",
                "messages": ["Hola", "¿Dónde está mi pedido #12345?"],
                "wa_id": "5491112345678",
            },
            "3": {
                "name": "Soporte Técnico (E-commerce)",
                "messages": ["Mi producto llegó dañado", "¿Qué puedo hacer?"],
                "wa_id": "5491112345678",
            },
            "4": {
                "name": "Consulta de Factura (Multi-dominio)",
                "messages": ["¿Puedo ver mi última factura?"],
                "wa_id": "5491112345678",
            },
            "5": {
                "name": "Consulta Médica (Hospital)",
                "messages": ["Necesito agendar una cita con el Dr. García"],
                "wa_id": "5491187654321",  # Diferente número (hospital)
            },
            "6": {
                "name": "Estado de Cuenta (Crédito)",
                "messages": ["¿Cuál es mi saldo pendiente?", "¿Cuándo vence mi cuota?"],
                "wa_id": "5491198765432",  # Diferente número (crédito)
            },
            "7": {
                "name": "Conversación Multi-turno (E-commerce)",
                "messages": [
                    "Hola",
                    "¿Qué productos tienen?",
                    "Busco una laptop",
                    "¿Cuál es la más barata?",
                    "Gracias, adiós",
                ],
                "wa_id": "5491112345678",
            },
            "8": {
                "name": "Test de Dominios Mixtos",
                "messages": [
                    "¿Tienen laptops?",  # E-commerce
                    "¿Cuándo puedo ver al doctor?",  # Hospital (cambio de contexto)
                    "¿Cuál es mi deuda?",  # Crédito (cambio de contexto)
                ],
                "wa_id": "5491112345678",
            },
        }

        table = Table(
            title="📋 Escenarios de Prueba WhatsApp",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("#", style="cyan", no_wrap=True)
        table.add_column("Escenario", style="yellow")
        table.add_column("Dominio", style="green")
        table.add_column("Mensajes", style="white")

        for num, scenario in scenarios.items():
            name = scenario["name"]
            domain = name.split("(")[1].replace(")", "") if "(" in name else "Multi"
            msg_count = len(scenario["messages"])
            msg_preview = scenario["messages"][0][:40] + "..." if len(scenario["messages"][0]) > 40 else scenario["messages"][0]

            table.add_row(num, name, domain, f"{msg_count} msgs - {msg_preview}")

        console.print(table)
        console.print("\n[bold cyan]Usa /run <número> para ejecutar un escenario[/bold cyan]\n")

        return scenarios

    async def run_interactive(self):
        """Modo interactivo del simulador"""
        console.print(
            Panel.fit(
                "[bold green]¡Bienvenido al Simulador de WhatsApp![/bold green]\n\n"
                "Este simulador envía mensajes al webhook de WhatsApp como si vinieran\n"
                "de un usuario real de WhatsApp. Útil para probar:\n"
                "  • Detección de dominio (e-commerce, hospital, crédito)\n"
                "  • Routing del Super Orchestrator\n"
                "  • Flujos completos de conversación\n\n"
                "Comandos disponibles:\n"
                "  • Escribe un mensaje para enviarlo\n"
                "  • /scenarios - Ver escenarios de prueba\n"
                "  • /run <número> - Ejecutar un escenario\n"
                "  • /user <wa_id> - Cambiar WhatsApp ID\n"
                "  • /help - Mostrar ayuda\n"
                "  • /quit - Salir",
                title="📱 WhatsApp Webhook Simulator",
                border_style="green",
            )
        )
        console.print()

        # Verificar que el servidor esté activo
        try:
            async with httpx.AsyncClient() as client:
                health = await client.get(f"{self.base_url}{API_V1_STR}/webhook/health")
                if health.status_code == 200:
                    console.print("[green]✅ Servidor activo y listo[/green]\n")
                else:
                    console.print("[yellow]⚠️ Servidor respondió con código no esperado[/yellow]\n")
        except Exception as e:
            console.print(f"[red]❌ No se pudo conectar al servidor: {e}[/red]")
            console.print(f"[yellow]Asegúrate de que el servidor esté corriendo en {self.base_url}[/yellow]\n")

        # Estado del simulador
        current_wa_id = "5491112345678"
        current_name = "Test User"

        # Mostrar escenarios
        scenarios = self.show_scenarios()

        while True:
            try:
                user_input = console.input("[bold yellow]WhatsApp > [/bold yellow]").strip()

                if not user_input:
                    continue

                # Comandos especiales
                if user_input in ["/quit", "/exit", "/q"]:
                    console.print("[bold green]👋 ¡Hasta luego![/bold green]")
                    break

                elif user_input == "/help":
                    console.print("\n[bold]Comandos Disponibles:[/bold]")
                    console.print("  /scenarios - Ver escenarios de prueba")
                    console.print("  /run <número> - Ejecutar un escenario")
                    console.print("  /user <wa_id> [nombre] - Cambiar usuario")
                    console.print("  /payload - Ver último payload generado")
                    console.print("  /quit - Salir\n")

                elif user_input == "/scenarios":
                    scenarios = self.show_scenarios()

                elif user_input.startswith("/run "):
                    scenario_num = user_input[5:].strip()
                    if scenario_num in scenarios:
                        scenario = scenarios[scenario_num]
                        await self.run_scenario(
                            scenario["name"],
                            scenario["messages"],
                            wa_id=scenario.get("wa_id", current_wa_id),
                        )
                    else:
                        console.print(f"[red]❌ Escenario '{scenario_num}' no encontrado[/red]\n")

                elif user_input.startswith("/user "):
                    parts = user_input[6:].strip().split(maxsplit=1)
                    current_wa_id = parts[0]
                    current_name = parts[1] if len(parts) > 1 else "Test User"
                    console.print(f"[green]✅ Usuario cambiado: {current_name} ({current_wa_id})[/green]\n")

                elif user_input.startswith("/payload"):
                    payload = self.generate_whatsapp_payload(
                        "Mensaje de ejemplo",
                        wa_id=current_wa_id,
                        name=current_name,
                    )
                    console.print(json.dumps(payload, indent=2))
                    console.print()

                else:
                    # Mensaje regular
                    await self.send_message(
                        user_input,
                        wa_id=current_wa_id,
                        name=current_name,
                    )

            except KeyboardInterrupt:
                console.print("\n[bold yellow]⚠️ Interrupción detectada[/bold yellow]")
                confirm = console.input("[yellow]¿Salir? (s/n): [/yellow]").strip().lower()
                if confirm in ["s", "y", "yes", "si", "sí"]:
                    console.print("[bold green]👋 ¡Hasta luego![/bold green]")
                    break

            except Exception as e:
                console.print(f"[bold red]❌ Error: {str(e)}[/bold red]")
                console.print("[yellow]Continuando...[/yellow]\n")


async def main():
    """Punto de entrada principal"""
    import argparse

    parser = argparse.ArgumentParser(description="WhatsApp Webhook Simulator")
    parser.add_argument(
        "--url",
        default="http://localhost:8001",
        help="Base URL del servidor (default: http://localhost:8001)",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        help="Ejecutar un escenario específico y salir (número del 1-8)",
    )
    parser.add_argument(
        "--message",
        type=str,
        help="Enviar un mensaje único y salir",
    )
    parser.add_argument(
        "--wa-id",
        default="5491112345678",
        help="WhatsApp ID del usuario (default: 5491112345678)",
    )

    args = parser.parse_args()

    simulator = WhatsAppSimulator(base_url=args.url)

    # Modo no interactivo: ejecutar escenario o mensaje
    if args.scenario:
        scenarios = {
            "1": {"name": "Productos", "messages": ["¿Qué laptops tienen?"], "wa_id": "5491112345678"},
            "2": {"name": "Tracking", "messages": ["¿Dónde está mi pedido #12345?"], "wa_id": "5491112345678"},
            "3": {"name": "Soporte", "messages": ["Mi producto llegó dañado"], "wa_id": "5491112345678"},
            "4": {"name": "Factura", "messages": ["¿Puedo ver mi factura?"], "wa_id": "5491112345678"},
            "5": {"name": "Hospital", "messages": ["Necesito una cita médica"], "wa_id": "5491187654321"},
            "6": {"name": "Crédito", "messages": ["¿Cuál es mi saldo?"], "wa_id": "5491198765432"},
            "7": {"name": "Multi-turno", "messages": ["Hola", "¿Qué laptops tienen?", "Gracias"], "wa_id": "5491112345678"},
            "8": {"name": "Multi-dominio", "messages": ["¿Tienen laptops?", "¿Cuándo veo al doctor?"], "wa_id": "5491112345678"},
        }

        if args.scenario in scenarios:
            scenario = scenarios[args.scenario]
            await simulator.run_scenario(scenario["name"], scenario["messages"], wa_id=scenario["wa_id"])
        else:
            console.print(f"[red]❌ Escenario '{args.scenario}' no válido. Use 1-8[/red]")

        return

    if args.message:
        await simulator.send_message(args.message, wa_id=args.wa_id)
        return

    # Modo interactivo
    await simulator.run_interactive()


if __name__ == "__main__":
    # Install rich if not available
    try:
        import rich  # noqa
    except ImportError:
        print("⚠️ Installing required package: rich")
        os.system(f"{sys.executable} -m pip install rich")
        print("✅ Package installed. Please run the script again.")
        sys.exit(0)

    asyncio.run(main())
