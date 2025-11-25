"""
Agente especializado en soporte técnico y atención al cliente
"""

import logging
from typing import Any, Dict, List, Optional

from ..utils.tracing import trace_async_method
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class SupportAgent(BaseAgent):
    """Agente especializado en soporte técnico y resolución de problemas"""

    def __init__(self, ollama=None, config: Optional[Dict[str, Any]] = None):
        super().__init__("support_agent", config or {}, ollama=ollama)

        # FAQ común
        self.faq_responses = self._load_faq_responses()

    @trace_async_method(
        name="support_agent_process",
        run_type="chain",
        metadata={"agent_type": "support", "escalation_enabled": True},
        extract_state=True,
    )
    async def _process_internal(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Procesa consultas de soporte técnico."""
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

            # Determinar si necesita escalación
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

            error_response = "Disculpa, encontré un problema procesando tu consulta. ¿Podrías reformularla?"

            return {
                "messages": [{"role": "assistant", "content": error_response}],
                "error_count": state_dict.get("error_count", 0) + 1,
                "current_agent": self.name,
            }

    def _detect_problem_type(self, message: str) -> str:
        """Detecta el tipo de problema del usuario."""
        message_lower = message.lower()

        problem_patterns = {
            "payment": ["pago", "tarjeta", "rechazada", "cobro", "débito", "crédito"],
            "delivery": ["entrega", "demora", "tarde", "no llegó", "perdido"],
            "product": ["defectuoso", "roto", "no funciona", "dañado", "problema con"],
            "account": ["cuenta", "contraseña", "login", "acceso", "usuario"],
            "return": ["devolver", "devolución", "cambio", "reembolso"],
            "technical": ["error", "bug", "no carga", "aplicación", "sitio web"],
        }

        for problem_type, keywords in problem_patterns.items():
            if any(keyword in message_lower for keyword in keywords):
                return problem_type

        return "general"

    def _search_faq(self, message: str, problem_type: str) -> Optional[str]:
        """Busca respuesta en FAQ."""
        message_lower = message.lower()

        # Buscar en FAQ del tipo de problema específico
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
2. **Revisar métodos de pago disponibles**
3. **Solucionar errores de tarjeta**

Por favor, indícame específicamente qué problema estás teniendo.""",
            "delivery": """Lamento que tengas problemas con la entrega. Puedo ayudarte a:

1. **Rastrear tu pedido** (necesitaré el número de orden)
2. **Reprogramar la entrega**
3. **Reportar un paquete perdido**

¿Cuál es tu número de orden?""",
            "product": """Siento mucho que hayas tenido problemas con el producto. Te ayudaré a resolverlo.

Opciones disponibles:
• **Solicitar cambio o devolución**
• **Obtener soporte técnico**
• **Consultar garantía**

¿Podrías describir el problema específico que estás teniendo?""",
            "account": """Te ayudaré con tu problema de cuenta. Puedo asistirte con:

• **Recuperar contraseña**
• **Actualizar información personal**
• **Resolver problemas de acceso**

¿Qué necesitas específicamente?""",
            "return": """Te ayudaré con el proceso de devolución. 

**Política de devoluciones:**
• 30 días desde la recepción
• Producto en condiciones originales
• Con empaque original

¿Tienes el número de orden del producto que deseas devolver?""",
            "technical": """Entiendo que estás experimentando problemas técnicos. Para ayudarte mejor:

1. ¿En qué dispositivo ocurre el problema? (móvil/computadora)
2. ¿Qué navegador/app estás usando?
3. ¿Cuándo comenzó el problema?

Mientras tanto, puedes intentar:
• Limpiar caché y cookies
• Actualizar la aplicación
• Reiniciar el dispositivo""",
            "general": """Estoy aquí para ayudarte. Puedo asistirte con:

• 🛒 Problemas con pedidos
• 💳 Consultas de pago
• 📦 Seguimiento de envíos
• 🔧 Soporte técnico
• ↩️ Devoluciones y cambios
• 👤 Problemas de cuenta

¿En qué puedo ayudarte específicamente?""",
        }

        return responses.get(problem_type, responses["general"])

    def _needs_human_intervention(self, message: str, problem_type: str) -> bool:
        """Determina si el caso requiere intervención humana."""
        message_lower = message.lower()

        # Palabras que indican necesidad de escalación
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

        # Tipos de problema que típicamente requieren humano
        human_required_types = ["legal", "fraud", "complex_technical"]

        return (
            any(keyword in message_lower for keyword in escalation_keywords)
            or problem_type in human_required_types
            or len(message) > 500  # Mensajes muy largos suelen ser complejos
        )

    def _load_faq_responses(self) -> Dict[str, List[Dict[str, Any]]]:
        """Carga respuestas FAQ predefinidas."""
        return {
            "payment": [
                {
                    "keywords": ["tarjeta rechazada", "pago rechazado"],
                    "response": """Tu tarjeta fue rechazada. Esto puede deberse a:

• **Fondos insuficientes**
• **Límite de crédito alcanzado**
• **Tarjeta vencida**
• **Datos incorrectos**

Por favor, verifica estos puntos o intenta con otro método de pago.""",
                },
                {
                    "keywords": ["métodos de pago", "formas de pago"],
                    "response": """Aceptamos los siguientes métodos de pago:

💳 **Tarjetas**: Visa, Mastercard, American Express
🏦 **Transferencia bancaria**
💰 **Mercado Pago**
📱 **Billeteras digitales**: PayPal

Todos los pagos son 100% seguros.""",
                },
            ],
            "delivery": [
                {
                    "keywords": ["tiempo de entrega", "cuánto tarda"],
                    "response": """Los tiempos de entrega son:

• **CABA**: 24-48 horas
• **GBA**: 48-72 horas
• **Interior**: 3-7 días hábiles

Los tiempos pueden variar según disponibilidad y método de envío elegido.""",
                }
            ],
            "general": [
                {
                    "keywords": ["horario", "atención"],
                    "response": """Nuestros horarios de atención son:

🕐 **Lunes a Viernes**: 9:00 - 18:00
🕐 **Sábados**: 9:00 - 13:00
❌ **Domingos y feriados**: Cerrado

Puedes dejarnos tu consulta y te responderemos a la brevedad.""",
                }
            ],
        }
