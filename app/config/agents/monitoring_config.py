from typing import Dict

from pydantic import BaseModel, Field


class MonitoringConfig(BaseModel):
    """Configuración de monitoreo"""

    enable_metrics: bool = True
    log_conversations: bool = True
    performance_tracking: bool = True
    alert_thresholds: Dict[str, float] = Field(
        default_factory=lambda: {"response_time_ms": 5000, "error_rate": 0.05, "memory_usage_mb": 512}
    )
