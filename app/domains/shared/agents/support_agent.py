# ============================================================================
# SCOPE: GLOBAL
# Description: Agente de soporte técnico y atención al cliente. Maneja soporte
#              e-commerce y software Excelencia Software.
# Tenant-Aware: Yes via BaseAgent - puede usar tenant's model/config.
# ============================================================================
"""
Agente especializado en soporte tecnico y atencion al cliente.

Este agente esta especializado en:
- Soporte general de e-commerce (pagos, envios, devoluciones)
- Soporte especializado de software Excelencia Software
- Incidencias de modulos, capacitaciones, tickets

Uses RAG (Knowledge Base Search) for context-aware responses.
"""

import logging
from typing import Any

from app.config.settings import get_settings
from app.core.agents import BaseAgent
from app.core.utils.tracing import trace_async_method
from app.domains.excelencia.application.services.support_response import (
    KnowledgeBaseSearch,
    RagQueryLogger,
    SearchMetrics,
)
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)
settings = get_settings()


class SupportAgent(BaseAgent):
    """
    Agente especializado en soporte tecnico y resolucion de problemas.

    Supports dual-mode configuration:
    - Global mode: Uses default model/temperature from BaseAgent
    - Multi-tenant mode: model/temperature can be overridden via apply_tenant_config()

    Specialized knowledge:
    - E-commerce support (payments, delivery, returns)
    - Excelencia Software software support (modules, incidents, training)
    """

    # Excelencia Software modules for specialized support
    EXCELENCIA_MODULES = {
        "inventario": {
            "name": "Modulo de Inventario",
            "common_issues": ["sincronizacion", "stock negativo", "transferencias"],
            "support_level": "L1",
        },
        "facturacion": {
            "name": "Modulo de Facturacion",
            "common_issues": ["cfdi", "timbrado", "cancelacion", "complemento pago"],
            "support_level": "L2",
        },
        "contabilidad": {
            "name": "Modulo de Contabilidad",
            "common_issues": ["polizas", "cierre mes", "balanza", "conciliacion"],
            "support_level": "L2",
        },
        "nomina": {
            "name": "Modulo de Nomina",
            "common_issues": ["timbrado recibo", "calculos", "isr", "imss"],
            "support_level": "L2",
        },
        "ventas": {
            "name": "Modulo de Ventas",
            "common_issues": ["cotizaciones", "pedidos", "precios", "descuentos"],
            "support_level": "L1",
        },
        "compras": {
            "name": "Modulo de Compras",
            "common_issues": ["ordenes compra", "recepciones", "cuentas por pagar"],
            "support_level": "L1",
        },
        "crm": {
            "name": "Modulo CRM",
            "common_issues": ["prospectos", "oportunidades", "seguimiento"],
            "support_level": "L1",
        },
        "produccion": {
            "name": "Modulo de Produccion",
            "common_issues": ["ordenes produccion", "explosion materiales", "costos"],
            "support_level": "L2",
        },
        "reportes": {
            "name": "Modulo de Reportes",
            "common_issues": ["dashboard", "exportacion", "personalizacion"],
            "support_level": "L1",
        },
    }

    def __init__(self, llm=None, config: dict[str, Any] | None = None):
        super().__init__("support_agent", config or {}, llm=llm)

        # Note: self.model and self.temperature are set by BaseAgent.__init__()
        # They can be overridden via apply_tenant_config() in multi-tenant mode

        # Initialize PromptManager for YAML-based prompts
        self.prompt_manager = PromptManager()

        # FAQ comun (e-commerce + Excelencia) - loaded from YAML
        self.faq_responses = self._load_faq_responses()

        # RAG integration for knowledge-based responses
        self._knowledge_search = KnowledgeBaseSearch(
            agent_key="support_agent",
            max_results=3,
        )
        self._rag_logger = RagQueryLogger(agent_key="support_agent")
        self._last_search_metrics: SearchMetrics | None = None
        self.use_rag = getattr(settings, "KNOWLEDGE_BASE_ENABLED", True)

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
                # Get RAG context for knowledge-based response
                rag_context = await self._get_rag_context(message, problem_type)

                # Generar respuesta personalizada con contexto RAG
                response_text = await self._generate_support_response(
                    message, problem_type, rag_context
                )

                # Log RAG query with response (fire-and-forget)
                if self._last_search_metrics and self._last_search_metrics.result_count > 0:
                    self._rag_logger.log_async(
                        query=message,
                        metrics=self._last_search_metrics,
                        response=response_text,
                    )

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

        # Check for Excelencia software issues first (higher priority)
        excelencia_module = self._detect_excelencia_module(message_lower)
        if excelencia_module:
            return f"excelencia_{excelencia_module}"

        # Check for Excelencia-specific keywords
        excelencia_keywords = [
            "modulo",
            "erp",
            "excelencia",
            "software",
            "sistema",
            "licencia",
            "capacitacion",
            "implementacion",
            "actualizacion",
            "version",
            "ticket",
            "incidencia",
        ]
        if any(kw in message_lower for kw in excelencia_keywords):
            return "excelencia_general"

        # E-commerce problem patterns
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

    def _detect_excelencia_module(self, message_lower: str) -> str | None:
        """Detecta si el mensaje menciona un modulo especifico de Excelencia."""
        for module_key, module_info in self.EXCELENCIA_MODULES.items():
            # Check module name
            if module_key in message_lower:
                return module_key
            # Check common issues for this module
            if any(issue in message_lower for issue in module_info["common_issues"]):
                return module_key
        return None

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

    async def _get_rag_context(self, message: str, problem_type: str) -> str:
        """
        Get RAG context from knowledge base.

        Args:
            message: User message
            problem_type: Detected problem type

        Returns:
            Formatted context string or empty string
        """
        self._last_search_metrics = None

        if not self.use_rag:
            return ""

        try:
            search_result = await self._knowledge_search.search(message, problem_type)
            self._last_search_metrics = search_result.metrics
            if search_result.context:
                logger.info(f"RAG context found for support query: {len(search_result.context)} chars")
            return search_result.context
        except Exception as e:
            logger.warning(f"RAG search failed: {e}")
            return ""

    async def _generate_support_response(
        self, message: str, problem_type: str, rag_context: str = ""
    ) -> str:
        """Genera respuesta de soporte personalizada usando YAML prompts."""
        # Check if it's an Excelencia module issue
        if problem_type.startswith("excelencia_"):
            return await self._generate_excelencia_response(message, problem_type)

        # Map problem types to registry keys
        key_mapping = {
            "payment": PromptRegistry.AGENTS_SUPPORT_RESPONSE_PAYMENT,
            "delivery": PromptRegistry.AGENTS_SUPPORT_RESPONSE_DELIVERY,
            "product": PromptRegistry.AGENTS_SUPPORT_RESPONSE_PRODUCT,
            "account": PromptRegistry.AGENTS_SUPPORT_RESPONSE_ACCOUNT,
            "return": PromptRegistry.AGENTS_SUPPORT_RESPONSE_RETURN,
            "technical": PromptRegistry.AGENTS_SUPPORT_RESPONSE_TECHNICAL,
            "general": PromptRegistry.AGENTS_SUPPORT_RESPONSE_GENERAL,
        }

        prompt_key = key_mapping.get(problem_type, PromptRegistry.AGENTS_SUPPORT_RESPONSE_GENERAL)

        try:
            response = await self.prompt_manager.get_prompt(prompt_key)
            return response
        except Exception as e:
            logger.warning(f"Failed to load YAML prompt for {problem_type}: {e}")
            # Fallback to general response
            try:
                return await self.prompt_manager.get_prompt(PromptRegistry.AGENTS_SUPPORT_RESPONSE_GENERAL)
            except Exception:
                return "Estoy aqui para ayudarte. En que puedo asistirte?"

    async def _generate_excelencia_response(self, message: str, problem_type: str) -> str:
        """Genera respuesta especializada para soporte de Excelencia Software usando YAML."""
        # Extract module name from problem_type
        module_key = problem_type.replace("excelencia_", "")

        if module_key == "general":
            try:
                return await self.prompt_manager.get_prompt(PromptRegistry.AGENTS_SUPPORT_EXCELENCIA_GENERAL)
            except Exception as e:
                logger.warning(f"Failed to load Excelencia general prompt: {e}")
                return "Entiendo que tienes una consulta sobre Excelencia Software. En que puedo ayudarte?"

        # Get module info
        module_info = self.EXCELENCIA_MODULES.get(module_key)
        if not module_info:
            return await self._generate_excelencia_response(message, "excelencia_general")

        module_name = module_info["name"]
        support_level = module_info["support_level"]
        common_issues = module_info["common_issues"]

        # Check for specific issues
        message_lower = message.lower()
        detected_issue = None
        for issue in common_issues:
            if issue in message_lower:
                detected_issue = issue
                break

        # Build variables for YAML template
        common_issues_list = "\n".join(f"- {issue.title()}" for issue in common_issues)
        detected_issue_section = ""
        if detected_issue:
            detected_issue_section = f"He detectado que mencionas **{detected_issue}**. Este es un problema conocido.\n"

        if support_level == "L2":
            escalation_message = (
                "Este modulo requiere soporte especializado. "
                "Un tecnico de nivel 2 se pondra en contacto contigo en las proximas 4 horas habiles."
            )
        else:
            escalation_message = (
                "Puedo generar un **ticket de soporte** para dar seguimiento a tu caso. "
                "Deseas que lo cree ahora?"
            )

        try:
            response = await self.prompt_manager.get_prompt(
                PromptRegistry.AGENTS_SUPPORT_EXCELENCIA_MODULE,
                variables={
                    "module_name": module_name,
                    "common_issues_list": common_issues_list,
                    "support_level": support_level,
                    "detected_issue_section": detected_issue_section,
                    "escalation_message": escalation_message,
                },
            )
            return response
        except Exception as e:
            logger.warning(f"Failed to load Excelencia module prompt: {e}")
            # Fallback to general response
            return await self._generate_excelencia_response(message, "excelencia_general")

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
        """Carga respuestas FAQ predefinidas (e-commerce + Excelencia)."""
        return {
            # E-commerce FAQ
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
            # Excelencia Software FAQ
            "excelencia_general": [
                {
                    "keywords": ["licencia", "activar licencia", "licenciamiento"],
                    "response": """Para activar o renovar tu licencia de **Excelencia Software**:

1. Ingresa a **Configuracion > Licenciamiento**
2. Haz clic en "Solicitar Activacion"
3. Copia el codigo de maquina
4. Contacta a tu ejecutivo para obtener la clave

**Tipos de licencia:**
- **Monousuario**: 1 usuario simultaneo
- **Red**: Multiples usuarios
- **Nube**: Acceso remoto

Tu ejecutivo puede ayudarte con renovaciones y ampliaciones.""",
                },
                {
                    "keywords": ["capacitacion", "entrenamiento", "curso"],
                    "response": """Ofrecemos diferentes opciones de **capacitacion**:

**Modalidades:**
- **Presencial**: En tus oficinas (min. 5 personas)
- **Virtual**: Sesiones por videollamada
- **E-learning**: Plataforma de cursos online

**Modulos disponibles:**
- Basico: Ventas, Compras, Inventario
- Intermedio: Contabilidad, Nomina
- Avanzado: Produccion, Reportes BI

Contacta a tu ejecutivo para programar una capacitacion.""",
                },
                {
                    "keywords": ["actualizacion", "nueva version", "upgrade"],
                    "response": """Para **actualizar** Excelencia Software:

**Proceso recomendado:**
1. Realizar respaldo completo de la base de datos
2. Cerrar todas las sesiones de usuarios
3. Ejecutar el instalador de la nueva version
4. Verificar la conversion de datos

**Importante:**
- Revisa las notas de version antes de actualizar
- Prueba en ambiente de pruebas primero
- Programa la actualizacion fuera de horario laboral

¿Necesitas asistencia con una actualizacion especifica?""",
                },
                {
                    "keywords": ["respaldo", "backup", "base de datos"],
                    "response": """Para realizar **respaldos** de Excelencia Software:

**Respaldo automatico:**
- Configura en **Herramientas > Respaldos**
- Programa respaldos diarios/semanales
- Guarda en ubicacion externa

**Respaldo manual:**
1. Ve a **Herramientas > Respaldo de BD**
2. Selecciona la ruta de destino
3. Haz clic en "Generar Respaldo"

**Mejores practicas:**
- Respaldo diario minimo
- Guardar en la nube o disco externo
- Verificar integridad periodicamente""",
                },
            ],
            "excelencia_facturacion": [
                {
                    "keywords": ["timbrado", "cfdi", "sat"],
                    "response": """Para problemas de **timbrado CFDI**:

**Errores comunes:**
- **CSD vencido**: Renueva en el portal del SAT
- **Sello invalido**: Verifica certificado y clave
- **RFC incorrecto**: Revisa datos del cliente
- **PAC no disponible**: Intenta mas tarde

**Verificaciones:**
1. Asegurate de tener internet estable
2. Verifica que tu CSD este vigente
3. Revisa que los datos fiscales sean correctos

Si el problema persiste, genera un ticket de soporte.""",
                },
                {
                    "keywords": ["cancelar factura", "cancelacion"],
                    "response": """Para **cancelar una factura CFDI**:

**Requisitos:**
- Dentro del mismo ejercicio fiscal
- Motivo de cancelacion valido
- Aceptacion del receptor (si aplica)

**Proceso:**
1. Ve a **Facturacion > Consulta de CFDI**
2. Localiza la factura a cancelar
3. Selecciona "Cancelar"
4. Indica el motivo y documento sustituto

**Nota:** Algunas cancelaciones requieren aceptacion del cliente en un plazo de 72 horas.""",
                },
            ],
            "excelencia_contabilidad": [
                {
                    "keywords": ["cierre mes", "cierre contable"],
                    "response": """Para el **cierre de mes** en Excelencia:

**Pasos previos:**
1. Verificar todas las polizas del periodo
2. Conciliar cuentas bancarias
3. Revisar cuentas por cobrar/pagar
4. Calcular depreciaciones

**Proceso de cierre:**
1. Ve a **Contabilidad > Cierre de Periodo**
2. Selecciona el mes a cerrar
3. Revisa el prelisting de cierre
4. Confirma el cierre

Una vez cerrado, no podras agregar polizas a ese periodo sin reabrirlo.""",
                },
            ],
            "excelencia_inventario": [
                {
                    "keywords": ["stock negativo", "existencia negativa"],
                    "response": """Para corregir **stock negativo**:

**Causas comunes:**
- Ventas sin entrada de compras
- Ajustes de inventario pendientes
- Transferencias no procesadas

**Solucion:**
1. Ve a **Inventarios > Existencias por Almacen**
2. Identifica los productos con stock negativo
3. Realiza un ajuste de inventario positivo
4. Documenta la causa del ajuste

Para prevenir esto, activa **Control de Existencias** en configuracion.""",
                },
            ],
            # General FAQ
            "general": [
                {
                    "keywords": ["horario", "atencion"],
                    "response": """Nuestros horarios de atencion son:

**Soporte Tecnico Excelencia:**
- Lunes a Viernes: 8:00 - 20:00
- Sabados: 9:00 - 14:00

**E-commerce:**
- Lunes a Viernes: 9:00 - 18:00
- Sabados: 9:00 - 13:00

Domingos y feriados: Cerrado

Puedes dejarnos tu consulta y te responderemos a la brevedad.""",
                },
                {
                    "keywords": ["contacto", "telefono", "email"],
                    "response": """Nuestros canales de contacto:

**Soporte Excelencia Software:**
- Portal: soporte.excelencia.com
- Email: soporte@excelencia.com
- Tel: 800-123-4567

**E-commerce:**
- WhatsApp: Este canal
- Email: ventas@aynux.com

Para soporte tecnico urgente, genera un ticket en el portal.""",
                },
            ],
        }
