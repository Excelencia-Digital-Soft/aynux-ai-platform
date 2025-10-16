"""
Interactive Chat Testing Interface

This script provides an interactive command-line interface for testing
the chatbot with automatic LangSmith tracing.
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

console = Console()


class ChatTester:
    """Interactive chat testing interface"""

    def __init__(self):
        self.service = None
        self.session_id = None
        self.user_id = "test_user"
        self.message_count = 0
        self.tracer = None

    async def initialize(self):
        """Initialize the chat service and LangSmith"""
        from app.config.langsmith_config import get_tracer
        from app.config.langsmith_init import initialize_langsmith
        from app.services.langgraph_chatbot_service import LangGraphChatbotService

        console.print("[bold green]🚀 Inicializando Chat Tester...[/bold green]")

        # Initialize LangSmith
        console.print("   📊 Configurando LangSmith tracing...")
        initialize_langsmith(force=True)
        self.tracer = get_tracer()

        if self.tracer.config.tracing_enabled:
            console.print(f"   ✅ LangSmith activo - Proyecto: {self.tracer.config.project_name}")
            console.print(
                f"   🔗 Ver trazas: https://smith.langchain.com/o/default/projects/p/{self.tracer.config.project_name}"
            )
        else:
            console.print("   ⚠️ LangSmith desactivado - Ejecutando sin tracing")

        # Initialize chat service
        console.print("   🤖 Inicializando servicio de chat...")
        self.service = LangGraphChatbotService()
        await self.service.initialize()

        # Generate session ID
        self.session_id = f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        console.print(f"   ✅ Servicio listo!")
        console.print(f"   🔑 Session ID: {self.session_id}\n")

    async def send_message(self, message: str) -> dict:
        """Send a message and get response with tracing"""
        self.message_count += 1

        console.print(Panel(f"[bold cyan]Tú:[/bold cyan] {message}", expand=False))

        # Send message
        result = await self.service.process_chat_message(
            message=message,
            user_id=self.user_id,
            session_id=self.session_id,
            metadata={"test_mode": True, "message_number": self.message_count},
        )

        # Display response
        response = result.get("response", "No response")
        agent = result.get("agent_used", "unknown")
        time_ms = result.get("processing_time_ms", 0)

        console.print(Panel(f"[bold green]Bot ({agent}):[/bold green]\n{response}", expand=False))

        # Display metadata
        metadata_table = Table(title="Metadatos de Procesamiento", show_header=True, header_style="bold magenta")
        metadata_table.add_column("Campo", style="cyan")
        metadata_table.add_column("Valor", style="green")

        metadata_table.add_row("Agente Usado", agent)
        metadata_table.add_row("Tiempo de Procesamiento", f"{time_ms}ms")
        metadata_table.add_row("Requiere Humano", str(result.get("requires_human", False)))
        metadata_table.add_row("Conversación Completa", str(result.get("is_complete", False)))
        metadata_table.add_row("Session ID", self.session_id)
        metadata_table.add_row("Mensaje #", str(self.message_count))

        console.print(metadata_table)
        console.print()

        return result

    async def send_message_stream(self, message: str):
        """Send a message with streaming response"""
        self.message_count += 1

        console.print(Panel(f"[bold cyan]Tú:[/bold cyan] {message}", expand=False))
        console.print("[bold yellow]🔄 Procesando (streaming)...[/bold yellow]\n")

        current_agent = "unknown"
        full_response = ""

        async for event in self.service.process_chat_message_stream(
            message=message,
            user_id=self.user_id,
            session_id=self.session_id,
            metadata={"test_mode": True, "message_number": self.message_count, "streaming": True},
        ):
            event_type = event.event_type.value

            if event_type == "agent_start":
                current_agent = event.agent_current
                console.print(f"[bold blue]🤖 {event.message}[/bold blue]")

            elif event_type == "progress":
                progress_pct = int(event.progress * 100)
                console.print(f"[yellow]⏳ {event.message} ({progress_pct}%)[/yellow]")

            elif event_type == "complete":
                full_response = event.message
                console.print(f"\n[bold green]✅ {event.agent_current}[/bold green]")

            elif event_type == "error":
                console.print(f"[bold red]❌ Error: {event.message}[/bold red]")
                return

        # Display final response
        console.print(Panel(f"[bold green]Bot ({current_agent}):[/bold green]\n{full_response}", expand=False))
        console.print()

    def show_menu(self):
        """Show interactive menu"""
        menu = Table(title="🎯 Menú de Opciones", show_header=True, header_style="bold magenta")
        menu.add_column("Comando", style="cyan", no_wrap=True)
        menu.add_column("Descripción", style="white")

        menu.add_row("Escribe un mensaje", "Enviar mensaje normal")
        menu.add_row("/stream <mensaje>", "Enviar mensaje con streaming")
        menu.add_row("/scenarios", "Ver escenarios de prueba predefinidos")
        menu.add_row("/history", "Ver historial de conversación")
        menu.add_row("/traces", "Ver últimas trazas en LangSmith")
        menu.add_row("/stats", "Mostrar estadísticas de la sesión")
        menu.add_row("/clear", "Limpiar sesión actual")
        menu.add_row("/help", "Mostrar esta ayuda")
        menu.add_row("/quit o /exit", "Salir del chat tester")

        console.print(menu)
        console.print()

    async def show_scenarios(self):
        """Show predefined test scenarios"""
        scenarios = {
            "1": ("Consulta de productos", "¿Qué laptops tienen disponibles?"),
            "2": ("Tracking de pedido", "¿Dónde está mi pedido #12345?"),
            "3": ("Soporte técnico", "Mi producto llegó dañado, ¿qué hago?"),
            "4": ("Consulta de factura", "¿Puedo ver mi última factura?"),
            "5": ("Consulta de crédito", "¿Cuál es mi saldo pendiente?"),
            "6": ("Saludo", "Hola, buenos días"),
            "7": ("Despedida", "Gracias, adiós"),
            "8": ("Multi-turn", ["Hola", "¿Qué productos tienen?", "¿Cuál es el más barato?", "Gracias"]),
        }

        table = Table(title="📋 Escenarios de Prueba Predefinidos", show_header=True, header_style="bold magenta")
        table.add_column("#", style="cyan", no_wrap=True)
        table.add_column("Tipo", style="yellow")
        table.add_column("Mensaje(s)", style="white")

        for num, (tipo, mensaje) in scenarios.items():
            if isinstance(mensaje, list):
                msg_display = " → ".join(mensaje)
            else:
                msg_display = mensaje
            table.add_row(num, tipo, msg_display)

        console.print(table)
        console.print("\n[bold cyan]Usa /run <número> para ejecutar un escenario[/bold cyan]\n")

        return scenarios

    async def show_history(self):
        """Show conversation history"""
        console.print("[bold blue]📜 Obteniendo historial...[/bold blue]")

        history = await self.service.get_conversation_history_langgraph(user_number=self.session_id, limit=50)

        if "error" in history:
            console.print(f"[red]❌ Error: {history['error']}[/red]")
            return

        messages = history.get("messages", [])
        total = history.get("total_messages", 0)

        console.print(f"[green]✅ Total de mensajes: {total}[/green]\n")

        for msg in messages[-10:]:  # Show last 10
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:100]
            timestamp = msg.get("timestamp", "N/A")

            if role == "user":
                console.print(f"[cyan]👤 Usuario ({timestamp}):[/cyan] {content}")
            else:
                console.print(f"[green]🤖 Bot ({timestamp}):[/green] {content}")

        console.print()

    async def show_traces(self):
        """Show recent LangSmith traces"""
        if not self.tracer or not self.tracer.client:
            console.print("[yellow]⚠️ LangSmith no está disponible[/yellow]")
            return

        console.print("[bold blue]🔍 Obteniendo trazas recientes...[/bold blue]")

        try:
            runs = list(
                self.tracer.client.list_runs(
                    project_name=self.tracer.config.project_name, limit=10, order="-start_time"
                )
            )

            if not runs:
                console.print("[yellow]⚠️ No se encontraron trazas[/yellow]")
                return

            table = Table(title="🔗 Últimas Trazas en LangSmith", show_header=True, header_style="bold magenta")
            table.add_column("Nombre", style="cyan")
            table.add_column("Estado", style="white")
            table.add_column("Latencia", style="green")
            table.add_column("ID", style="blue")

            for run in runs[:5]:
                status = "✅ OK" if not run.error else f"❌ Error: {run.error}"
                latency = f"{run.latency:.2f}s" if run.latency else "N/A"
                run_id = str(run.id)[:12] + "..."

                table.add_row(run.name, status, latency, run_id)

            console.print(table)
            console.print(
                f"\n[cyan]🔗 Ver todas: https://smith.langchain.com/o/default/projects/p/{self.tracer.config.project_name}[/cyan]\n"
            )

        except Exception as e:
            console.print(f"[red]❌ Error obteniendo trazas: {str(e)}[/red]")

    async def show_stats(self):
        """Show session statistics"""
        table = Table(title="📊 Estadísticas de la Sesión", show_header=True, header_style="bold magenta")
        table.add_column("Métrica", style="cyan")
        table.add_column("Valor", style="green")

        table.add_row("Session ID", self.session_id)
        table.add_row("User ID", self.user_id)
        table.add_row("Mensajes Enviados", str(self.message_count))
        table.add_row(
            "LangSmith Activo", "✅ Sí" if self.tracer and self.tracer.config.tracing_enabled else "❌ No"
        )

        if self.tracer and self.tracer.config.tracing_enabled:
            table.add_row("Proyecto LangSmith", self.tracer.config.project_name)

        console.print(table)
        console.print()

    async def run_interactive(self):
        """Run interactive chat loop"""
        await self.initialize()

        console.print(
            Panel.fit(
                "[bold green]¡Bienvenido al Chat Tester Interactivo![/bold green]\n\n"
                "Este chat se conecta al mismo backend que WhatsApp.\n"
                "Todas las conversaciones se rastrean en LangSmith automáticamente.\n\n"
                "Escribe /help para ver los comandos disponibles.",
                title="🤖 Aynux Chat Tester",
                border_style="green",
            )
        )
        console.print()

        self.show_menu()

        # Predefined scenarios
        scenarios = await self.show_scenarios()

        while True:
            try:
                # Get user input
                user_input = console.input("[bold yellow]> [/bold yellow]").strip()

                if not user_input:
                    continue

                # Handle commands
                if user_input in ["/quit", "/exit"]:
                    console.print("[bold green]👋 ¡Hasta luego![/bold green]")
                    break

                elif user_input == "/help":
                    self.show_menu()

                elif user_input == "/scenarios":
                    scenarios = await self.show_scenarios()

                elif user_input == "/history":
                    await self.show_history()

                elif user_input == "/traces":
                    await self.show_traces()

                elif user_input == "/stats":
                    await self.show_stats()

                elif user_input == "/clear":
                    self.session_id = f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    self.message_count = 0
                    console.print(f"[green]✅ Sesión reiniciada: {self.session_id}[/green]\n")

                elif user_input.startswith("/stream "):
                    message = user_input[8:].strip()
                    if message:
                        await self.send_message_stream(message)

                elif user_input.startswith("/run "):
                    scenario_num = user_input[5:].strip()
                    if scenario_num in scenarios:
                        tipo, messages = scenarios[scenario_num]
                        console.print(f"[bold cyan]🎯 Ejecutando escenario: {tipo}[/bold cyan]\n")

                        if isinstance(messages, list):
                            for msg in messages:
                                await self.send_message(msg)
                                await asyncio.sleep(1)  # Pause between messages
                        else:
                            await self.send_message(messages)
                    else:
                        console.print(f"[red]❌ Escenario '{scenario_num}' no encontrado[/red]\n")

                else:
                    # Regular message
                    await self.send_message(user_input)

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
    """Main entry point"""
    tester = ChatTester()
    await tester.run_interactive()


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
