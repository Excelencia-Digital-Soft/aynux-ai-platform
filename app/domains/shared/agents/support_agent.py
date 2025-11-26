"""
Agente especializado en soporte tecnico y atencion al cliente
"""

import logging
from typing import Any

from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method

logger = logging.getLogger(__name__)


class SupportAgent(BaseAgent):
    """Agente especializado en soporte tecnico y resolucion de problemas"""

    def __init__(self, ollama=None, config: dict[str, Any] | None = None):
        super().__init__("support_agent", config or {}, ollama=ollama)

        # FAQ comun
        self.faq_responses = self._load_faq_responses()

    @trace_async_method(
        name="support_agent_process",
        run_type="chain",
        metadata={"agent_type": "support", "escalation_enabled": True},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Procesa consultas de soporte tecnico."""
        try:
            # Detectar tipo de problema
            problem_type = self._detect_problem_type(message)

            # Buscar en FAQ primero
            faq_response = self._search_faq(message, problem_type)

            if faq_response:
                response_text = faq_response
            else:
                # Generar respuesta personalizada
                response_text = self._generate_support_response(message, problem_type)

            # Determinar si necesita escalacion
            requires_human = self._needs_human_intervention(message, problem_type)

            return {
                "messages": [{"role": "assistant", "content": response_text}],
                "current_agent": self.name,
                "agent_history": [self.name],
                "retrieved_data": {"problem_type": problem_type},
                "requires_human": requires_human,
                "is_complete": not requires_human,
            }

        except Exception as e:
            logger.error(f"Error in support agent: {str(e)}")

            error_response = "Disculpa, encontre un problema procesando tu consulta. Podrias reformularla?"

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    def _detect_problem_type(self, message: str) -> str:
        """Detecta el tipo de problema del usuario."""
        message_lower = message.lower()

        problem_patterns = {
            "payment": ["pago", "tarjeta", "rechazada", "cobro", "debito", "credito"],
            "delivery": ["entrega", "demora", "tarde", "no llego", "perdido"],
            "product": ["defectuoso", "roto", "no funciona", "danado", "problema con"],
            "account": ["cuenta", "contrasena", "login", "acceso", "usuario"],
            "return": ["devolver", "devolucion", "cambio", "reembolso"],
            "technical": ["error", "bug", "no carga", "aplicacion", "sitio web"],
        }

        for problem_type, keywords in problem_patterns.items():
            if any(keyword in message_lower for keyword in keywords):
                return problem_type

        return "general"

    def _search_faq(self, message: str, problem_type: str) -> str | None:
        """Busca respuesta en FAQ."""
        message_lower = message.lower()

        # Buscar en FAQ del tipo de problema especifico
        if problem_type in self.faq_responses:
            for faq in self.faq_responses[problem_type]:
                if any(keyword in message_lower for keyword in faq["keywords"]):
                    return faq["response"]

        # Buscar en FAQ general
        if "general" in self.faq_responses:
            for faq in self.faq_responses["general"]:
                if any(keyword in message_lower for keyword in faq["keywords"]):
                    return faq["response"]

        return None

    def _generate_support_response(self, _: str, problem_type: str) -> str:
        """Genera respuesta de soporte personalizada."""
        responses = {
            "payment": """Entiendo que tienes problemas con el pago. Te puedo ayudar con:

1. **Verificar el estado del pago**
2. **Revisar metodos de pago disponibles**
3. **Solucionar errores de tarjeta**

Por favor, indicame especificamente que problema estas teniendo.""",
            "delivery": """Lamento que tengas problemas con la entrega. Puedo ayudarte a:

1. **Rastrear tu pedido** (necesitare el numero de orden)
2. **Reprogramar la entrega**
3. **Reportar un paquete perdido**

Cual es tu numero de orden?""",
            "product": """Siento mucho que hayas tenido problemas con el producto. Te ayudare a resolverlo.

Opciones disponibles:
- **Solicitar cambio o devolucion**
- **Obtener soporte tecnico**
- **Consultar garantia**

Podrias describir el problema especifico que estas teniendo?""",
            "account": """Te ayudare con tu problema de cuenta. Puedo asistirte con:

- **Recuperar contrasena**
- **Actualizar informacion personal**
- **Resolver problemas de acceso**

Que necesitas especificamente?""",
            "return": """Te ayudare con el proceso de devolucion.

**Politica de devoluciones:**
- 30 dias desde la recepcion
- Producto en condiciones originales
- Con empaque original

Tienes el numero de orden del producto que deseas devolver?""",
            "technical": """Entiendo que estas experimentando problemas tecnicos. Para ayudarte mejor:

1. En que dispositivo ocurre el problema? (movil/computadora)
2. Que navegador/app estas usando?
3. Cuando comenzo el problema?

Mientras tanto, puedes intentar:
- Limpiar cache y cookies
- Actualizar la aplicacion
- Reiniciar el dispositivo""",
            "general": """Estoy aqui para ayudarte. Puedo asistirte con:

- Problemas con pedidos
- Consultas de pago
- Seguimiento de envios
- Soporte tecnico
- Devoluciones y cambios
- Problemas de cuenta

En que puedo ayudarte especificamente?""",
        }

        return responses.get(problem_type, responses["general"])

    def _needs_human_intervention(self, message: str, problem_type: str) -> bool:
        """Determina si el caso requiere intervencion humana."""
        message_lower = message.lower()

        # Palabras que indican necesidad de escalacion
        escalation_keywords = [
            "hablar con humano",
            "agente real",
            "persona real",
            "supervisor",
            "gerente",
            "muy urgente",
            "emergencia",
            "legal",
            "abogado",
            "denuncia",
            "estafa",
            "fraude",
        ]

        # Tipos de problema que tipicamente requieren humano
        human_required_types = ["legal", "fraud", "complex_technical"]

        return (
            any(keyword in message_lower for keyword in escalation_keywords)
            or problem_type in human_required_types
            or len(message) > 500  # Mensajes muy largos suelen ser complejos
        )

    def _load_faq_responses(self) -> dict[str, list[dict[str, Any]]]:
        """Carga respuestas FAQ predefinidas."""
        return {
            "payment": [
                {
                    "keywords": ["tarjeta rechazada", "pago rechazado"],
                    "response": """Tu tarjeta fue rechazada. Esto puede deberse a:

- **Fondos insuficientes**
- **Limite de credito alcanzado**
- **Tarjeta vencida**
- **Datos incorrectos**

Por favor, verifica estos puntos o intenta con otro metodo de pago.""",
                },
                {
                    "keywords": ["metodos de pago", "formas de pago"],
                    "response": """Aceptamos los siguientes metodos de pago:

**Tarjetas**: Visa, Mastercard, American Express
**Transferencia bancaria**
**Mercado Pago**
**Billeteras digitales**: PayPal

Todos los pagos son 100% seguros.""",
                },
            ],
            "delivery": [
                {
                    "keywords": ["tiempo de entrega", "cuanto tarda"],
                    "response": """Los tiempos de entrega son:

- **CABA**: 24-48 horas
- **GBA**: 48-72 horas
- **Interior**: 3-7 dias habiles

Los tiempos pueden variar segun disponibilidad y metodo de envio elegido.""",
                }
            ],
            "general": [
                {
                    "keywords": ["horario", "atencion"],
                    "response": """Nuestros horarios de atencion son:

**Lunes a Viernes**: 9:00 - 18:00
**Sabados**: 9:00 - 13:00
**Domingos y feriados**: Cerrado

Puedes dejarnos tu consulta y te responderemos a la brevedad.""",
                }
            ],
        }
