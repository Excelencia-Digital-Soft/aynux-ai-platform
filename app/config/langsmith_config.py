"""
LangSmith configuration and integration for ConversaShop.

This module provides comprehensive tracing, monitoring, and evaluation
capabilities for the LangGraph multi-agent system.
"""

import logging
import os
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, Optional

from langchain_core.tracers.context import tracing_v2_enabled
from langsmith import Client
from langsmith.run_helpers import traceable
from langsmith.schemas import Example
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LangSmithConfig(BaseModel):
    """Configuration for LangSmith integration."""

    # API Configuration
    api_key: Optional[str] = Field(default=None, description="LangSmith API key")
    api_url: str = Field(default="https://api.smith.langchain.com", description="LangSmith API URL")

    # Project Configuration
    project_name: str = Field(default="conversashop-production", description="LangSmith project name")
    dataset_name: str = Field(default="conversashop-evals", description="Default dataset name")

    # Tracing Configuration
    tracing_enabled: bool = Field(default=True, description="Enable tracing")
    trace_sample_rate: float = Field(default=1.0, description="Sampling rate for traces (0.0 to 1.0)")
    verbose_tracing: bool = Field(default=False, description="Enable verbose tracing")

    # Performance Configuration
    batch_size: int = Field(default=100, description="Batch size for bulk operations")
    max_retries: int = Field(default=3, description="Maximum retries for API calls")
    timeout: int = Field(default=30, description="Timeout for API calls in seconds")

    # Evaluation Configuration
    auto_eval_enabled: bool = Field(default=False, description="Enable automatic evaluation")
    eval_frequency: int = Field(default=100, description="Run evaluation every N conversations")

    # Monitoring Configuration
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    alert_thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "error_rate": 0.05,  # Alert if error rate > 5%
            "latency_p95": 5000,  # Alert if P95 latency > 5s
            "success_rate": 0.95,  # Alert if success rate < 95%
        }
    )

    class Config:
        env_prefix = "LANGSMITH_"
        case_sensitive = False


class LangSmithTracer:
    """
    Comprehensive LangSmith tracer for the ConversaShop system.
    Handles initialization, tracing, and monitoring.
    """

    def __init__(self, config: Optional[LangSmithConfig] = None):
        """Initialize the LangSmith tracer with configuration."""
        self.config = config or self._load_config()
        self.client = None
        self._initialize_client()

    def _load_config(self) -> LangSmithConfig:
        """Load configuration from environment variables and settings."""
        try:
            from app.config.settings import get_settings
            settings = get_settings()
            
            # Use settings if available, fallback to environment variables
            return LangSmithConfig(
                api_key=settings.LANGSMITH_API_KEY or os.getenv("LANGSMITH_API_KEY"),
                api_url=settings.LANGSMITH_ENDPOINT or os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"),
                project_name=settings.LANGSMITH_PROJECT or os.getenv("LANGSMITH_PROJECT", "conversashop-production"),
                tracing_enabled=settings.LANGSMITH_TRACING if hasattr(settings, 'LANGSMITH_TRACING') else os.getenv("LANGSMITH_TRACING", "true").lower() == "true",
                verbose_tracing=settings.LANGSMITH_VERBOSE if hasattr(settings, 'LANGSMITH_VERBOSE') else os.getenv("LANGSMITH_VERBOSE", "false").lower() == "true",
                trace_sample_rate=float(os.getenv("LANGSMITH_SAMPLE_RATE", "1.0")),
                auto_eval_enabled=os.getenv("LANGSMITH_AUTO_EVAL", "false").lower() == "true",
                metrics_enabled=os.getenv("LANGSMITH_METRICS_ENABLED", "true").lower() == "true",
            )
        except ImportError:
            # Fallback to environment variables if settings not available
            return LangSmithConfig(
                api_key=os.getenv("LANGSMITH_API_KEY"),
                project_name=os.getenv("LANGSMITH_PROJECT", "conversashop-production"),
                tracing_enabled=os.getenv("LANGSMITH_TRACING", "true").lower() == "true",
                verbose_tracing=os.getenv("LANGSMITH_VERBOSE", "false").lower() == "true",
                trace_sample_rate=float(os.getenv("LANGSMITH_SAMPLE_RATE", "1.0")),
                auto_eval_enabled=os.getenv("LANGSMITH_AUTO_EVAL", "false").lower() == "true",
                metrics_enabled=os.getenv("LANGSMITH_METRICS_ENABLED", "true").lower() == "true",
            )

    def _initialize_client(self):
        """Initialize the LangSmith client."""
        if not self.config.api_key:
            logger.warning("LangSmith API key not found. Tracing disabled.")
            self.config.tracing_enabled = False
            return

        try:
            self.client = Client(
                api_key=self.config.api_key,
                api_url=self.config.api_url,
            )

            # Set environment variables for LangChain integration
            os.environ["LANGSMITH_API_KEY"] = self.config.api_key
            os.environ["LANGSMITH_PROJECT"] = self.config.project_name
            os.environ["LANGSMITH_TRACING_V2"] = "true" if self.config.tracing_enabled else "false"
            os.environ["LANGSMITH_VERBOSE"] = "true" if self.config.verbose_tracing else "false"

            logger.info(f"LangSmith client initialized for project: {self.config.project_name}")

        except Exception as e:
            logger.error(f"Failed to initialize LangSmith client: {e}")
            self.config.tracing_enabled = False

    @contextmanager
    def trace_chain(self, _: str, **metadata):
        """
        Context manager for tracing a chain execution.

        Args:
            name: Name of the chain being traced
            **metadata: Additional metadata to include in the trace
        """
        if not self.config.tracing_enabled:
            yield
            return

        tags = metadata.get("tags", [])
        with tracing_v2_enabled(project_name=self.config.project_name, tags=tags):
            yield

    @asynccontextmanager
    async def atrace_chain(self, _: str, **metadata):
        """
        Async context manager for tracing a chain execution.

        Args:
            name: Name of the chain being traced
            **metadata: Additional metadata to include in the trace
        """
        if not self.config.tracing_enabled:
            yield
            return

        tags = metadata.get("tags", [])
        with tracing_v2_enabled(project_name=self.config.project_name, tags=tags):
            yield

    def trace_agent(self, agent_name: str, agent_type: str = "chain"):
        """
        Decorator for tracing agent executions.

        Args:
            agent_name: Name of the agent
            agent_type: Type of agent (e.g., "product", "category", "supervisor")
        """

        def decorator(func):
            if not self.config.tracing_enabled:
                return func

            @wraps(func)
            @traceable(
                name=agent_name,
                run_type="chain",  # Use 'chain' for agents as it's the closest valid type
                project_name=self.config.project_name,
            )
            async def wrapper(*args, **kwargs):
                # Add agent metadata
                metadata = {
                    "agent_name": agent_name,
                    "agent_type": agent_type,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                # Extract state if available
                if len(args) > 1 and isinstance(args[1], dict):
                    state = args[1]
                    metadata["conversation_id"] = state.get("conversation_id")
                    metadata["user_id"] = state.get("user_id")

                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    logger.error(f"Error in {agent_name}: {e}")
                    raise

            return wrapper

        return decorator

    def trace_tool(self, tool_name: str):
        """
        Decorator for tracing tool executions.

        Args:
            tool_name: Name of the tool being traced
        """

        def decorator(func):
            if not self.config.tracing_enabled:
                return func

            @wraps(func)
            @traceable(
                name=tool_name,
                run_type="tool",
                project_name=self.config.project_name,
            )
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)

            return wrapper

        return decorator

    def log_feedback(self, run_id: str, score: float, comment: Optional[str] = None, feedback_type: str = "user"):
        """
        Log feedback for a specific run.

        Args:
            run_id: ID of the run to provide feedback for
            score: Feedback score (0.0 to 1.0)
            comment: Optional comment
            feedback_type: Type of feedback (user, model, human)
        """
        if not self.client:
            return

        try:
            self.client.create_feedback(
                run_id=run_id,
                key=feedback_type,
                score=score,
                comment=comment,
            )
        except Exception as e:
            logger.error(f"Failed to log feedback: {e}")

    def create_dataset(self, dataset_name: str, description: str = ""):
        """
        Create a new dataset for evaluation.

        Args:
            dataset_name: Name of the dataset
            description: Description of the dataset
        """
        if not self.client:
            return None

        try:
            dataset = self.client.create_dataset(
                dataset_name=dataset_name,
                description=description,
            )
            logger.info(f"Created dataset: {dataset_name}")
            return dataset
        except Exception as e:
            logger.error(f"Failed to create dataset: {e}")
            return None

    def add_example_to_dataset(
        self,
        dataset_name: str,
        inputs: Dict[str, Any],
        outputs: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Add an example to a dataset.

        Args:
            dataset_name: Name of the dataset
            inputs: Input data for the example
            outputs: Expected output data
            metadata: Additional metadata
        """
        if not self.client:
            return

        try:
            example = Example(
                inputs=inputs,
                outputs=outputs,
                metadata=metadata,
            )

            self.client.create_example(
                dataset_name=dataset_name,
                example=example,
            )
        except Exception as e:
            logger.error(f"Failed to add example to dataset: {e}")

    def get_metrics(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metrics for a specific run or project.

        Args:
            run_id: Optional run ID to get metrics for

        Returns:
            Dictionary containing metrics
        """
        if not self.client:
            return {}

        try:
            if run_id:
                run = self.client.read_run(run_id)
                return {
                    "latency": run.latency,
                    "tokens": run.token_count,
                    "cost": run.total_cost,
                    "error": run.error,
                    "feedback": run.feedback_stats,
                }
            else:
                # Get project-level metrics
                runs = list(
                    self.client.list_runs(
                        project_name=self.config.project_name,
                        limit=1000,
                    )
                )

                total_runs = len(runs)
                successful_runs = sum(1 for r in runs if not r.error)
                total_latency = sum(r.latency or 0 for r in runs)

                return {
                    "total_runs": total_runs,
                    "success_rate": successful_runs / total_runs if total_runs > 0 else 0,
                    "avg_latency": total_latency / total_runs if total_runs > 0 else 0,
                    "error_rate": 1 - (successful_runs / total_runs) if total_runs > 0 else 0,
                }
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return {}


# Global tracer instance
_tracer: Optional[LangSmithTracer] = None


def get_tracer() -> LangSmithTracer:
    """Get or create the global LangSmith tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = LangSmithTracer()
    return _tracer


def trace_langgraph_node(node_name: str):
    """
    Decorator specifically for LangGraph nodes.

    Args:
        node_name: Name of the LangGraph node
    """
    return get_tracer().trace_agent(node_name, agent_type="langgraph_node")


def trace_integration(integration_name: str):
    """
    Decorator for tracing integration calls (Ollama, ChromaDB, PostgreSQL).

    Args:
        integration_name: Name of the integration
    """

    def decorator(func):
        tracer = get_tracer()
        if not tracer.config.tracing_enabled:
            return func

        @wraps(func)
        @traceable(
            name=integration_name,
            run_type="tool",  # Use 'tool' instead of 'integration' for LangSmith compatibility
            project_name=tracer.config.project_name,
            tags=["integration", integration_name],  # Add tags to identify as integration
        )
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        return wrapper

    return decorator


class ConversationTracer:
    """
    Specialized tracer for conversation flows in ConversaShop.
    Tracks entire conversation lifecycle.
    """

    def __init__(self, conversation_id: str, user_id: Optional[str] = None):
        """
        Initialize conversation tracer.

        Args:
            conversation_id: Unique conversation identifier
            user_id: Optional user identifier
        """
        self.conversation_id = conversation_id
        self.user_id = user_id
        self.tracer = get_tracer()
        self.start_time = datetime.now(timezone.utc)
        self.messages = []
        self.agent_sequence = []

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """Add a message to the conversation trace."""
        self.messages.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": metadata or {},
            }
        )

    def add_agent_transition(self, from_agent: str, to_agent: str, reason: str):
        """Track agent transitions in the conversation."""
        self.agent_sequence.append(
            {"from": from_agent, "to": to_agent, "reason": reason, "timestamp": datetime.now(timezone.utc).isoformat()}
        )

    def end_conversation(self, outcome: str = "success"):
        """
        End the conversation and log final metrics.

        Args:
            outcome: Outcome of the conversation (success, failure, abandoned)
        """
        duration = (datetime.now(timezone.utc) - self.start_time).total_seconds()

        metadata = {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "duration_seconds": duration,
            "message_count": len(self.messages),
            "agent_count": len(set(a["to"] for a in self.agent_sequence)),
            "outcome": outcome,
            "agent_sequence": self.agent_sequence,
        }

        logger.info(f"Conversation {self.conversation_id} ended: {outcome}, metadata: {metadata}")

        # Log to LangSmith if enabled
        if self.tracer.config.metrics_enabled:
            # This would be logged as a custom metric in LangSmith
            pass

