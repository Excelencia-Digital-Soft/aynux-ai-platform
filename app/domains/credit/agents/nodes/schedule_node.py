"""
Schedule Node - Credit domain node for payment schedules.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method

logger = logging.getLogger(__name__)


class ScheduleNode(BaseAgent):
    """Credit node specialized in payment schedules and planning."""

    def __init__(self, llm=None, config: dict[str, Any] | None = None):
        super().__init__("schedule_node", config or {}, llm=llm)

    @trace_async_method(
        name="schedule_node_process",
        run_type="chain",
        metadata={"agent_type": "schedule_node", "domain": "credit"},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Process payment schedule queries."""
        try:
            credit_account_id = state_dict.get("credit_account_id")

            if not credit_account_id:
                return self._handle_no_account()

            # Detect query type
            query_type = self._detect_query_type(message)

            if query_type == "full_schedule":
                response_text = self._handle_full_schedule(credit_account_id)
            elif query_type == "next_payment":
                response_text = self._handle_next_payment(credit_account_id)
            elif query_type == "modify_schedule":
                response_text = self._handle_modify_schedule()
            else:
                response_text = self._handle_general_schedule_query(credit_account_id)

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "retrieved_data": {
                    "query_type": query_type,
                    "credit_account_id": credit_account_id,
                },
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in schedule node: {str(e)}")

            error_response = (
                "Disculpa, tuve un problema consultando tu calendario de pagos. "
                "Por favor intenta de nuevo."
            )

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    def _detect_query_type(self, message: str) -> str:
        """Detect the type of schedule query."""
        message_lower = message.lower()

        query_patterns = {
            "full_schedule": ["calendario", "todos los pagos", "plan de pagos", "cronograma"],
            "next_payment": ["proximo pago", "siguiente pago", "cuando debo pagar"],
            "modify_schedule": ["cambiar fecha", "modificar", "reprogramar", "adelantar"],
        }

        for query_type, keywords in query_patterns.items():
            if any(keyword in message_lower for keyword in keywords):
                return query_type

        return "general"

    def _handle_no_account(self) -> dict[str, Any]:
        """Handle when no credit account is found."""
        response = """**Calendario de Pagos**

Para mostrar tu calendario necesito identificar tu cuenta.

Por favor proporciona:
- Tu número de cuenta
- O tu número de cliente

¿Cuál es tu información?"""

        return {
            "messages": [{"role": "assistant", "content": response}],
            "current_agent": self.name,
            "agent_history": [self.name],
            "is_complete": False,
        }

    def _handle_full_schedule(self, account_id: str) -> str:
        """Handle full payment schedule request."""
        _ = account_id  # unused in simulation

        # Generate simulated schedule
        schedule = self._generate_schedule(6)

        response = """**Calendario de Pagos**

**Próximos 6 meses:**

"""
        for payment in schedule:
            status = "[PENDING]" if payment["status"] == "pending" else "[PAID]"
            response += f"""{payment["number"]}. **{payment["due_date"]}**
   Monto: ${payment["amount"]:,.2f}
   {status} {payment["status"].capitalize()}

"""

        response += """**Resumen:**
- Total a pagar: $15,000.00
- Pagos restantes: 6
- Fecha de liquidación: Junio 2025

¿Deseas modificar alguna fecha de pago?"""

        return response

    def _handle_next_payment(self, account_id: str) -> str:
        """Handle next payment query."""
        _ = account_id  # unused in simulation

        next_date = (datetime.now() + timedelta(days=15)).strftime("%d/%m/%Y")

        return f"""**Próximo Pago**

[UPCOMING] **Fecha de vencimiento:** {next_date}

**Detalles:**
- Pago mínimo: $2,500.00
- Pago para no generar intereses: $15,000.00
- Días restantes: 15 días

**Opciones de pago:**
1. Pago en línea - Inmediato
2. Domiciliación - Automático
3. Pago en tienda - Genera referencia

**Recordatorio:**
Te enviaremos notificación 3 días antes del vencimiento.

¿Deseas realizar el pago ahora?"""

    def _handle_modify_schedule(self) -> str:
        """Handle schedule modification request."""
        return """**Modificar Calendario de Pagos**

**Opciones disponibles:**

1. **Cambiar fecha de corte**
   - Disponible: día 1, 10, 15, 20 de cada mes
   - Sin costo adicional
   - Aplica desde el siguiente mes

2. **Adelantar pagos**
   - Reduce intereses
   - Sin penalización
   - Pago mínimo no requerido

3. **Plan de reestructura**
   - Ampliar plazo
   - Reducir monto mensual
   - Requiere evaluación

4. **Domiciliación bancaria**
   - Cargo automático
   - Evita olvidos
   - Beneficios exclusivos

¿Qué modificación te interesa?"""

    def _handle_general_schedule_query(self, account_id: str) -> str:
        """Handle general schedule queries."""
        _ = account_id  # unused

        return """**Centro de Pagos Programados**

¿En qué puedo ayudarte?

- **Ver calendario completo** - Todos tus pagos
- **Próximo pago** - Fecha y monto
- **Modificar fechas** - Cambiar día de pago
- **Configurar recordatorios** - Alertas antes del vencimiento

¿Qué necesitas consultar?"""

    def _generate_schedule(self, months: int) -> list[dict[str, Any]]:
        """Generate simulated payment schedule."""
        schedule = []
        base_date = datetime.now()

        for i in range(months):
            payment_date = base_date + timedelta(days=(i + 1) * 30)
            schedule.append(
                {
                    "number": i + 1,
                    "due_date": payment_date.strftime("%d/%m/%Y"),
                    "amount": 2500.00,
                    "status": "pending" if i > 0 else "upcoming",
                }
            )

        return schedule


# Alias for backward compatibility
ScheduleAgent = ScheduleNode
