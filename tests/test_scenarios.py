"""
Comprehensive Test Scenarios for Aynux Bot

This module contains predefined test scenarios to validate
different agent behaviors, routing decisions, and conversation flows.
"""

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

console = Console()


@dataclass
class TestScenario:
    """Test scenario configuration"""

    id: str
    name: str
    description: str
    messages: List[str]
    expected_agents: List[str]
    expected_outcomes: Dict[str, Any]
    tags: List[str]


# Define test scenarios
SCENARIOS = [
    TestScenario(
        id="product_query_simple",
        name="Consulta Simple de Productos",
        description="Usuario pregunta por productos disponibles de forma genérica",
        messages=["Hola, ¿qué productos tienen disponibles?"],
        expected_agents=["product_agent"],
        expected_outcomes={"should_list_products": True, "should_show_categories": True},
        tags=["products", "simple", "listing"],
    ),
    TestScenario(
        id="product_query_specific",
        name="Búsqueda Específica de Producto",
        description="Usuario busca un producto específico por nombre o características",
        messages=["¿Tienen laptops Dell disponibles?", "Busco una notebook gamer con RTX 4060"],
        expected_agents=["product_agent", "product_agent"],
        expected_outcomes={"should_show_specific_products": True, "should_filter_by_specs": True},
        tags=["products", "search", "filtering"],
    ),
    TestScenario(
        id="category_navigation",
        name="Navegación por Categorías",
        description="Usuario navega por categorías de productos",
        messages=[
            "¿Qué categorías de productos tienen?",
            "Muéstrame los productos de la categoría laptops",
            "¿Y componentes de PC?",
        ],
        expected_agents=["category_agent", "category_agent", "category_agent"],
        expected_outcomes={"should_show_categories": True, "should_navigate_hierarchy": True},
        tags=["categories", "navigation", "browsing"],
    ),
    TestScenario(
        id="order_tracking",
        name="Seguimiento de Pedido",
        description="Usuario consulta el estado de su pedido",
        messages=["¿Dónde está mi pedido?", "Quiero rastrear mi pedido #12345", "¿Cuándo llega mi compra?"],
        expected_agents=["tracking_agent", "tracking_agent", "tracking_agent"],
        expected_outcomes={"should_request_order_number": True, "should_show_tracking_info": True},
        tags=["tracking", "orders", "status"],
    ),
    TestScenario(
        id="customer_support",
        name="Soporte al Cliente",
        description="Usuario solicita ayuda o reporta un problema",
        messages=[
            "Mi producto llegó dañado",
            "Necesito hacer una devolución",
            "¿Cómo puedo cambiar un producto defectuoso?",
        ],
        expected_agents=["support_agent", "support_agent", "support_agent"],
        expected_outcomes={"should_offer_help": True, "should_provide_instructions": True},
        tags=["support", "returns", "complaints"],
    ),
    TestScenario(
        id="invoice_credit_query",
        name="Consultas de Facturación y Crédito",
        description="Usuario pregunta sobre facturas o saldo pendiente",
        messages=[
            "¿Puedo ver mi última factura?",
            "¿Cuál es mi saldo pendiente?",
            "Necesito una copia de la factura del mes pasado",
        ],
        expected_agents=["credit_agent", "credit_agent", "credit_agent"],
        expected_outcomes={"should_show_invoice_info": True, "should_show_balance": True},
        tags=["credit", "invoicing", "billing"],
    ),
    TestScenario(
        id="promotions_query",
        name="Consulta de Promociones",
        description="Usuario pregunta por ofertas y descuentos",
        messages=["¿Qué ofertas tienen?", "¿Hay descuentos en laptops?", "Quiero ver las promociones vigentes"],
        expected_agents=["promotions_agent", "promotions_agent", "promotions_agent"],
        expected_outcomes={"should_show_promotions": True, "should_filter_by_category": True},
        tags=["promotions", "offers", "discounts"],
    ),
    TestScenario(
        id="greeting_farewell",
        name="Saludos y Despedidas",
        description="Interacciones de cortesía",
        messages=["Hola", "Buenos días", "Gracias", "Adiós", "Hasta luego"],
        expected_agents=["greeting_agent", "greeting_agent", "farewell_agent", "farewell_agent", "farewell_agent"],
        expected_outcomes={"should_greet_user": True, "should_say_goodbye": True},
        tags=["greeting", "farewell", "courtesy"],
    ),
    TestScenario(
        id="multi_turn_product_purchase",
        name="Conversación Multi-Turno: Compra de Producto",
        description="Flujo completo de consulta, comparación y decisión de compra",
        messages=[
            "Hola",
            "¿Qué laptops tienen?",
            "¿Cuál es la más barata?",
            "¿Y la más potente?",
            "Quiero comprar la Dell XPS 15",
            "¿Cómo puedo pagar?",
            "Perfecto, gracias",
        ],
        expected_agents=[
            "greeting_agent",
            "product_agent",
            "product_agent",
            "product_agent",
            "product_agent",
            "support_agent",
            "farewell_agent",
        ],
        expected_outcomes={
            "should_maintain_context": True,
            "should_filter_products": True,
            "should_provide_payment_info": True,
        },
        tags=["multi-turn", "purchase", "end-to-end"],
    ),
    TestScenario(
        id="ambiguous_query",
        name="Consulta Ambigua",
        description="Consulta que podría ser interpretada de múltiples formas",
        messages=["¿Tienen stock?", "Info", "Quiero saber más"],
        expected_agents=["fallback_agent", "fallback_agent", "fallback_agent"],
        expected_outcomes={"should_ask_clarification": True, "should_offer_options": True},
        tags=["ambiguous", "fallback", "clarification"],
    ),
    TestScenario(
        id="price_comparison",
        name="Comparación de Precios",
        description="Usuario compara precios entre diferentes productos",
        messages=[
            "¿Cuánto cuestan las laptops?",
            "¿Cuál es la diferencia de precio entre Dell y HP?",
            "Muéstrame las opciones más económicas",
        ],
        expected_agents=["product_agent", "product_agent", "product_agent"],
        expected_outcomes={"should_show_prices": True, "should_compare_options": True},
        tags=["products", "pricing", "comparison"],
    ),
    TestScenario(
        id="specifications_query",
        name="Consulta de Especificaciones Técnicas",
        description="Usuario pregunta por detalles técnicos específicos",
        messages=[
            "¿Qué procesador tiene la Dell XPS 15?",
            "¿Cuánta RAM tiene?",
            "¿Viene con SSD o HDD?",
            "¿Qué tarjeta gráfica trae?",
        ],
        expected_agents=["product_agent", "product_agent", "product_agent", "product_agent"],
        expected_outcomes={"should_show_specifications": True, "should_maintain_product_context": True},
        tags=["products", "specifications", "technical"],
    ),
    TestScenario(
        id="availability_stock",
        name="Consulta de Disponibilidad",
        description="Usuario pregunta si productos están en stock",
        messages=[
            "¿Tienen stock de la Dell XPS 15?",
            "¿Cuándo van a recibir más unidades?",
            "¿Puedo reservar una?",
        ],
        expected_agents=["product_agent", "product_agent", "support_agent"],
        expected_outcomes={"should_check_stock": True, "should_offer_reservation": True},
        tags=["products", "stock", "availability"],
    ),
    TestScenario(
        id="shipping_delivery",
        name="Consultas de Envío y Entrega",
        description="Usuario pregunta sobre opciones de envío",
        messages=[
            "¿Hacen envíos a domicilio?",
            "¿Cuánto cuesta el envío?",
            "¿En cuánto tiempo llega?",
            "¿Puedo retirarlo en tienda?",
        ],
        expected_agents=["support_agent", "support_agent", "support_agent", "support_agent"],
        expected_outcomes={"should_show_shipping_options": True, "should_show_delivery_time": True},
        tags=["shipping", "delivery", "logistics"],
    ),
    TestScenario(
        id="payment_methods",
        name="Consulta de Métodos de Pago",
        description="Usuario pregunta sobre formas de pago disponibles",
        messages=[
            "¿Qué formas de pago aceptan?",
            "¿Puedo pagar en cuotas?",
            "¿Aceptan tarjetas de crédito?",
            "¿Tienen financiación?",
        ],
        expected_agents=["support_agent", "support_agent", "support_agent", "credit_agent"],
        expected_outcomes={"should_show_payment_methods": True, "should_show_financing_options": True},
        tags=["payment", "financing", "credit"],
    ),
    TestScenario(
        id="warranty_returns",
        name="Consultas de Garantía y Devoluciones",
        description="Usuario pregunta sobre políticas de garantía",
        messages=[
            "¿Qué garantía tienen los productos?",
            "¿Cuánto tiempo tengo para hacer una devolución?",
            "¿Qué pasa si el producto viene defectuoso?",
        ],
        expected_agents=["support_agent", "support_agent", "support_agent"],
        expected_outcomes={"should_explain_warranty": True, "should_explain_return_policy": True},
        tags=["warranty", "returns", "policy"],
    ),
]


class ScenarioRunner:
    """Test scenario executor"""

    def __init__(self):
        self.service = None
        self.results = []

    async def initialize(self):
        """Initialize chat service"""
        from app.config.langsmith_init import initialize_langsmith
        from app.services.langgraph_chatbot_service import LangGraphChatbotService

        console.print("[bold green]🚀 Initializing Scenario Runner...[/bold green]")

        # Initialize LangSmith
        initialize_langsmith(force=True)

        # Initialize chat service
        self.service = LangGraphChatbotService()
        await self.service.initialize()

        console.print("[bold green]✅ Service ready![/bold green]\n")

    async def run_scenario(self, scenario: TestScenario) -> Dict[str, Any]:
        """Execute a single test scenario"""
        console.print(f"[bold cyan]🧪 Running: {scenario.name}[/bold cyan]")
        console.print(f"   {scenario.description}\n")

        session_id = f"scenario_{scenario.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        agents_used = []
        responses = []
        errors = []
        total_time = 0

        for i, message in enumerate(scenario.messages, 1):
            console.print(f"   [{i}/{len(scenario.messages)}] User: {message}")

            try:
                result = await self.service.process_chat_message(
                    message=message,
                    user_id=f"scenario_user_{scenario.id}",
                    session_id=session_id,
                    metadata={"scenario_id": scenario.id, "message_index": i},
                )

                agent = result.get("agent_used", "unknown")
                response = result.get("response", "")
                time_ms = result.get("processing_time_ms", 0)

                agents_used.append(agent)
                responses.append(response)
                total_time += time_ms

                console.print(f"   [{i}/{len(scenario.messages)}] Bot ({agent}): {response[:100]}...")
                console.print(f"   [{i}/{len(scenario.messages)}] Time: {time_ms}ms\n")

            except Exception as e:
                errors.append({"message": message, "error": str(e)})
                console.print(f"   [bold red]❌ Error: {str(e)}[/bold red]\n")

        # Validate results
        validation = self._validate_scenario(scenario, agents_used, responses, errors)

        result = {
            "scenario_id": scenario.id,
            "scenario_name": scenario.name,
            "success": validation["passed"],
            "agents_used": agents_used,
            "expected_agents": scenario.expected_agents,
            "agents_match": validation["agents_match"],
            "responses": responses,
            "errors": errors,
            "total_time_ms": total_time,
            "avg_time_ms": total_time / len(scenario.messages) if scenario.messages else 0,
            "validation": validation,
            "timestamp": datetime.now().isoformat(),
        }

        self.results.append(result)
        return result

    def _validate_scenario(
        self, scenario: TestScenario, agents_used: List[str], responses: List[str], errors: List[Dict]
    ) -> Dict[str, Any]:
        """Validate scenario execution results"""

        # Check if agents match expected
        agents_match = agents_used == scenario.expected_agents

        # Check if there are errors
        has_errors = len(errors) > 0

        # Check if all messages got responses
        all_responded = len(responses) == len(scenario.messages)

        # Overall pass/fail
        passed = agents_match and not has_errors and all_responded

        return {
            "passed": passed,
            "agents_match": agents_match,
            "agents_used": agents_used,
            "expected_agents": scenario.expected_agents,
            "has_errors": has_errors,
            "error_count": len(errors),
            "all_responded": all_responded,
            "response_count": len(responses),
            "expected_count": len(scenario.messages),
        }

    def display_summary(self):
        """Display test execution summary"""
        console.print("\n" + "=" * 80)
        console.print("[bold green]📊 TEST EXECUTION SUMMARY[/bold green]")
        console.print("=" * 80 + "\n")

        # Overall statistics
        total = len(self.results)
        passed = sum(1 for r in self.results if r["success"])
        failed = total - passed

        console.print(f"[bold]Total Scenarios:[/bold] {total}")
        console.print(f"[bold green]Passed:[/bold green] {passed}")
        console.print(f"[bold red]Failed:[/bold red] {failed}")
        console.print(f"[bold cyan]Success Rate:[/bold cyan] {(passed/total*100) if total > 0 else 0:.1f}%\n")

        # Results table
        table = Table(title="Scenario Results", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="white")
        table.add_column("Status", style="white")
        table.add_column("Agents Match", style="white")
        table.add_column("Avg Time (ms)", style="green")

        for result in self.results:
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            agents_match = "✅" if result["agents_match"] else "❌"

            table.add_row(
                result["scenario_id"],
                result["scenario_name"][:40],
                status,
                agents_match,
                f"{result['avg_time_ms']:.0f}",
            )

        console.print(table)

        # Failed scenarios details
        if failed > 0:
            console.print("\n[bold red]❌ FAILED SCENARIOS DETAILS:[/bold red]\n")

            for result in self.results:
                if not result["success"]:
                    console.print(f"[bold red]Scenario:[/bold red] {result['scenario_name']}")
                    console.print(f"  Expected agents: {result['expected_agents']}")
                    console.print(f"  Actual agents:   {result['agents_used']}")

                    if result["errors"]:
                        console.print(f"  Errors:")
                        for err in result["errors"]:
                            console.print(f"    - {err['message']}: {err['error']}")

                    console.print()

    def save_results(self, filename: str = "test_results.json"):
        """Save results to JSON file"""
        filepath = os.path.join(os.path.dirname(__file__), filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        console.print(f"\n[bold green]💾 Results saved to: {filepath}[/bold green]")


async def run_all_scenarios():
    """Run all test scenarios"""
    runner = ScenarioRunner()
    await runner.initialize()

    console.print(f"[bold cyan]Running {len(SCENARIOS)} test scenarios...[/bold cyan]\n")

    for i, scenario in enumerate(SCENARIOS, 1):
        console.print(f"[bold yellow]{'='*80}[/bold yellow]")
        console.print(f"[bold yellow]Scenario {i}/{len(SCENARIOS)}[/bold yellow]")
        console.print(f"[bold yellow]{'='*80}[/bold yellow]\n")

        await runner.run_scenario(scenario)

        # Brief pause between scenarios
        await asyncio.sleep(1)

    runner.display_summary()
    runner.save_results()


async def run_scenario_by_id(scenario_id: str):
    """Run a specific scenario by ID"""
    scenario = next((s for s in SCENARIOS if s.id == scenario_id), None)

    if not scenario:
        console.print(f"[bold red]❌ Scenario '{scenario_id}' not found![/bold red]")
        return

    runner = ScenarioRunner()
    await runner.initialize()

    await runner.run_scenario(scenario)
    runner.display_summary()


async def run_scenarios_by_tag(tag: str):
    """Run all scenarios with a specific tag"""
    matching = [s for s in SCENARIOS if tag in s.tags]

    if not matching:
        console.print(f"[bold red]❌ No scenarios found with tag '{tag}'![/bold red]")
        return

    console.print(f"[bold cyan]Found {len(matching)} scenario(s) with tag '{tag}'[/bold cyan]\n")

    runner = ScenarioRunner()
    await runner.initialize()

    for scenario in matching:
        await runner.run_scenario(scenario)
        await asyncio.sleep(1)

    runner.display_summary()
    runner.save_results(f"test_results_{tag}.json")


def list_scenarios():
    """List all available scenarios"""
    table = Table(title="Available Test Scenarios", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="white")
    table.add_column("Messages", style="green")
    table.add_column("Tags", style="yellow")

    for scenario in SCENARIOS:
        table.add_row(scenario.id, scenario.name, str(len(scenario.messages)), ", ".join(scenario.tags))

    console.print(table)


async def main():
    """Main entry point"""
    import sys

    if len(sys.argv) < 2:
        console.print("[bold yellow]Usage:[/bold yellow]")
        console.print("  python test_scenarios.py all           - Run all scenarios")
        console.print("  python test_scenarios.py list          - List all scenarios")
        console.print("  python test_scenarios.py run <id>      - Run specific scenario")
        console.print("  python test_scenarios.py tag <tag>     - Run scenarios with tag")
        console.print("\nExample:")
        console.print("  python test_scenarios.py run product_query_simple")
        console.print("  python test_scenarios.py tag products")
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "all":
        await run_all_scenarios()

    elif command == "list":
        list_scenarios()

    elif command == "run" and len(sys.argv) > 2:
        scenario_id = sys.argv[2]
        await run_scenario_by_id(scenario_id)

    elif command == "tag" and len(sys.argv) > 2:
        tag = sys.argv[2]
        await run_scenarios_by_tag(tag)

    else:
        console.print("[bold red]❌ Invalid command![/bold red]")
        console.print("Run 'python test_scenarios.py' for usage help")


if __name__ == "__main__":
    asyncio.run(main())
