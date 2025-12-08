"""
This module is deprecated and will be removed in a future version.

Please use the `PromptManager` from `app.prompts.manager` instead, which
loads prompts from YAML templates.
"""
from app.core.shared.deprecation import deprecated

@deprecated(
    reason="Legacy monolithic prompt service no longer maintained",
    replacement="Use PromptManager from app.prompts.manager with YAML templates",
    removal_version="3.0.0",
)
class PromptService:
    pass
