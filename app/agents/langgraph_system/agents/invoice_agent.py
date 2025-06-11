"""
Agente especializado en generación de facturas
"""
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.agents.langgraph_system.agents.base_agent import BaseAgent
from app.agents.langgraph_system.models import SharedState


class InvoiceAgent(BaseAgent):
    """Agente especializado en generación y gestión de facturas"""
    
    def __init__(self, db_connection, invoice_api, llm):
        super().__init__("invoice_agent")
        self.db = db_connection
        self.invoice_api = invoice_api
        self.llm = llm
        
        # Inicializar herramientas
        self.tools = [
            InvoiceGeneratorTool(invoice_api),
            TaxCalculatorTool(),
            InvoiceValidatorTool(),
            InvoiceDeliveryTool()
        ]
    
    async def _process_internal(self, state: SharedState) -> Dict[str, Any]:
        """Procesa solicitudes de facturas"""
        user_message = state.get_last_user_message()
        entities = state.current_intent.entities if state.current_intent else {}
        customer = state.customer
        
        # Extraer números de orden si existen
        order_numbers = self._extract_order_numbers(user_message, entities)
        
        # Determinar tipo de solicitud
        request_type = self._determine_request_type(user_message)
        
        if request_type == "generate_new":
            return await self._handle_new_invoice_request(
                order_numbers, 
                customer,
                user_message
            )
        elif request_type == "resend_existing":
            return await self._handle_resend_request(
                order_numbers,
                customer
            )
        elif request_type == "update_billing":
            return await self._handle_billing_update(
                customer,
                user_message
            )
        else:
            return await self._handle_general_invoice_inquiry(
                customer,
                user_message
            )
    
    def _determine_request_type(self, message: str) -> str:
        """Determina el tipo de solicitud de factura"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["generar", "nueva", "crear"]):
            return "generate_new"
        elif any(word in message_lower for word in ["reenviar", "enviar de nuevo", "duplicado"]):
            return "resend_existing"
        elif any(word in message_lower for word in ["cambiar datos", "actualizar", "corregir"]):
            return "update_billing"
        else:
            return "general"
    
    async def _handle_new_invoice_request(
        self,
        order_numbers: List[str],
        customer,
        message: str
    ) -> Dict[str, Any]:
        """Maneja solicitudes de nuevas facturas"""
        if not customer:
            return self._request_customer_info()
        
        # Buscar órdenes para facturar
        if order_numbers:
            orders = await self._get_orders_by_numbers(order_numbers, customer.customer_id)
        else:
            # Buscar órdenes pendientes de facturación
            orders = await self._get_unfactured_orders(customer.customer_id)
        
        if not orders:
            return self._handle_no_orders_for_invoice(order_numbers)
        
        # Procesar cada orden
        invoice_results = []
        total_processed = 0
        
        for order in orders:
            try:
                # Verificar si ya tiene factura
                existing_invoice = await self._check_existing_invoice(order['id'])
                if existing_invoice:
                    invoice_results.append({
                        "order_id": order['id'],
                        "status": "already_exists",
                        "invoice": existing_invoice
                    })
                    continue
                
                # Calcular impuestos
                tax_calculation = await self.tools[1].calculate_taxes(
                    order,
                    customer
                )
                
                # Generar factura
                invoice = await self.tools[0].generate_invoice(
                    order,
                    tax_calculation,
                    customer
                )
                
                # Validar factura
                validation = await self.tools[2].validate_invoice(invoice)
                
                if validation['valid']:
                    # Enviar factura
                    delivery_result = await self.tools[3].send_invoice(
                        invoice,
                        customer.email,
                        customer.phone
                    )
                    
                    invoice_results.append({
                        "order_id": order['id'],
                        "status": "success",
                        "invoice": invoice,
                        "delivery": delivery_result
                    })
                    total_processed += 1
                else:
                    invoice_results.append({
                        "order_id": order['id'],
                        "status": "validation_failed",
                        "error": validation['errors']
                    })
                    
            except Exception as e:
                invoice_results.append({
                    "order_id": order['id'],
                    "status": "error",
                    "error": str(e)
                })
        
        return self._format_invoice_generation_response(
            invoice_results,
            total_processed,
            customer
        )
    
    async def _handle_resend_request(
        self,
        order_numbers: List[str],
        customer
    ) -> Dict[str, Any]:
        """Maneja solicitudes de reenvío de facturas"""
        if not customer:
            return self._request_customer_info()
        
        if not order_numbers:
            # Buscar facturas recientes
            recent_invoices = await self._get_recent_invoices(customer.customer_id, limit=5)
            
            if not recent_invoices:
                return {
                    "text": "No encontré facturas recientes en tu cuenta. ¿Podrías proporcionarme el número de orden?",
                    "data": {},
                    "tools_used": []
                }
            
            return self._format_recent_invoices_response(recent_invoices)
        
        # Buscar facturas específicas
        invoices_found = []
        for order_num in order_numbers:
            invoice = await self._find_invoice_by_order(order_num, customer.customer_id)
            if invoice:
                # Reenviar factura
                delivery_result = await self.tools[3].send_invoice(
                    invoice,
                    customer.email,
                    customer.phone
                )
                invoices_found.append({
                    "order_number": order_num,
                    "invoice": invoice,
                    "resent": delivery_result['success']
                })
        
        return self._format_resend_response(invoices_found, customer)
    
    async def _handle_billing_update(
        self,
        customer,
        message: str
    ) -> Dict[str, Any]:
        """Maneja actualizaciones de datos de facturación"""
        if not customer:
            return self._request_customer_info()
        
        # Extraer nuevos datos del mensaje
        new_data = await self._extract_billing_data(message)
        
        if not new_data:
            return {
                "text": """📝 **Para actualizar tus datos de facturación, necesito:**

• Razón social o nombre completo
• RFC o CUIT
• Dirección fiscal completa
• Email para envío

Por favor proporciona la información que deseas actualizar.""",
                "data": {},
                "tools_used": []
            }
        
        # Validar nuevos datos
        validation = await self._validate_billing_data(new_data)
        
        if validation['valid']:
            # Actualizar datos
            update_result = await self._update_customer_billing(
                customer.customer_id,
                new_data
            )
            
            response = "✅ **Datos de facturación actualizados correctamente**\n\n"
            response += "**Información actualizada:**\n"
            
            for field, value in new_data.items():
                field_name = self._translate_field_name(field)
                response += f"• {field_name}: {value}\n"
            
            response += "\nTus próximas facturas se generarán con esta información."
            
            return {
                "text": response,
                "data": {
                    "updated_data": new_data,
                    "update_result": update_result
                },
                "tools_used": []
            }
        else:
            response = "❌ **Error en los datos proporcionados:**\n\n"
            for error in validation['errors']:
                response += f"• {error}\n"
            
            response += "\nPor favor corrige estos datos y vuelve a intentar."
            
            return {
                "text": response,
                "data": {
                    "validation_errors": validation['errors']
                },
                "tools_used": []
            }
    
    async def _handle_general_invoice_inquiry(
        self,
        customer,
        message: str
    ) -> Dict[str, Any]:
        """Maneja consultas generales sobre facturas"""
        response = "🧾 **Información sobre Facturas**\n\n"
        
        if customer:
            # Mostrar información personalizada
            recent_invoices = await self._get_recent_invoices(customer.customer_id, limit=3)
            
            if recent_invoices:
                response += f"**Tus últimas {len(recent_invoices)} facturas:**\n"
                for invoice in recent_invoices:
                    response += f"• Orden #{invoice['order_number']} - ${invoice['total']:,.2f}\n"
                    response += f"  Fecha: {invoice['date']} - [Descargar PDF]({invoice['pdf_url']})\n"
                response += "\n"
        
        response += "**¿Qué puedo hacer por ti?**\n"
        response += "• 📄 Generar factura para una orden\n"
        response += "• 📧 Reenviar factura existente\n"
        response += "• ✏️ Actualizar datos de facturación\n"
        response += "• 📋 Consultar estado de facturación\n\n"
        
        response += "**Información importante:**\n"
        response += "• Las facturas se generan en formato PDF\n"
        response += "• Se envían por email y WhatsApp\n"
        response += "• Incluyen todos los impuestos vigentes\n"
        response += "• Son válidas para uso fiscal\n\n"
        
        response += "¿En qué específicamente puedo ayudarte?"
        
        return {
            "text": response,
            "data": {
                "general_inquiry": True
            },
            "tools_used": []
        }
    
    # Métodos auxiliares
    def _extract_order_numbers(self, message: str, entities: Dict) -> List[str]:
        """Extrae números de orden del mensaje"""
        order_numbers = []
        
        # De entidades
        if entities.get("order_numbers"):
            order_numbers.extend(entities["order_numbers"])
        
        # Patrones adicionales
        patterns = [
            r'#(\d{6,})',
            r'orden\s*[:‑–—-]?\s*(\d{6,})',
            r'pedido\s*[:‑–—-]?\s*(\d{6,})',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            order_numbers.extend(matches)
        
        return list(set(order_numbers))
    
    async def _extract_billing_data(self, message: str) -> Dict[str, str]:
        """Extrae datos de facturación del mensaje"""
        data = {}
        
        # RFC/CUIT
        rfc_match = re.search(r'rfc\s*[:‑–—-]?\s*([A-Z0-9]{10,13})', message, re.IGNORECASE)
        if rfc_match:
            data['rfc'] = rfc_match.group(1)
        
        # Email
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
        if email_match:
            data['email'] = email_match.group(0)
        
        # Nombre/Razón social (simplificado)
        name_patterns = [
            r'nombre\s*[:‑–—-]?\s*([A-Za-z\s]+)',
            r'razón\s+social\s*[:‑–—-]?\s*([A-Za-z\s]+)'
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                data['name'] = match.group(1).strip()
                break
        
        return data
    
    def _translate_field_name(self, field: str) -> str:
        """Traduce nombres de campos"""
        translations = {
            'name': 'Nombre/Razón Social',
            'rfc': 'RFC/CUIT',
            'email': 'Email',
            'address': 'Dirección',
            'phone': 'Teléfono'
        }
        return translations.get(field, field)
    
    def _request_customer_info(self) -> Dict[str, Any]:
        """Solicita información del cliente"""
        return {
            "text": "Para generar una factura, necesito que estés registrado en nuestro sistema. ¿Podrías proporcionarme tu email o número de cliente?",
            "data": {},
            "tools_used": []
        }
    
    def _handle_no_orders_for_invoice(self, order_numbers: List[str]) -> Dict[str, Any]:
        """Maneja cuando no hay órdenes para facturar"""
        if order_numbers:
            response = f"❌ No encontré órdenes válidas para los números: {', '.join(order_numbers)}\n\n"
            response += "Verifica que:\n"
            response += "• Los números sean correctos\n"
            response += "• Las órdenes estén pagadas\n"
            response += "• No tengan factura previa\n"
        else:
            response = "📭 No encontré órdenes pendientes de facturación en tu cuenta.\n\n"
            response += "Las facturas se generan automáticamente al pagar. ¿Necesitas el comprobante de alguna orden específica?"
        
        return {
            "text": response,
            "data": {},
            "tools_used": []
        }
    
    def _format_invoice_generation_response(
        self,
        results: List[Dict],
        total_processed: int,
        customer
    ) -> Dict[str, Any]:
        """Formatea respuesta de generación de facturas"""
        response = f"🧾 **Proceso de Facturación Completado**\n\n"
        
        if total_processed > 0:
            response += f"✅ **{total_processed} facturas generadas exitosamente**\n\n"
            
            successful_invoices = [r for r in results if r['status'] == 'success']
            
            for result in successful_invoices:
                invoice = result['invoice']
                response += f"**Factura #{invoice['invoice_number']}**\n"
                response += f"• Orden: #{result['order_id']}\n"
                response += f"• Total: ${invoice['total']:,.2f}\n"
                response += f"• Fecha: {invoice['date']}\n"
                response += f"• [Descargar PDF]({invoice['pdf_url']})\n\n"
        
        # Facturas que ya existían
        existing = [r for r in results if r['status'] == 'already_exists']
        if existing:
            response += f"ℹ️ **{len(existing)} facturas ya existían:**\n"
            for result in existing:
                response += f"• Orden #{result['order_id']} - Ya facturada\n"
            response += "\n"
        
        # Errores
        errors = [r for r in results if r['status'] in ['error', 'validation_failed']]
        if errors:
            response += f"❌ **{len(errors)} errores:**\n"
            for result in errors:
                response += f"• Orden #{result['order_id']}: {result['error']}\n"
            response += "\n"
        
        # Información de envío
        if total_processed > 0:
            response += f"📧 Las facturas han sido enviadas a: {customer.email}\n"
            response += "💬 También recibirás los PDFs por WhatsApp\n"
        
        return {
            "text": response,
            "data": {
                "results": results,
                "total_processed": total_processed
            },
            "tools_used": ["InvoiceGeneratorTool", "TaxCalculatorTool", "InvoiceValidatorTool", "InvoiceDeliveryTool"]
        }
    
    # Métodos de integración con BD (simulados)
    async def _get_orders_by_numbers(self, order_numbers: List[str], customer_id: str) -> List[Dict]:
        """Obtiene órdenes por números"""
        # En producción consultaría la BD
        return []
    
    async def _get_unfactured_orders(self, customer_id: str) -> List[Dict]:
        """Obtiene órdenes sin facturar"""
        # En producción consultaría la BD
        return []
    
    async def _check_existing_invoice(self, order_id: str) -> Optional[Dict]:
        """Verifica si existe factura para una orden"""
        # En producción consultaría la BD
        return None
    
    async def _get_recent_invoices(self, customer_id: str, limit: int) -> List[Dict]:
        """Obtiene facturas recientes"""
        # En producción consultaría la BD
        return []
    
    async def _find_invoice_by_order(self, order_number: str, customer_id: str) -> Optional[Dict]:
        """Busca factura por número de orden"""
        # En producción consultaría la BD
        return None
    
    async def _validate_billing_data(self, data: Dict) -> Dict[str, Any]:
        """Valida datos de facturación"""
        # Validación simplificada
        return {"valid": True, "errors": []}
    
    async def _update_customer_billing(self, customer_id: str, data: Dict) -> Dict[str, Any]:
        """Actualiza datos de facturación del cliente"""
        # En producción actualizaría la BD
        return {"success": True}


# Herramientas del InvoiceAgent
class InvoiceGeneratorTool:
    """Herramienta de generación de facturas"""
    
    def __init__(self, invoice_api):
        self.api = invoice_api
    
    async def generate_invoice(
        self,
        order: Dict,
        tax_calculation: Dict,
        customer
    ) -> Dict[str, Any]:
        """Genera una factura"""
        # En producción llamaría a la API de facturación
        import random
        
        invoice_number = f"FC{random.randint(100000, 999999)}"
        
        return {
            "invoice_number": invoice_number,
            "order_id": order['id'],
            "customer_id": customer.customer_id,
            "date": datetime.now().strftime("%d/%m/%Y"),
            "subtotal": order['subtotal'],
            "taxes": tax_calculation['total_tax'],
            "total": order['subtotal'] + tax_calculation['total_tax'],
            "currency": "ARS",
            "pdf_url": f"https://invoices.example.com/{invoice_number}.pdf"
        }


class TaxCalculatorTool:
    """Herramienta de cálculo de impuestos"""
    
    async def calculate_taxes(self, order: Dict, customer) -> Dict[str, Any]:
        """Calcula impuestos para una orden"""
        # En producción esto sería más complejo
        subtotal = order.get('subtotal', 0)
        
        # IVA 21% (Argentina)
        iva_rate = 0.21
        iva_amount = subtotal * iva_rate
        
        return {
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "total_tax": iva_amount,
            "tax_details": [
                {
                    "name": "IVA",
                    "rate": iva_rate,
                    "amount": iva_amount
                }
            ]
        }


class InvoiceValidatorTool:
    """Herramienta de validación de facturas"""
    
    async def validate_invoice(self, invoice: Dict) -> Dict[str, Any]:
        """Valida una factura antes de enviarla"""
        errors = []
        
        # Validaciones básicas
        if not invoice.get('invoice_number'):
            errors.append("Número de factura requerido")
        
        if not invoice.get('customer_id'):
            errors.append("ID de cliente requerido")
        
        if invoice.get('total', 0) <= 0:
            errors.append("Total debe ser mayor a 0")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }


class InvoiceDeliveryTool:
    """Herramienta de entrega de facturas"""
    
    async def send_invoice(
        self,
        invoice: Dict,
        email: str,
        phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Envía factura por email y WhatsApp"""
        # En producción enviaría emails y mensajes reales
        
        delivery_results = {
            "success": True,
            "email_sent": bool(email),
            "whatsapp_sent": bool(phone),
            "delivery_time": datetime.now().isoformat()
        }
        
        return delivery_results