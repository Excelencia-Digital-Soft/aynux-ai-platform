"""
Agente de soporte técnico
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.agents.langgraph_system.agents.base_agent import BaseAgent
from app.agents.langgraph_system.models import SharedState


class SupportAgent(BaseAgent):
    """Agente especializado en soporte técnico y troubleshooting"""

    def __init__(self, vector_store, knowledge_base, llm):
        super().__init__("support_agent")
        self.vector_store = vector_store
        self.kb = knowledge_base  # Base de conocimiento técnico
        self.llm = llm

        # Inicializar herramientas
        self.tools = [
            TroubleshootingTool(knowledge_base, llm),
            ProductManualTool(vector_store),
            FAQSearchTool(vector_store),
            TicketCreationTool(),
        ]

    async def _process_internal(self, state: SharedState) -> Dict[str, Any]:
        """Procesa consultas de soporte técnico"""
        user_message = state.get_last_user_message()

        entities = state.current_intent.entities if state.current_intent else {}

        # Determinar tipo de problema
        problem_type = await self._analyze_problem_type(user_message, entities)

        if problem_type == "product_issue":
            return await self._handle_product_issue(user_message, entities, state)
        elif problem_type == "warranty":
            return await self._handle_warranty_inquiry(user_message, state)
        elif problem_type == "return":
            return await self._handle_return_request(user_message, state)
        elif problem_type == "technical_help":
            return await self._handle_technical_help(user_message, entities)
        else:
            return await self._handle_general_support(user_message, state)

    async def _analyze_problem_type(self, message: str, entities: Dict) -> str:
        """Analiza el tipo de problema de soporte"""
        message_lower = message.lower()

        # Patrones para diferentes tipos de problemas
        if any(word in message_lower for word in ["no funciona", "falla", "error", "problema con"]):
            return "product_issue"
        elif any(word in message_lower for word in ["garantía", "garantia", "warranty"]):
            return "warranty"
        elif any(word in message_lower for word in ["devolver", "devolución", "cambio", "retorno"]):
            return "return"
        elif any(word in message_lower for word in ["cómo", "como", "ayuda con", "configurar"]):
            return "technical_help"
        else:
            return "general"

    async def _handle_product_issue(self, message: str, entities: Dict, state: SharedState) -> Dict[str, Any]:
        """Maneja problemas con productos"""
        # Buscar en base de conocimiento
        kb_results = await self.tools[0].search_troubleshooting(message)

        # Buscar en FAQs
        faq_results = await self.tools[2].search_faqs(message)

        # Si encontramos soluciones
        if kb_results or faq_results:
            response = "🔧 **Encontré estas soluciones para tu problema:**\n\n"

            # Mostrar soluciones de troubleshooting
            if kb_results:
                for idx, solution in enumerate(kb_results[:3], 1):
                    response += f"**Solución {idx}: {solution['title']}**\n"
                    response += f"{solution['description']}\n\n"

                    # Pasos si existen
                    if solution.get("steps"):
                        response += "📋 **Pasos a seguir:**\n"
                        for step_idx, step in enumerate(solution["steps"], 1):
                            response += f"{step_idx}. {step}\n"
                        response += "\n"

            # Mostrar FAQs relevantes
            if faq_results and len(kb_results) < 2:
                response += "\n**❓ Preguntas frecuentes relacionadas:**\n"
                for faq in faq_results[:2]:
                    response += f"• {faq['question']}\n"
                    response += f"  → {faq['answer']}\n\n"

            response += "¿Esto resolvió tu problema? Si no, puedo crear un ticket de soporte."

            return {
                "text": response,
                "data": {"kb_results": kb_results, "faq_results": faq_results},
                "tools_used": ["TroubleshootingTool", "FAQSearchTool"],
            }
        else:
            # No hay solución inmediata - preparar ticket
            return await self._prepare_support_ticket(message, state)

    async def _handle_warranty_inquiry(self, message: str, state: SharedState) -> Dict[str, Any]:
        """Maneja consultas sobre garantía"""
        response = "🛡️ **Información sobre Garantía:**\n\n"

        # Buscar productos mencionados
        products = await self._extract_product_mentions(message)

        if products:
            # Información específica de garantía
            for product in products:
                warranty_info = await self._get_warranty_info(product)
                response += f"**{product}:**\n"
                response += f"• Garantía: {warranty_info['duration']}\n"
                response += f"• Cobertura: {warranty_info['coverage']}\n"
                response += f"• Condiciones: {warranty_info['conditions']}\n\n"
        else:
            # Información general de garantía
            response += "**Cobertura estándar de garantía:**\n"
            response += "• **Laptops y PCs:** 12 meses\n"
            response += "• **Componentes:** 6-24 meses según fabricante\n"
            response += "• **Accesorios:** 3-6 meses\n\n"

            response += "**¿Qué cubre la garantía?**\n"
            response += "✅ Defectos de fabricación\n"
            response += "✅ Fallas en condiciones normales de uso\n"
            response += "✅ Componentes defectuosos\n\n"

            response += "**¿Qué NO cubre?**\n"
            response += "❌ Daños físicos o por mal uso\n"
            response += "❌ Modificaciones no autorizadas\n"
            response += "❌ Daños por líquidos\n\n"

        response += "Para validar tu garantía, necesito tu número de orden o serie del producto."

        return {"text": response, "data": {"warranty_inquiry": True, "products_mentioned": products}, "tools_used": []}

    async def _handle_return_request(self, message: str, state: SharedState) -> Dict[str, Any]:
        """Maneja solicitudes de devolución"""
        response = "↩️ **Proceso de Devolución:**\n\n"

        # Verificar si hay orden mencionada
        order_numbers = self._extract_order_numbers(message)

        if order_numbers:
            # Verificar elegibilidad
            for order_num in order_numbers:
                eligibility = await self._check_return_eligibility(order_num)

                if eligibility["eligible"]:
                    response += f"✅ **Orden #{order_num}** - Elegible para devolución\n"
                    response += f"   • Días restantes: {eligibility['days_remaining']}\n"
                    response += "   • Condición requerida: Producto sin uso\n\n"
                else:
                    response += f"❌ **Orden #{order_num}** - {eligibility['reason']}\n\n"
        else:
            # Información general de devoluciones
            response += "**Política de devoluciones:**\n"
            response += "• **Plazo:** 30 días desde la recepción\n"
            response += "• **Condición:** Producto sin uso, empaque original\n"
            response += "• **Proceso:** 5-10 días hábiles\n\n"

        response += "**📋 Pasos para devolución:**\n"
        response += "1. Solicitar autorización (RMA)\n"
        response += "2. Embalar producto en caja original\n"
        response += "3. Adjuntar formulario de devolución\n"
        response += "4. Enviar a nuestra dirección\n"
        response += "5. Reembolso tras inspección\n\n"

        response += "¿Deseas iniciar el proceso de devolución?"

        return {"text": response, "data": {"return_request": True, "order_numbers": order_numbers}, "tools_used": []}

    async def _handle_technical_help(self, message: str, entities: Dict) -> Dict[str, Any]:
        """Maneja solicitudes de ayuda técnica"""
        # Buscar manuales relevantes
        manual_results = await self.tools[1].search_manuals(message)

        # Buscar guías de configuración
        setup_guides = await self.tools[0].search_setup_guides(message)

        response = "💡 **Ayuda Técnica:**\n\n"

        if manual_results:
            response += "📚 **Manuales disponibles:**\n"
            for manual in manual_results[:3]:
                response += f"• [{manual['title']}]({manual['url']})\n"
                response += f"  {manual['description']}\n"
            response += "\n"

        if setup_guides:
            response += "🔧 **Guías de configuración:**\n"
            for guide in setup_guides[:3]:
                response += f"\n**{guide['title']}**\n"

                # Mostrar primeros pasos
                if guide.get("steps"):
                    for idx, step in enumerate(guide["steps"][:3], 1):
                        response += f"{idx}. {step}\n"
                    if len(guide["steps"]) > 3:
                        response += f"... y {len(guide['steps']) - 3} pasos más\n"

        # Videos tutoriales si existen
        response += "\n📹 **Videos tutoriales:**\n"
        response += "• [Configuración inicial](video_link)\n"
        response += "• [Solución de problemas comunes](video_link)\n"

        response += "\n¿Necesitas ayuda con algún paso específico?"

        return {
            "text": response,
            "data": {"manual_results": manual_results, "setup_guides": setup_guides},
            "tools_used": ["ProductManualTool", "TroubleshootingTool"],
        }

    async def _handle_general_support(self, message: str, state: SharedState) -> Dict[str, Any]:
        """Maneja consultas generales de soporte"""
        # Buscar en FAQs
        faq_results = await self.tools[2].search_faqs(message)

        if faq_results:
            response = "❓ **Preguntas Frecuentes relacionadas:**\n\n"

            for faq in faq_results[:5]:
                response += f"**Q: {faq['question']}**\n"
                response += f"A: {faq['answer']}\n\n"

            response += "¿Esto responde tu pregunta? Si no, puedo ayudarte de otra manera."
        else:
            response = "🤝 **¿En qué puedo ayudarte?**\n\n"
            response += "Puedo asistirte con:\n"
            response += "• 🔧 Problemas técnicos\n"
            response += "• 🛡️ Consultas de garantía\n"
            response += "• ↩️ Devoluciones y cambios\n"
            response += "• 📚 Manuales y guías\n"
            response += "• 🎫 Crear ticket de soporte\n\n"
            response += "Por favor, describe tu consulta con más detalle."

        return {"text": response, "data": {"faq_results": faq_results}, "tools_used": ["FAQSearchTool"]}

    async def _prepare_support_ticket(self, issue: str, state: SharedState) -> Dict[str, Any]:
        """Prepara un ticket de soporte"""
        # Recopilar información para el ticket
        ticket_data = {
            "customer_id": state.customer.customer_id if state.customer else None,
            "issue_description": issue,
            "conversation_id": state.conversation.conversation_id if state.conversation else None,
            "priority": self._determine_priority(issue),
            "category": "technical_support",
        }

        # Crear ticket
        ticket = await self.tools[3].create_ticket(ticket_data)

        response = "🎫 **Ticket de Soporte Creado**\n\n"
        response += f"📋 **Número de ticket:** `{ticket['ticket_id']}`\n"
        response += f"🔔 **Prioridad:** {ticket['priority']}\n"
        response += f"⏱️ **Tiempo estimado de respuesta:** {ticket['estimated_response']}\n\n"

        response += "**¿Qué sigue?**\n"
        response += "1. Recibirás un email de confirmación\n"
        response += "2. Un técnico revisará tu caso\n"
        response += "3. Te contactaremos con la solución\n\n"

        response += "Mientras tanto, ¿hay algo más en lo que pueda ayudarte?"

        return {"text": response, "data": {"ticket": ticket, "escalated": True}, "tools_used": ["TicketCreationTool"]}

    # Métodos auxiliares
    async def _extract_product_mentions(self, message: str) -> List[str]:
        """Extrae productos mencionados en el mensaje"""
        # Implementación simplificada
        products = []

        # Patrones de productos comunes
        product_patterns = [
            r"(laptop|notebook)\s+(\w+)?",
            r"(mouse|ratón)\s+(\w+)?",
            r"(teclado|keyboard)\s+(\w+)?",
        ]

        for pattern in product_patterns:
            matches = re.findall(pattern, message.lower())
            for match in matches:
                products.append(" ".join(match).strip())

        return products

    def _extract_order_numbers(self, message: str) -> List[str]:
        """Extrae números de orden del mensaje"""
        pattern = r"#?(\d{6,})"
        return re.findall(pattern, message)

    async def _get_warranty_info(self, product: str) -> Dict[str, Any]:
        """Obtiene información de garantía para un producto"""
        # En producción esto consultaría la BD
        return {
            "duration": "12 meses",
            "coverage": "Defectos de fabricación y componentes",
            "conditions": "Uso normal, sin daños físicos",
        }

    async def _check_return_eligibility(self, order_number: str) -> Dict[str, Any]:
        """Verifica elegibilidad para devolución"""
        # En producción esto consultaría la BD
        # Simulación
        import random

        if random.choice([True, True, False]):  # 66% elegible
            return {"eligible": True, "days_remaining": random.randint(5, 25)}
        else:
            return {"eligible": False, "reason": "Plazo de devolución expirado (30 días)"}

    def _determine_priority(self, issue: str) -> str:
        """Determina la prioridad del ticket"""
        issue_lower = issue.lower()

        # Alta prioridad
        if any(word in issue_lower for word in ["no funciona", "urgente", "crítico"]):
            return "high"
        # Media prioridad
        elif any(word in issue_lower for word in ["problema", "error", "ayuda"]):
            return "medium"
        # Baja prioridad
        else:
            return "low"


# Herramientas del SupportAgent
class TroubleshootingTool:
    """Herramienta de troubleshooting"""

    def __init__(self, knowledge_base, llm):
        self.kb = knowledge_base
        self.llm = llm

    async def search_troubleshooting(self, issue: str) -> List[Dict]:
        """Busca soluciones de troubleshooting"""
        # En producción buscaría en la base de conocimiento
        # Simulación
        solutions = [
            {
                "title": "Laptop no enciende",
                "description": "Verificar conexión de alimentación y batería",
                "steps": [
                    "Conectar el cargador y verificar LED de carga",
                    "Mantener presionado el botón de encendido por 10 segundos",
                    "Desconectar batería y volver a conectar",
                    "Probar con otro cargador compatible",
                ],
                "success_rate": 0.85,
            }
        ]

        # Filtrar por relevancia
        if "no enciende" in issue.lower() or "no prende" in issue.lower():
            return solutions

        return []

    async def search_setup_guides(self, query: str) -> List[Dict]:
        """Busca guías de configuración"""
        # Simulación
        return [
            {
                "title": "Configuración inicial de Windows",
                "steps": [
                    "Seleccionar idioma y región",
                    "Conectar a red WiFi",
                    "Crear cuenta de usuario",
                    "Configurar privacidad",
                    "Instalar actualizaciones",
                ],
            }
        ]


class ProductManualTool:
    """Herramienta para buscar manuales"""

    def __init__(self, vector_store):
        self.vector_store = vector_store

    async def search_manuals(self, query: str) -> List[Dict]:
        """Busca manuales de productos"""
        # En producción buscaría en vector store
        return [
            {
                "title": "Manual de Usuario - Laptop Gaming X",
                "description": "Guía completa de uso y mantenimiento",
                "url": "https://example.com/manual/laptop-x.pdf",
                "pages": 120,
            }
        ]


class FAQSearchTool:
    """Herramienta de búsqueda en FAQs"""

    def __init__(self, vector_store):
        self.vector_store = vector_store

    async def search_faqs(self, query: str) -> List[Dict]:
        """Busca en preguntas frecuentes"""
        # En producción haría búsqueda semántica
        faqs = [
            {
                "question": "¿Cómo activo la garantía?",
                "answer": "La garantía se activa automáticamente con la compra. Guarda tu factura como comprobante.",
            },
            {
                "question": "¿Puedo devolver un producto abierto?",
                "answer": "Sí, dentro de 30 días y en perfectas condiciones, con empaque original.",
            },
        ]

        # Filtrado simple
        relevant_faqs = []
        query_lower = query.lower()

        for faq in faqs:
            if any(word in faq["question"].lower() or word in faq["answer"].lower() for word in query_lower.split()):
                relevant_faqs.append(faq)

        return relevant_faqs


class TicketCreationTool:
    """Herramienta para crear tickets de soporte"""

    async def create_ticket(self, ticket_data: Dict) -> Dict[str, Any]:
        """Crea un ticket de soporte"""
        import random
        import string

        # Generar ID de ticket
        ticket_id = "TK" + "".join(random.choices(string.digits, k=8))

        # Determinar tiempo de respuesta según prioridad
        response_times = {"high": "2-4 horas", "medium": "24 horas", "low": "48-72 horas"}

        return {
            "ticket_id": ticket_id,
            "status": "open",
            "priority": ticket_data.get("priority", "medium"),
            "estimated_response": response_times.get(ticket_data.get("priority", "medium")),
            "created_at": datetime.now().isoformat(),
            "assigned_to": None,
        }

