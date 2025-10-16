"""
Ejemplo de migración del IntentRouter al sistema de prompts centralizado.

Este archivo muestra cómo refactorizar el código existente.
"""

from typing import Any, Dict, Optional

from app.prompts import PromptManager, PromptRegistry


class IntentRouterRefactored:
    """
    Versión refactorizada del IntentRouter usando PromptManager.

    ANTES: Prompts hardcodeados en el código
    DESPUÉS: Prompts centralizados y configurables
    """

    def __init__(self, ollama=None, config: Optional[Dict[str, Any]] = None):
        self.ollama = ollama
        self.config = config or {}

        # ===== NUEVO: Usar PromptManager =====
        self.prompt_manager = PromptManager(
            cache_size=self.config.get("prompt_cache_size", 500), cache_ttl=self.config.get("prompt_cache_ttl", 3600)
        )

        # El resto de la configuración permanece igual
        self.confidence_threshold = self.config.get("confidence_threshold", 0.75)
        self.fallback_agent = self.config.get("fallback_agent", "support_agent")

    async def analyze_intent_with_llm(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analiza intención usando LLM.

        CAMBIOS PRINCIPALES:
        1. Prompts cargados desde PromptManager
        2. Variables extraídas a diccionario
        3. Templates renderizados automáticamente
        """

        # ===== ANTES =====
        # system_prompt = """
        # You are an expert intent classifier...
        # """
        #
        # user_prompt = f"""
        # ### Customer Data
        # {customer_data}
        # ...
        # """

        # ===== DESPUÉS =====
        try:
            # 1. Obtener system prompt desde el manager
            system_prompt = await self.prompt_manager.get_prompt(PromptRegistry.INTENT_ANALYZER_SYSTEM)

            # 2. Preparar variables para el user prompt
            variables = {
                "customer_data": self._format_customer_data(state_dict.get("customer_data")),
                "context_info": self._format_context_info(state_dict.get("conversation_data")),
                "message": message,
            }

            # 3. Obtener user prompt renderizado
            user_prompt = await self.prompt_manager.get_prompt(PromptRegistry.INTENT_ANALYZER_USER, variables=variables)

            # 4. Llamar a Ollama (sin cambios)
            response_text = await self.ollama.generate_response(
                system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.5
            )

            # 5. Procesar respuesta (sin cambios)
            # ... resto del código igual ...

            return {"success": True}

        except Exception as e:
            print(f"Error in LLM analysis: {e}")
            return {"success": False, "error": str(e)}

    def _format_customer_data(self, customer_data: Optional[Dict[str, Any]]) -> str:
        """Helper para formatear datos del cliente."""
        if not customer_data:
            return "No hay datos de cliente disponibles"

        import json

        return json.dumps(customer_data, indent=2)

    def _format_context_info(self, conversation_data: Optional[Dict[str, Any]]) -> str:
        """Helper para formatear información de contexto."""
        if not conversation_data:
            return "No hay contexto de conversación"

        context_parts = []
        if channel := conversation_data.get("channel"):
            context_parts.append(f"Channel: {channel}")
        if language := conversation_data.get("language"):
            context_parts.append(f"Language: {language}")

        return ", ".join(context_parts) if context_parts else "Sin contexto adicional"


# ===== EJEMPLO DE USO =====


async def compare_approaches():
    """Compara el approach antiguo vs el nuevo."""

    print("=" * 70)
    print("COMPARACIÓN: ANTES vs DESPUÉS")
    print("=" * 70)

    # Setup
    message = "Quiero comprar una laptop gamer"
    state_dict = {
        "customer_data": {"name": "Juan", "tier": "VIP"},
        "conversation_data": {"channel": "whatsapp", "language": "es"},
    }

    print("\n📋 ANTES - Prompt Hardcodeado:")
    print("-" * 70)
    print("""
    def analyze_intent_with_llm(message, state_dict):
        # ❌ Prompt hardcodeado en el código
        system_prompt = '''
        You are an expert intent classifier for an e-commerce assistant.
        Your task is to analyze the context and user message...
        '''

        # ❌ Difícil de mantener
        # ❌ No versionado
        # ❌ No cacheable
        # ❌ Requiere redeploy para cambios

        user_prompt = f'''
        ### Customer Data
        {json.dumps(customer_data, indent=2)}

        ### Current User Message
        "{message}"
        '''

        response = await ollama.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )
        return response
    """)

    print("\n✅ DESPUÉS - Sistema Centralizado:")
    print("-" * 70)
    print("""
    def analyze_intent_with_llm(message, state_dict):
        # ✅ Prompts centralizados
        system_prompt = await self.prompt_manager.get_prompt(
            PromptRegistry.INTENT_ANALYZER_SYSTEM
        )

        # ✅ Variables estructuradas
        variables = {
            "customer_data": self._format_customer_data(state_dict.get("customer_data")),
            "context_info": self._format_context_info(state_dict.get("conversation_data")),
            "message": message
        }

        # ✅ Renderizado automático
        user_prompt = await self.prompt_manager.get_prompt(
            PromptRegistry.INTENT_ANALYZER_USER,
            variables=variables
        )

        # ✅ Mantenible: editar YAML sin tocar código
        # ✅ Versionado: historial completo de cambios
        # ✅ Cacheable: performance mejorada
        # ✅ Dinámico: cambios sin redeploy

        response = await ollama.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )
        return response
    """)

    print("\n📊 BENEFICIOS:")
    print("-" * 70)
    benefits = [
        ("Mantenibilidad", "Prompts en YAML, fáciles de editar"),
        ("Versionado", "Historial completo, rollback posible"),
        ("Performance", "Caché inteligente reduce latencia"),
        ("Flexibilidad", "Prompts dinámicos sin redeploy"),
        ("Colaboración", "Equipo puede editar prompts"),
        ("Testing", "A/B testing de diferentes versiones"),
        ("Auditoría", "Tracking de cambios y performance"),
        ("Type-Safety", "Registry con autocompletado"),
    ]

    for benefit, description in benefits:
        print(f"  ✅ {benefit:15s} → {description}")


# ===== GUÍA DE MIGRACIÓN PASO A PASO =====


def print_migration_guide():
    """Imprime guía de migración."""
    print("\n\n" + "=" * 70)
    print("GUÍA DE MIGRACIÓN PASO A PASO")
    print("=" * 70)

    steps = [
        (
            "1. Instalar PromptManager",
            """
        from app.prompts import PromptManager, PromptRegistry

        class YourService:
            def __init__(self):
                self.prompt_manager = PromptManager()
        """,
        ),
        (
            "2. Identificar prompts hardcodeados",
            """
        # Buscar en tu código:
        - Strings multilínea con f-strings
        - Variables tipo "system_prompt", "user_prompt"
        - Prompts largos (>100 caracteres)
        - Prompts con lógica de templating manual
        """,
        ),
        (
            "3. Extraer a variables",
            """
        # Crear diccionario de variables
        variables = {
            "message": message,
            "context": context,
            "user_data": user_data
        }
        """,
        ),
        (
            "4. Usar PromptManager",
            """
        # Reemplazar prompt hardcodeado
        system_prompt = await self.prompt_manager.get_prompt(
            PromptRegistry.YOUR_PROMPT_KEY,
            variables=variables
        )
        """,
        ),
        (
            "5. Verificar y testear",
            """
        # Asegurarse de que:
        - Variables coincidan con template
        - Prompts se carguen correctamente
        - Funcionalidad no cambia
        - Performance mejora con caché
        """,
        ),
    ]

    for step, code in steps:
        print(f"\n{step}")
        print("-" * 70)
        print(code)


if __name__ == "__main__":
    import asyncio

    async def main():
        await compare_approaches()
        print_migration_guide()

        print("\n\n" + "=" * 70)
        print("¡MIGRACIÓN COMPLETA!")
        print("=" * 70)
        print("\nPróximos pasos:")
        print("1. Aplicar mismo patrón a otros servicios")
        print("2. Crear prompts dinámicos para casos especiales")
        print("3. Configurar A/B testing")
        print("4. Monitorear métricas de performance")

    asyncio.run(main())
