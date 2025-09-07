"""
Monitoring module for ConversaShop LangSmith integration.

This module provides comprehensive monitoring capabilities including:
- Real-time dashboard data generation
- Advanced alerting with multiple notification channels
- Alert correlation and escalation management
"""

from .langsmith_dashboard import (
    ConversaShopMonitor,
    DashboardData,
    Alert,
    AlertSeverity,
    AlertStatus,
    get_monitor
)

from .alerts import (
    ConversaShopAlertManager,
    NotificationService,
    AlertCorrelationEngine,
    NotificationChannel,
    EscalationLevel,
    AlertRule,
    EscalationPolicy,
    get_alert_manager
)

__all__ = [
    # Dashboard
    "ConversaShopMonitor",
    "DashboardData",
    "Alert",
    "AlertSeverity", 
    "AlertStatus",
    "get_monitor",
    
    # Alerting
    "ConversaShopAlertManager",
    "NotificationService",
    "AlertCorrelationEngine",
    "NotificationChannel",
    "EscalationLevel",
    "AlertRule",
    "EscalationPolicy",
    "get_alert_manager"
]