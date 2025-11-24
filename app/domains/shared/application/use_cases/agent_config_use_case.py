"""
Agent Configuration Use Cases

Use cases for managing agent configuration (Excelencia agent modules).
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GetAgentConfigUseCase:
    """
    Use Case: Get Agent Configuration

    Retrieves current agent configuration (Excelencia modules).

    Responsibilities:
    - Read configuration from agent module
    - Return formatted configuration
    - Handle errors gracefully

    Follows SRP: Single responsibility for reading agent config
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize get agent config use case.

        Args:
            config_path: Optional path to config file (default: excelencia_agent.py)
        """
        self.config_path = config_path or self._get_default_config_path()

    def _get_default_config_path(self) -> str:
        """Get default path to Excelencia agent module."""
        return "app/agents/subagent/excelencia_agent.py"

    async def execute(self) -> Dict[str, Any]:
        """
        Get current agent configuration.

        Returns:
            Dictionary with:
                - modules: Dict of Excelencia modules
                - query_types: Dict of query type keywords
                - settings: Agent settings (model, temperature, etc.)

        Example:
            use_case = GetAgentConfigUseCase()
            config = await use_case.execute()
        """
        try:
            # Import Excelencia agent to get current configuration
            from app.agents.subagent.excelencia_agent import (
                EXCELENCIA_MODULES,
                ExcelenciaAgent,
            )

            # Create temporary instance to get settings
            temp_agent = ExcelenciaAgent()

            config = {
                "modules": EXCELENCIA_MODULES,
                "query_types": temp_agent.query_types,
                "settings": {
                    "model": temp_agent.model,
                    "temperature": temp_agent.temperature,
                    "max_response_length": temp_agent.max_response_length,
                    "use_rag": temp_agent.use_rag,
                    "rag_max_results": temp_agent.rag_max_results,
                },
                "available_document_types": [
                    "mission_vision",
                    "contact_info",
                    "software_catalog",
                    "faq",
                    "clients",
                    "success_stories",
                    "general",
                ],
            }

            logger.info("Retrieved agent configuration successfully")
            return config

        except Exception as e:
            logger.error(f"Error getting agent config: {e}")
            raise


class UpdateAgentModulesUseCase:
    """
    Use Case: Update Agent Modules Configuration

    Updates Excelencia agent modules configuration.

    Responsibilities:
    - Validate module data structure
    - Update agent configuration file
    - Backup previous configuration
    - Handle errors and rollback

    Follows SRP: Single responsibility for updating module config

    NOTE: This requires modifying the Python source file, which means
    the application needs to be restarted for changes to take effect.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize update agent modules use case.

        Args:
            config_path: Optional path to config file
        """
        self.config_path = config_path or self._get_default_config_path()

    def _get_default_config_path(self) -> str:
        """Get default path to Excelencia agent module."""
        return "app/agents/subagent/excelencia_agent.py"

    def _validate_module_structure(self, modules: Dict[str, Any]) -> bool:
        """
        Validate module data structure.

        Args:
            modules: Dict of modules to validate

        Returns:
            True if valid

        Raises:
            ValueError: If structure is invalid
        """
        required_fields = {"name", "description", "features", "target"}

        for module_id, module_data in modules.items():
            missing_fields = required_fields - set(module_data.keys())
            if missing_fields:
                raise ValueError(f"Module '{module_id}' missing required fields: {missing_fields}")

            if not isinstance(module_data["features"], list):
                raise ValueError(f"Module '{module_id}' features must be a list")

        return True

    def _generate_module_code(self, modules: Dict[str, Any]) -> str:
        """
        Generate Python code for EXCELENCIA_MODULES dictionary.

        Args:
            modules: Dict of modules

        Returns:
            Python code as string
        """
        lines = ["EXCELENCIA_MODULES = {"]

        for module_id, module_data in modules.items():
            lines.append(f'    "{module_id}": {{')
            lines.append(f'        "name": "{module_data["name"]}",')
            lines.append(f'        "description": "{module_data["description"]}",')

            # Format features list
            features_str = ", ".join(f'"{f}"' for f in module_data["features"])
            lines.append(f'        "features": [{features_str}],')

            lines.append(f'        "target": "{module_data["target"]}",')
            lines.append("    },")

        lines.append("}")

        return "\n".join(lines)

    async def execute(self, modules: Dict[str, Any], create_backup: bool = True) -> Dict[str, Any]:
        """
        Update agent modules configuration.

        Args:
            modules: New modules configuration
            create_backup: Whether to create backup of current config

        Returns:
            Dictionary with:
                - success: True if successful
                - modules_updated: Number of modules updated
                - backup_path: Path to backup file (if created)
                - requires_restart: True (always, as source code changed)

        Raises:
            ValueError: If validation fails

        Example:
            use_case = UpdateAgentModulesUseCase()
            result = await use_case.execute({
                "historia_clinica": {
                    "name": "Historia Clínica Electrónica",
                    "description": "Sistema de historias clínicas",
                    "features": ["Registro", "Consultas"],
                    "target": "Hospitales"
                }
            })
        """
        backup_path = None  # Initialize early for exception handler

        try:
            # 1. Validate module structure
            self._validate_module_structure(modules)

            # 2. Read current file
            file_path = Path(self.config_path)
            if not file_path.exists():
                raise FileNotFoundError(f"Config file not found: {self.config_path}")

            original_content = file_path.read_text(encoding="utf-8")

            # 3. Create backup if requested
            if create_backup:
                backup_path = f"{self.config_path}.backup"
                Path(backup_path).write_text(original_content, encoding="utf-8")
                logger.info(f"Created backup at: {backup_path}")

            # 4. Generate new EXCELENCIA_MODULES code
            new_modules_code = self._generate_module_code(modules)

            # 5. Replace EXCELENCIA_MODULES in file
            # Find the start and end of EXCELENCIA_MODULES definition
            lines = original_content.split("\n")
            start_idx = None
            end_idx = None
            brace_count = 0

            for i, line in enumerate(lines):
                if "EXCELENCIA_MODULES = {" in line:
                    start_idx = i
                    brace_count = 1
                elif start_idx is not None:
                    brace_count += line.count("{") - line.count("}")
                    if brace_count == 0:
                        end_idx = i
                        break

            if start_idx is None or end_idx is None:
                raise ValueError("Could not find EXCELENCIA_MODULES in config file")

            # Replace the section
            new_lines = lines[:start_idx] + new_modules_code.split("\n") + lines[end_idx + 1 :]
            new_content = "\n".join(new_lines)

            # 6. Write updated content
            file_path.write_text(new_content, encoding="utf-8")

            result = {
                "success": True,
                "modules_updated": len(modules),
                "backup_path": backup_path,
                "requires_restart": True,
                "message": (
                    "Configuration updated successfully. " "Please restart the application for changes to take effect."
                ),
            }

            logger.info(f"Updated {len(modules)} agent modules successfully")
            return result

        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Error updating agent modules: {e}")
            # Try to restore from backup if it exists
            if create_backup and backup_path and Path(backup_path).exists():
                try:
                    Path(self.config_path).write_text(Path(backup_path).read_text(encoding="utf-8"), encoding="utf-8")
                    logger.info("Restored from backup after error")
                except Exception as restore_error:
                    logger.error(f"Failed to restore from backup: {restore_error}")

            raise ValueError(f"Failed to update agent modules: {str(e)}")


class UpdateAgentSettingsUseCase:
    """
    Use Case: Update Agent Settings

    Updates Excelencia agent settings (model, temperature, etc.).

    NOTE: This is a simplified version that returns configuration.
    For production, consider using a database-backed configuration system.
    """

    async def execute(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update agent settings.

        Args:
            settings: Dictionary with settings to update:
                - model: LLM model name
                - temperature: Temperature (0.0-1.0)
                - max_response_length: Max response length
                - use_rag: Whether to use RAG
                - rag_max_results: Number of RAG results

        Returns:
            Dictionary with updated settings

        Note:
            Currently returns settings as-is. For production, implement
            database-backed configuration or environment variable updates.
        """
        try:
            # Validate settings
            if "temperature" in settings:
                temp = settings["temperature"]
                if not (0.0 <= temp <= 1.0):
                    raise ValueError("Temperature must be between 0.0 and 1.0")

            if "max_response_length" in settings:
                max_len = settings["max_response_length"]
                if max_len < 100 or max_len > 2000:
                    raise ValueError("Max response length must be between 100 and 2000")

            logger.info("Agent settings validated successfully")

            return {
                "success": True,
                "settings": settings,
                "message": (
                    "Settings validated. For production use, implement " "database-backed configuration storage."
                ),
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error updating agent settings: {e}")
            raise ValueError(f"Failed to update settings: {str(e)}")
