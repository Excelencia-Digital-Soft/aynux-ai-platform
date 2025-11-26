"""
Excelencia Domain Entities

Core business objects for the Excelencia ERP domain.
"""

from app.domains.excelencia.domain.entities.demo import Demo, DemoRequest
from app.domains.excelencia.domain.entities.module import ERPModule

__all__ = [
    "Demo",
    "DemoRequest",
    "ERPModule",
]
