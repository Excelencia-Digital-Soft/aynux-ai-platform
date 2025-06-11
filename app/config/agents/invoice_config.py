from .agent_config import AgentConfig


class InvoiceAgentConfig(AgentConfig):
    """Configuración específica para el agente de facturación"""

    auto_generate_invoice: bool = True
    send_email: bool = False  # Para WhatsApp principalmente
    payment_methods_shown: int = 3
