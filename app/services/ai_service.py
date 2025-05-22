import json
import logging
import re
from typing import Optional

import httpx
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from app.config.settings import get_settings
from app.models.ciudadano import ChatbotResponse

logger = logging.getLogger(__name__)


class AIService:
    """
    Servicio para interactuar con modelos de IA generativa
    """

    def __init__(self):
        self.settings = get_settings()
        self.model = self.settings.OLLAMA_API_MODEL

    async def generate_principal_mensaje(
        self,
        nombre_completo: str,
        estado: str,
        estado_conversacion: str,
        tramites: list,
        verificado: bool,
        documento: str,
        message: str,
        historial: Optional[str] = None,
    ) -> ChatbotResponse:
        """
        Genera un mensaje principal utilizando el modelo de IA
        """
        prompt = f"""
        Eres un asistente virtual de la municipalidad. Tu función principal es ayudar a los ciudadanos con trámites y consultas municipales.
        
        Información del ciudadano:
        - Nombre: {nombre_completo}
        - Documento: {documento}
        - Estado: {estado}
        - Estado de Conversación: {estado_conversacion}
        - Verificado: {verificado}
        - Historial de mensajes: {historial or "No hay historial disponible"}

        Trámites disponibles:
        {",".join([str(tramite) for tramite in tramites])}

        NOTAS IMPORTANTES:
        1. Información del ciudadano:
        Nombre: Nombre completo del ciudadano
        Documento: Número de documento del ciudadano
        Estado: Representa si el ciudadano está activo en el sistema municipal
        Verificado: Indica si el ciudadano ya confirmó su identidad
        Estado de Conversación: Representa el estado actual de la conversación:
                                - inicio: Primera interacción, se verifica identidad
                                - verificar: Para validación de datos
                                - verificado: Identidad confirmada, puede continuar
                                - consulta_deuda: Consulta de deudas municipales
                                - certificados: Solicitud de certificados (residencia, etc.)
                                - tramites: Información o inicio de trámites
                                - reclamos: Registro de reclamos municipales
                                - turnos: Solicitud o consulta de turnos
        
        Funcionamiento:
        1_ Identificación del ciudadano:
        Se identifica al ciudadano cuando el estado es "inicio", preguntando si es la persona con los datos proporcionados.
        Si confirma, se cambia a "verificado" y se le da la bienvenida.
        Cuando esté verificado, se le trata por su nombre y no es necesario verificar nuevamente.
        Siempre preguntar en qué puede ayudar mientras su estado sea "activo" y esté "verificado".

        2_ Trámites:
        No mencionar todos los trámites al inicio, solo si el ciudadano pregunta por ellos.
        Si pregunta por trámites, mostrar la lista disponible y preguntar si desea iniciar alguno.

        3_ Lenguaje y tono:
        Respuestas claras, amigables y profesionales.
        Conciso pero informativo para que el usuario tome decisiones.

        **IMPORTANTE**:  
        Siempre responde en **formato JSON** con la siguiente estructura:  
        {{
        "mensaje": "Texto de la respuesta del chatbot",
        "estado": "Nuevo estado de la conversación"
        }}

        Estados posibles:
        - inicio: primera interacción
        - verificar: verificación pendiente
        - verificado: identidad confirmada, estado general de conversación
        - consulta_deuda: cuando pregunta por deudas municipales
        - certificados: cuando solicita certificados (residencia, etc.)
        - tramites: cuando pregunta por trámites disponibles
        - reclamos: cuando quiere hacer un reclamo (basura, alumbrado, etc.)
        - turnos: cuando solicita turnos para oficinas municipales
        """

        prompt_completo = f"{prompt}\n\nUsuario: {message}\nChatbot:"

        # Generar respuesta con el modelo
        response = await self._generate_content(prompt_completo)

        # Procesar la respuesta
        return self._procesar_respuesta(response)

    async def verificar_ciudadano(self, mensaje: str) -> str:
        """
        Verifica si la respuesta del usuario es una afirmación o negación
        """
        prompt = """
        Eres un asistente virtual que debe verificar una respuesta y clasificarla en afirmacion o negacion.

        El usuario responderá si es él o no. Tu tarea es clasificar su respuesta en una de estas categorías:

        - "afirmacion" → Si el usuario confirma que es él (ejemplo: "Sí", "Soy yo", "Correcto", "Así es").
        - "negacion" → Si el usuario niega que es él (ejemplo: "No", "No soy yo", "Se equivocaron").
        - "invalido" → Si la respuesta es confusa o irrelevante (ejemplo: "Hola", "Quiero saber algo más", "??").

        ### **Ejemplo de respuestas esperadas:**
        Usuario: "Sí, soy yo" → Respuesta: **afirmacion**  
        Usuario: "No, se equivocaron" → Respuesta: **negacion**  
        Usuario: "Hola, ¿cómo estás?" → Respuesta: **invalido**

        Devuelve únicamente una de las palabras: **afirmacion**, **negacion** o **invalido**, sin agregar explicaciones.
        """

        response = await self._generate_content(prompt + f"\nUsuario: {mensaje}")
        return response.strip().lower()

    async def _generate_content(
        self, prompt: str, model: Optional[str] = None, temperature: float = 0.2
    ) -> str:
        """
        Procesa una consulta con Ollama de forma simplificada y devuelve el resultado completo.

        Args:
            prompt: Texto completo del prompt
            model: Modelo a utilizar (opcional, usa el predeterminado si no se especifica)
            temperature: Nivel de creatividad (0.0 a 1.0)

        Returns:
            Respuesta completa del modelo
        """
        try:
            # Usar modelo predeterminado si no se especifica
            if not model:
                model = self.model

            # Configurar el modelo Ollama
            chat_model = ChatOllama(
                model=model,
                temperature=temperature,
                top_k=0,
                top_p=0,
                num_gpu=50,
                verbose=False,  # Cambiado a False para reducir logs
            )

            # Intentar ejecutar el modelo
            try:
                # Crear el prompt template simple
                prompt_template = ChatPromptTemplate.from_template(prompt)

                # Configurar la cadena simple sin historial ni streaming
                chain = prompt_template | chat_model | StrOutputParser()

                # Ejecutar la cadena y retornar el resultado completo
                result = await chain.ainvoke({})
                return result
            except httpx.ConnectError:
                return "ERROR_OLLAMA_CONNECTION_FAILED: No se pudo establecer conexión con el servicio Ollama."
            except httpx.ReadTimeout:
                return "ERROR_OLLAMA_TIMEOUT: Tiempo de espera agotado al comunicarse con Ollama."

        except Exception as e:
            error_msg = f"Error procesando consulta con Ollama: {str(e)}"
            logger.error(error_msg)
            return f"ERROR_OLLAMA_GENERAL: {error_msg}"

    @staticmethod
    def _procesar_respuesta(mensaje: str) -> ChatbotResponse:
        """
        Procesa la respuesta del modelo de IA
        """
        try:
            if not mensaje.strip():
                raise ValueError("La respuesta del chatbot está vacía.")

            # Buscar si el mensaje contiene JSON en formato de bloque de código
            json_match = re.search(r"```json\s*(\{.*?})\s*```", mensaje, re.DOTALL)
            if json_match:
                mensaje = json_match.group(1)

            # Decodificar el JSON
            response_data = json.loads(mensaje)

            # Validar y crear el objeto ChatbotResponse
            return ChatbotResponse(
                mensaje=response_data.get(
                    "mensaje", "Lo siento, hubo un error en mi respuesta."
                ),
                estado=response_data.get("estado", "verificado"),
            )
        except (json.JSONDecodeError, KeyError) as e:
            # En caso de error, devolver una respuesta por defecto
            print(f"Error al procesar la respuesta del chatbot: {e}")
            return ChatbotResponse(
                mensaje=mensaje
                if mensaje
                else "Lo siento, hubo un error en mi respuesta.",
                estado="verificado",
            )
