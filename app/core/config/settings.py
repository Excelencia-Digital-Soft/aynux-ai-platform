"""
Core Configuration Settings

Re-exports settings from the main config module for convenience.
Use this module for settings access within the core layer.
"""

from app.config.settings import Settings, get_settings

__all__ = [
    "Settings",
    "get_settings",
]
