import logging
import traceback
from typing import Any, Dict, Optional

from app.models.ciudadano import User
from app.models.message import Contact, WhatsAppMessage
from app.repositories.ciudadano_repository import CiudadanoRepository
from app.repositories.redis_repository import RedisRepository
from app.services.ai_service import AIService
from app.services.ciudadano_service import CiudadanoService
from app.services.tramites_service import TramitesService
from app.services.whatsapp_service import WhatsAppService
from app.utils.certificate_utils import CertificateGenerator


class ChatbotService:
    """
    Servicio principal que coordina la interacción con el chatbot
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.user_repo = CiudadanoRepository()
        # TODO: Cambiar a Pydantic en vez de Dict.
        self.redis_repo = RedisRepository[Dict[str, Any]](Dict, prefix="chat")
        self.ciudadano_service = CiudadanoService()
        self.whatsapp_service = WhatsAppService()
        self.ai_service = AIService()
        self.tramites_service = TramitesService()
        self.certificate_generator = CertificateGenerator()

    async def procesar_mensaje(
        self, message: WhatsAppMessage, contact: Contact
    ) -> Dict[str, Any]:
        """
        Procesa un mensaje entrante de WhatsApp

        Args:
            message: Mensaje entrante
            contact: Información del contacto

        Returns:
            Respuesta del procesamiento
        """
        try:
            user_number = contact.wa_id
            message_text = self._extract_message_text(message)

            # Obtener información del ciudadano
            ciudadano_info = await self.ciudadano_service.get_info_ciudadano(
                user_number
            )

            print("...CIUDADANO_INFO", ciudadano_info)

            if not ciudadano_info.get("esExitoso", False):
                # Si no se puede obtener la información del ciudadano, enviar mensaje de error
                await self.whatsapp_service.enviar_mensaje_texto(
                    user_number,
                    "Lo siento, no se pudo obtener su información. Por favor, acérquese a las oficinas municipales para registrarse o actualizar sus datos.",
                )
                return {
                    "status": "error",
                    "message": "No se pudo obtener información del ciudadano",
                }

            # Extraer datos del ciudadano
            # {'id': 18, 'idMunicipio': 5, 'idLocalidad': 1, 'idTipoDocumento': 1, 'numeroDocumento': '41122633', 'cuil': '-', 'nombres': 'Mateo Jorge', 'apellidos': 'Sirerol Sanchez', 'calle': 'Hipolito Yrigoyen', 'numero': '27', 'orientacion': 'SUR', 'referencias': 'camioneta', 'telefono': '2644962105', 'celular': '2645404301', 'email': 'msirerol@gmail.com', 'fechaAlta': '2025-05-02T00:00:00', 'estadoId': 1, 'numeroContribuyente': 0}
            ciudadano_data = ciudadano_info.get("datos", {})
            nombre = ciudadano_data.get("nombre", "")
            apellido = ciudadano_data.get("apellido", "")
            nombre_completo = f"{nombre} {apellido}".strip()
            documento = ciudadano_data.get("documento", "")
            id_ciudadano = ciudadano_data.get("id_ciudadano", "")

            # Obtener o crear usuario
            user = await self._get_or_create_user(user_number, id_ciudadano)
            estado_actual = user.state.state

            # Guardar mensaje en el historial de conversación
            self.redis_repo.save_conversation_history(
                user_number, "persona", message_text
            )
            historial = self.redis_repo.get_conversation_history(user_number)
            historial_str = "\n".join(
                [f"{msg['role']}: {msg['content']}" for msg in historial]
            )

            # Lista de trámites disponibles
            tramites = await self.tramites_service.get_tramites_disponibles()
            tramites_lista = tramites.get("data", [])

            # Procesar según el estado actual
            if estado_actual == "inicio":
                # Actualizar estado a verificar
                self.user_repo.update_user_state(user_number, "verificar")
                await self.whatsapp_service.enviar_mensaje_texto(
                    user_number,
                    f"Hola, ¿es usted {nombre_completo}? Por favor, confirme para continuar.",
                )
                return {"status": "success", "state": "verificar"}

            elif estado_actual == "verificar":
                # Verificar respuesta del usuario
                resp = await self._procesar_user_verificando(
                    user_number, message_text, id_ciudadano
                )
                await self.whatsapp_service.enviar_mensaje_texto(user_number, resp)
                return {
                    "status": "success",
                    "state": "verificado"
                    if "Gracias por confirmar" in resp
                    else "no_verificado",
                }

            else:
                # Generar respuesta con IA para cualquier otro estado
                mensaje_respuesta = await self.ai_service.generate_principal_mensaje(
                    nombre_completo,
                    "activo",  # Estado del ciudadano (simplificado por ahora)
                    estado_actual,
                    tramites_lista,
                    user.state.verificado,
                    documento,
                    message_text,
                    historial_str,
                )

                # Guardar respuesta en el historial de conversación
                self.redis_repo.save_conversation_history(
                    user_number, "bot", mensaje_respuesta.mensaje
                )

                # Procesar según el estado devuelto por la IA
                if mensaje_respuesta.estado == "consulta_deuda":
                    response = await self._procesar_consulta_deuda(
                        user_number, id_ciudadano
                    )
                    return response

                elif mensaje_respuesta.estado == "certificados":
                    response = await self._procesar_solicitud_certificado(
                        user_number, nombre_completo, documento, id_ciudadano
                    )
                    return response

                elif mensaje_respuesta.estado == "tramites":
                    response = await self._procesar_consulta_tramites(
                        user_number, id_ciudadano
                    )
                    return response

                else:
                    # Actualizar estado del usuario y enviar respuesta
                    self.user_repo.update_user_state(
                        user_number, mensaje_respuesta.estado
                    )
                    await self.whatsapp_service.enviar_mensaje_texto(
                        user_number, mensaje_respuesta.mensaje
                    )
                    return {"status": "success", "state": mensaje_respuesta.estado}

        except Exception as e:
            tb = traceback.format_exc()
            self.logger.error(
                f"Error en el procesamiento del mensaje en la línea {e.__traceback__.tb_lineno}: {e}\n{tb}"
            )
            # En producción, podríamos enviar un mensaje genérico de error
            return {"status": "error", "message": str(e)}

    async def _get_or_create_user(
        self, user_number: str, id_ciudadano: Optional[str] = None
    ) -> User:
        """
        Obtiene un usuario existente o crea uno nuevo
        """
        user = self.user_repo.get_user(user_number)
        if not user:
            user = self.user_repo.create_user(user_number, id_ciudadano)
        return user

    async def _procesar_user_verificando(
        self, user_number: str, mensaje: str, id_ciudadano: str
    ) -> str:
        """
        Procesa la respuesta del usuario durante la verificación
        """
        respuesta = await self.ai_service.verificar_ciudadano(mensaje)

        if respuesta == "afirmacion":
            self.user_repo.update_user(user_number, "verificado", True, id_ciudadano)
            return "Gracias por confirmar tu identidad. Soy el asistente virtual de la municipalidad. ¿En qué puedo ayudarte?"
        else:
            self.user_repo.update_user(user_number, "noverificado", False, id_ciudadano)
            return "Lo siento, parece que hubo un error. Por favor, comunícate con atención al ciudadano."

    async def _procesar_consulta_deuda(
        self, user_number: str, id_ciudadano: str
    ) -> Dict[str, Any]:
        """
        Procesa una consulta de deuda
        """
        try:
            deuda = await self.tramites_service.obtener_deuda_contribuyente(
                id_ciudadano
            )
            if not deuda or not deuda.get("success"):
                raise ValueError("No se obtuvo información de deuda válida")

            # Formatear mensaje de deuda
            deuda_data = deuda.get("data", {})
            if isinstance(deuda_data, list) and deuda_data:
                total_deuda = sum(item.get("monto", 0) for item in deuda_data)
                mensaje = f"Su deuda total es de ${total_deuda:.2f}. Detalles:\n\n"

                for item in deuda_data:
                    mensaje += f"- {item.get('concepto', 'Concepto no especificado')}: ${item.get('monto', 0):.2f} (Vencimiento: {item.get('vencimiento', 'No especificado')})\n"
            else:
                mensaje = "No se encontraron deudas pendientes."

            await self.whatsapp_service.enviar_mensaje_texto(user_number, mensaje)
            return {"status": "success", "state": "consulta_deuda"}

        except Exception as e:
            self.logger.error(f"Error al obtener información de deuda: {e}")
            mensaje = (
                "No se pudo obtener información sobre su deuda, intente nuevamente."
            )
            await self.whatsapp_service.enviar_mensaje_texto(user_number, mensaje)
            return {"status": "error", "message": str(e)}

    async def _procesar_solicitud_certificado(
        self, user_number: str, nombre_completo: str, documento: str, id_ciudadano: str
    ) -> Dict[str, Any]:
        """
        Procesa una solicitud de certificado
        """
        try:
            imagen = await self.certificate_generator.generate_qr_certificate(
                nombre_completo, documento, id_ciudadano
            )

            if not imagen:
                raise ValueError("No se pudo generar la imagen del certificado")

            await self.whatsapp_service.enviar_documento(
                user_number, imagen, "Certificado de Residencia"
            )
            await self.whatsapp_service.enviar_mensaje_texto(
                user_number,
                "Aquí tiene su certificado de residencia. Este documento tiene validez de 30 días.",
            )
            return {"status": "success", "state": "certificados"}

        except Exception as e:
            self.logger.error(f"Error al generar/enviar certificado: {e}")
            mensaje = "No se pudo generar su certificado, intente nuevamente o acérquese a la municipalidad."
            await self.whatsapp_service.enviar_mensaje_texto(user_number, mensaje)
            return {"status": "error", "message": str(e)}

    async def _procesar_consulta_tramites(
        self, user_number: str, id_ciudadano: str
    ) -> Dict[str, Any]:
        """
        Procesa una consulta de trámites disponibles
        """
        try:
            tramites = await self.tramites_service.get_tramites_disponibles()
            if not tramites or not tramites.get("success"):
                raise ValueError("No se pudo obtener la lista de trámites")

            tramites_lista = tramites.get("data", [])
            if not tramites_lista:
                mensaje = "No hay trámites disponibles en este momento."
            else:
                mensaje = "Los trámites disponibles son:\n\n"
                for tramite in tramites_lista:
                    mensaje += f"- {tramite.get('nombre', 'Sin nombre')}: {tramite.get('descripcion', 'Sin descripción')}\n"

                mensaje += "\n¿Desea iniciar alguno de estos trámites?"

            await self.whatsapp_service.enviar_mensaje_texto(user_number, mensaje)
            return {"status": "success", "state": "tramites"}

        except Exception as e:
            self.logger.error(f"Error al obtener trámites: {e}")
            mensaje = "No se pudo obtener la lista de trámites disponibles, intente nuevamente."
            await self.whatsapp_service.enviar_mensaje_texto(user_number, mensaje)
            return {"status": "error", "message": str(e)}

    def _extract_message_text(self, message: WhatsAppMessage) -> str:
        """
        Extrae el texto del mensaje según su tipo
        """
        if message.type == "text" and message.text:
            return message.text.body
        elif message.type == "interactive" and message.interactive:
            if (
                message.interactive.type == "button_reply"
                and message.interactive.button_reply
            ):
                return message.interactive.button_reply.title
            elif (
                message.interactive.type == "list_reply"
                and message.interactive.list_reply
            ):
                return message.interactive.list_reply.title

        # Si no podemos extraer el texto, retornamos un mensaje vacío
        return ""
