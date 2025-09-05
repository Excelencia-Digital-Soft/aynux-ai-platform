"""
AI Data Integration for LangGraph Agents.

This module provides integration points for LangGraph agents to access
user-specific data through the AI Data Pipeline Service.
"""

import logging
from typing import Any, Dict, List, Optional

from app.services.ai_data_pipeline_service import (
    PipelineExecutionContext,
    create_ai_data_pipeline_service,
    get_user_context_for_agent,
)

logger = logging.getLogger(__name__)


class AgentDataContext:
    """
    Data context provider for LangGraph agents.

    This class provides a simple interface for agents to access
    user-specific data and enhance their responses with relevant context.
    """

    def __init__(self):
        self.pipeline_service = create_ai_data_pipeline_service(
            {"chunk_size": 800, "max_records": 5000, "enable_auto_refresh": True, "refresh_interval_hours": 12}
        )
        self._initialized_users = set()

    async def ensure_user_data_ready(self, user_id: str, priority_tables: Optional[List[str]] = None) -> bool:
        """
        Ensure user data is available in the vector store.

        Args:
            user_id: User identifier (phone number, etc.)
            priority_tables: Tables to prioritize for this user

        Returns:
            True if data is ready for use
        """
        try:
            # Check if we've already initialized this user recently
            if user_id in self._initialized_users:
                return True

            # Determine which tables to process
            tables_to_process = priority_tables or ["customers", "products", "orders", "conversations"]

            # Filter to only existing tables
            available_tables = self.pipeline_service.get_available_tables()
            tables_to_process = [t for t in tables_to_process if t in available_tables]

            if not tables_to_process:
                logger.warning(f"No suitable tables found for user {user_id}")
                return False

            # Setup pipeline context
            context = PipelineExecutionContext(
                user_id=user_id,
                tables=tables_to_process,
                chunk_size=800,
                force_refresh=False,  # Only refresh if needed
            )

            # Execute pipeline setup
            result = await self.pipeline_service.setup_user_data_pipeline(context)

            if result.success:
                self._initialized_users.add(user_id)
                logger.info(f"Successfully initialized data for user {user_id}")
                return True
            else:
                logger.error(f"Failed to initialize data for user {user_id}: {result.errors}")
                return False

        except Exception as e:
            logger.error(f"Error ensuring user data ready: {e}")
            return False

    async def get_context_for_query(
        self, user_id: str, query: str, context_type: str = "general", max_results: int = 5
    ) -> str:
        """
        Get relevant context for a user query.

        Args:
            user_id: User identifier
            query: User's query or intent
            context_type: Type of context needed (general, product, order, etc.)
            max_results: Maximum number of relevant documents

        Returns:
            Formatted context string for AI agent
        """
        try:
            # Ensure user data is available
            await self.ensure_user_data_ready(user_id)

            # Determine table filters based on context type
            table_filters = self._get_table_filters_for_context(context_type)

            # Get relevant context
            context_text = await get_user_context_for_agent(
                user_id=user_id, query=query, table_filters=table_filters, max_results=max_results
            )

            return context_text

        except Exception as e:
            logger.error(f"Error getting context for query: {e}")
            return f"Error retrieving user context: {str(e)}"

    async def get_user_purchase_history(self, user_id: str, limit: int = 10) -> str:
        """Get formatted user purchase history."""
        return await self.get_context_for_query(
            user_id=user_id, query="purchase history orders products bought", context_type="orders", max_results=limit
        )

    async def get_user_product_preferences(self, user_id: str, category: Optional[str] = None) -> str:
        """Get user product preferences and interests."""
        query = f"product preferences interests {category}" if category else "product preferences interests"
        return await self.get_context_for_query(user_id=user_id, query=query, context_type="products", max_results=8)

    async def get_conversation_context(self, user_id: str, recent_only: bool = True) -> str:
        """Get relevant conversation history context."""
        query = "recent conversations messages history" if recent_only else "conversation history"
        return await self.get_context_for_query(
            user_id=user_id, query=query, context_type="conversations", max_results=5
        )

    def _get_table_filters_for_context(self, context_type: str) -> Optional[List[str]]:
        """Get table filters based on context type."""
        filters_map = {
            "general": None,  # Search all tables
            "products": ["products", "categories"],
            "orders": ["orders", "order_items", "products"],
            "conversations": ["conversations", "messages"],
            "customer": ["customers", "customer_preferences"],
            "support": ["conversations", "support_tickets"],
        }

        return filters_map.get(context_type)


# Agent Integration Mixins
class DataEnhancedAgentMixin:
    """
    Mixin class for LangGraph agents to easily access user data.

    Add this mixin to any agent class to enable data-enhanced responses.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data_context = AgentDataContext()

    async def get_user_context(self, user_id: str, query: str, context_type: str = "general") -> str:
        """Get user-specific context for the current query."""
        return await self.data_context.get_context_for_query(user_id=user_id, query=query, context_type=context_type)

    async def enhance_prompt_with_context(
        self, base_prompt: str, user_id: str, query: str, context_type: str = "general"
    ) -> str:
        """Enhance an AI prompt with relevant user context."""
        user_context = await self.get_user_context(user_id, query, context_type)

        if "No relevant" not in user_context and "Error" not in user_context:
            enhanced_prompt = f"""{base_prompt}

USUARIO INFORMACIÓN RELEVANTE:
{user_context}

Usa esta información del usuario para personalizar tu respuesta cuando sea relevante."""
            return enhanced_prompt
        else:
            return base_prompt


# Convenience Functions for Agents
async def get_enhanced_prompt_for_agent(agent_type: str, base_prompt: str, user_id: str, user_query: str) -> str:
    """
    Convenience function to get an enhanced prompt for any agent.

    Args:
        agent_type: Type of agent (product, category, support, etc.)
        base_prompt: Base prompt template
        user_id: User identifier
        user_query: User's query

    Returns:
        Enhanced prompt with user context
    """
    data_context = AgentDataContext()

    # Map agent types to context types
    context_type_map = {
        "product": "products",
        "category": "products",
        "order": "orders",
        "support": "support",
        "tracking": "orders",
        "invoice": "orders",
        "promotion": "products",
    }

    context_type = context_type_map.get(agent_type, "general")

    user_context = await data_context.get_context_for_query(
        user_id=user_id,
        query=user_query,
        context_type=context_type,
        max_results=3,  # Limit for prompt efficiency
    )

    if "No relevant" not in user_context and "Error" not in user_context:
        return f"""{base_prompt}

CONTEXTO DEL USUARIO:
{user_context}

INSTRUCCIONES:
- Usa la información del usuario para personalizar tu respuesta
- Si no hay información relevante del usuario, responde normalmente
- Sé específico y útil basándote en el historial del usuario"""

    return base_prompt


async def initialize_user_data_pipeline(user_id: str) -> bool:
    """
    Initialize the data pipeline for a new user.

    This should be called when a user first interacts with the system
    or when you want to refresh their data.

    Args:
        user_id: User identifier

    Returns:
        True if initialization was successful
    """
    data_context = AgentDataContext()
    return await data_context.ensure_user_data_ready(user_id)


async def get_user_summary_context(user_id: str) -> Dict[str, str]:
    """
    Get a comprehensive summary of user context across different areas.

    Args:
        user_id: User identifier

    Returns:
        Dictionary with different context types
    """
    data_context = AgentDataContext()

    context_summary = {}

    try:
        # Get different types of context
        context_types = [
            ("purchase_history", "purchase history recent orders"),
            ("product_preferences", "product preferences categories interests"),
            ("conversation_history", "recent conversations interactions"),
            ("support_history", "support tickets help requests"),
        ]

        for context_name, query in context_types:
            try:
                context_text = await data_context.get_context_for_query(user_id=user_id, query=query, max_results=3)
                context_summary[context_name] = context_text
            except Exception as e:
                logger.error(f"Error getting {context_name} for user {user_id}: {e}")
                context_summary[context_name] = f"Error retrieving {context_name}"

        return context_summary

    except Exception as e:
        logger.error(f"Error getting user summary context: {e}")
        return {"error": str(e)}


# Example usage in an agent
class EnhancedProductAgent(DataEnhancedAgentMixin):
    """
    Example of how to enhance the ProductAgent with user data.

    This is a demonstration of how to integrate the data pipeline
    with existing LangGraph agents.
    """
    
    def __init__(self):
        self.name = "enhanced_product_agent"

    async def _process_internal_with_context(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced processing with user context."""

        # Extract user ID from state
        user_id = state_dict.get("user_phone") or state_dict.get("user_id")

        if not user_id:
            # Fall back to normal processing
            return await self._process_internal_without_context(message, state_dict)

        try:
            # Get enhanced prompt with user context
            base_prompt = f"El usuario pregunta sobre productos: {message}"

            enhanced_prompt = await self.enhance_prompt_with_context(
                base_prompt=base_prompt, user_id=user_id, query=message, context_type="products"
            )

            # Use enhanced prompt for AI processing
            # (integrate with your existing AI processing logic)

            return {
                "messages": [{"role": "assistant", "content": "Enhanced response with user context"}],
                "current_agent": self.name,
                "enhanced_with_context": True,
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in enhanced processing: {e}")
            # Fall back to normal processing
            return await self._process_internal_without_context(message, state_dict)

    async def _process_internal_without_context(self, message: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Normal processing without user context."""
        # Original agent processing logic
        return {
            "messages": [{"role": "assistant", "content": "Standard response"}],
            "current_agent": self.name,
            "is_complete": True,
        }

