"""
Tracing utilities for LangGraph agents and tools.
Provides decorators and context managers for comprehensive observability.
"""

import json
import logging
import time
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

from langchain_core.tracers.context import tracing_v2_enabled
from langsmith import traceable

from app.config.langsmith_config import get_tracer

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TracingMetrics:
    """Container for tracing metrics."""

    def __init__(self):
        self.start_time = time.time()
        self.end_time = None
        self.duration_ms = None
        self.token_count = 0
        self.error_count = 0
        self.success = True
        self.metadata = {}

    def end(self):
        """Mark the end of the traced operation."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "duration_ms": self.duration_ms,
            "token_count": self.token_count,
            "error_count": self.error_count,
            "success": self.success,
            "metadata": self.metadata,
        }


def trace_async_method(
    name: Optional[str] = None,
    run_type: str = "chain",
    metadata: Optional[Dict[str, Any]] = None,
    extract_state: bool = True,
    _: bool = False,
):
    """
    Comprehensive async method tracer with metrics collection.

    Args:
        name: Name for the trace (defaults to method name)
        run_type: Type of run (chain, agent, tool, etc.)
        metadata: Additional metadata to include
        extract_state: Whether to extract state information from arguments
        measure_tokens: Whether to measure token usage
    """

    def decorator(func: Callable) -> Callable:
        tracer = get_tracer()

        if not tracer.config.tracing_enabled:
            return func

        trace_name = name or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            metrics = TracingMetrics()
            trace_metadata = metadata or {}

            # Extract state information if available
            if extract_state and len(args) > 1:
                if hasattr(args[0], "__class__"):
                    trace_metadata["class"] = args[0].__class__.__name__

                # Look for state dict in arguments
                for arg in args[1:]:
                    if isinstance(arg, dict):
                        state_info = arg
                        trace_metadata.update(
                            {
                                "conversation_id": state_info.get("conversation_id"),
                                "user_id": state_info.get("user_id"),
                                "current_agent": state_info.get("current_agent"),
                                "message_count": len(state_info.get("messages", [])),
                            }
                        )
                        break

            # Add custom metadata
            trace_metadata.update(
                {
                    "run_type": run_type,
                    "function": func.__name__,
                    "module": func.__module__,
                }
            )

            @traceable(
                name=trace_name,
                run_type=run_type,
                metadata=trace_metadata,
                project_name=tracer.config.project_name,
            )
            async def traced_func(*args, **kwargs):
                try:
                    result = await func(*args, **kwargs)
                    metrics.success = True
                    return result
                except Exception as e:
                    metrics.success = False
                    metrics.error_count += 1
                    logger.error(f"Error in {trace_name}: {e}")
                    raise
                finally:
                    metrics.end()

                    # Log metrics
                    logger.debug(f"Trace {trace_name} completed: {metrics.to_dict()}")

            return await traced_func(*args, **kwargs)

        return wrapper

    return decorator


def trace_sync_method(name: Optional[str] = None, run_type: str = "chain", metadata: Optional[Dict[str, Any]] = None):
    """
    Synchronous method tracer.

    Args:
        name: Name for the trace
        run_type: Type of run
        metadata: Additional metadata
    """

    def decorator(func: Callable) -> Callable:
        tracer = get_tracer()

        if not tracer.config.tracing_enabled:
            return func

        trace_name = name or func.__name__

        @wraps(func)
        @traceable(
            name=trace_name,
            run_type=run_type,
            metadata=metadata,
            project_name=tracer.config.project_name,
        )
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


@asynccontextmanager
async def trace_context(name: str, metadata: Optional[Dict[str, Any]] = None, tags: Optional[list] = None):
    """
    Async context manager for tracing a block of code.

    Args:
        name: Name of the traced context
        metadata: Metadata to include
        tags: Tags to apply to the trace
    """
    tracer = get_tracer()

    if not tracer.config.tracing_enabled:
        yield
        return

    # Use the correct API for tracing_v2_enabled (without metadata parameter)
    with tracing_v2_enabled(project_name=tracer.config.project_name, tags=tags or []):
        start_time = time.time()
        try:
            # Store metadata in logger if provided
            if metadata:
                logger.debug(f"Trace context {name} started with metadata: {metadata}")
            yield
        finally:
            duration = (time.time() - start_time) * 1000
            logger.debug(f"Trace context {name} completed in {duration:.2f}ms")


class AgentTracer:
    """
    Specialized tracer for LangGraph agents.
    Tracks agent-specific metrics and behaviors.
    """

    def __init__(self, agent_name: str, agent_type: str):
        """
        Initialize agent tracer.

        Args:
            agent_name: Name of the agent
            agent_type: Type of agent
        """
        self.agent_name = agent_name
        self.agent_type = agent_type
        self.tracer = get_tracer()
        self.metrics = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "total_duration_ms": 0,
            "avg_duration_ms": 0,
        }

    def trace_process(self):
        """Decorator for tracing agent process methods."""

        def decorator(func):
            if not self.tracer.config.tracing_enabled:
                return func

            @wraps(func)
            @traceable(
                name=f"{self.agent_name}_process",
                run_type="chain",
                metadata={
                    "agent_name": self.agent_name,
                    "agent_type": self.agent_type,
                },
                project_name=self.tracer.config.project_name,
            )
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                self.metrics["total_calls"] += 1

                try:
                    # Extract message and state
                    message = args[1] if len(args) > 1 else ""
                    
                    # Safely format message for logging
                    if isinstance(message, str):
                        message_preview = message[:100]
                    else:
                        message_preview = str(message)[:100]

                    # Log agent invocation
                    logger.info(f"Agent {self.agent_name} processing message: {message_preview}...")

                    result = await func(*args, **kwargs)

                    self.metrics["successful_calls"] += 1

                    # Log successful completion
                    logger.info(f"Agent {self.agent_name} completed successfully")

                    return result

                except Exception as e:
                    self.metrics["failed_calls"] += 1
                    logger.error(f"Agent {self.agent_name} failed: {e}")
                    raise

                finally:
                    duration_ms = (time.time() - start_time) * 1000
                    self.metrics["total_duration_ms"] += duration_ms
                    self.metrics["avg_duration_ms"] = self.metrics["total_duration_ms"] / self.metrics["total_calls"]

                    # Log metrics
                    logger.debug(f"Agent {self.agent_name} metrics: {self.metrics}")

            return wrapper

        return decorator

    def get_metrics(self) -> Dict[str, Any]:
        """Get current agent metrics."""
        return self.metrics.copy()


class ToolTracer:
    """
    Specialized tracer for tools used by agents.
    """

    def __init__(self, tool_name: str):
        """
        Initialize tool tracer.

        Args:
            tool_name: Name of the tool
        """
        self.tool_name = tool_name
        self.tracer = get_tracer()
        self.call_count = 0
        self.error_count = 0

    def trace_call(self):
        """Decorator for tracing tool calls."""

        def decorator(func):
            if not self.tracer.config.tracing_enabled:
                return func

            @wraps(func)
            @traceable(
                name=f"tool_{self.tool_name}",
                run_type="tool",
                metadata={"tool_name": self.tool_name},
                project_name=self.tracer.config.project_name,
            )
            async def wrapper(*args, **kwargs):
                self.call_count += 1

                try:
                    result = await func(*args, **kwargs)
                    logger.debug(f"Tool {self.tool_name} executed successfully")
                    return result
                except Exception as e:
                    self.error_count += 1
                    logger.error(f"Tool {self.tool_name} failed: {e}")
                    raise

            return wrapper

        return decorator


class IntegrationTracer:
    """
    Tracer for external integrations (Ollama, ChromaDB, PostgreSQL).
    """

    def __init__(self, integration_name: str):
        """
        Initialize integration tracer.

        Args:
            integration_name: Name of the integration
        """
        self.integration_name = integration_name
        self.tracer = get_tracer()

    def trace_call(self, operation: str):
        """
        Decorator for tracing integration calls.

        Args:
            operation: Name of the operation being performed
        """

        def decorator(func):
            if not self.tracer.config.tracing_enabled:
                return func

            @wraps(func)
            @traceable(
                name=f"{self.integration_name}_{operation}",
                run_type="tool",
                metadata={
                    "integration": self.integration_name,
                    "operation": operation,
                },
                project_name=self.tracer.config.project_name,
            )
            async def wrapper(*args, **kwargs):
                start_time = time.time()

                try:
                    result = await func(*args, **kwargs)
                    duration_ms = (time.time() - start_time) * 1000

                    logger.debug(f"Integration {self.integration_name}.{operation} completed in {duration_ms:.2f}ms")

                    return result
                except Exception as e:
                    logger.error(f"Integration {self.integration_name}.{operation} failed: {e}")
                    raise

            return wrapper

        return decorator


def trace_langgraph_edge(from_node: str, to_node: str):
    """
    Trace a LangGraph edge transition.

    Args:
        from_node: Source node
        to_node: Destination node
    """
    tracer = get_tracer()

    if not tracer.config.tracing_enabled:
        return lambda func: func

    def decorator(func):
        @wraps(func)
        @traceable(
            name=f"edge_{from_node}_to_{to_node}",
            run_type="chain",
            metadata={
                "from_node": from_node,
                "to_node": to_node,
            },
            project_name=tracer.config.project_name,
        )
        def wrapper(*args, **kwargs):
            logger.debug(f"Edge transition: {from_node} -> {to_node}")
            return func(*args, **kwargs)

        return wrapper

    return decorator


def log_agent_response(agent_name: str, message: str, response: str, metadata: Optional[Dict[str, Any]] = None):
    """
    Log an agent's response for analysis.

    Args:
        agent_name: Name of the agent
        message: Input message
        response: Agent's response
        metadata: Additional metadata
    """
    tracer = get_tracer()

    if not tracer.config.metrics_enabled:
        return

    log_data = {
        "agent": agent_name,
        "input": message[:500],  # Truncate long messages
        "output": response[:500],
        "timestamp": time.time(),
        **(metadata or {}),
    }

    logger.info(f"Agent response logged: {json.dumps(log_data)}")


# Export utility functions for easy access
__all__ = [
    "trace_async_method",
    "trace_sync_method",
    "trace_context",
    "AgentTracer",
    "ToolTracer",
    "IntegrationTracer",
    "trace_langgraph_edge",
    "log_agent_response",
    "TracingMetrics",
]
