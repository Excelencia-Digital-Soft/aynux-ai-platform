# ============================================================================
# SCOPE: GLOBAL
# Description: Helper functions for Chat Admin API - execution visualization.
# ============================================================================
"""
Chat Admin Helpers - Execution step and graph builders for visualization.

Provides factory functions for creating ExecutionStepModel and ChatGraphResponse
objects used by the Chat Visualizer interface.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.chat import (
    ChatGraphEdge,
    ChatGraphNode,
    ChatGraphResponse,
    ExecutionStepModel,
)


def create_execution_step(
    step_number: int,
    node_type: str,
    name: str,
    description: str,
    *,
    input_data: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
    duration_ms: int = 0,
    status: str = "completed",
    error_message: str | None = None,
) -> ExecutionStepModel:
    """
    Create an ExecutionStepModel with proper defaults.

    Args:
        step_number: Step sequence number
        node_type: Type (start, tool_call, llm_call, decision, end, error, orchestrator, agent, supervisor)
        name: Step name or agent name
        description: Step description
        input_data: Optional step input data
        output_data: Optional step output data
        duration_ms: Execution duration in milliseconds
        status: Status (pending, running, completed, error)
        error_message: Error message if status is error

    Returns:
        ExecutionStepModel instance
    """
    return ExecutionStepModel(
        id=str(uuid.uuid4()),
        step_number=step_number,
        node_type=node_type,
        name=name,
        description=description,
        input=input_data,
        output=output_data,
        duration_ms=duration_ms,
        status=status,
        error_message=error_message,
        timestamp=datetime.now(UTC).isoformat(),
    )


def build_debug_execution_steps(
    message: str,
    response: str,
    agent_history: list[str],
    routing_decision: dict[str, Any],
    response_time_ms: float,
) -> list[ExecutionStepModel]:
    """
    Build execution steps for /test endpoint debug mode.

    Args:
        message: Original user message
        response: Agent response text
        agent_history: List of agent names that processed the message
        routing_decision: Orchestrator routing decision details
        response_time_ms: Total response time in milliseconds

    Returns:
        List of ExecutionStepModel for visualization
    """
    steps: list[ExecutionStepModel] = []
    step_number = 1

    # Step 1: Message received
    steps.append(
        create_execution_step(
            step_number=step_number,
            node_type="start",
            name="message_received",
            description="User message received",
            input_data={"message": message},
            duration_ms=10,
        )
    )
    step_number += 1

    # Steps 2+: Each agent in history
    per_agent_duration = int(response_time_ms / max(len(agent_history), 1))
    for agent_name in agent_history:
        if agent_name == "orchestrator":
            node_type = "orchestrator"
        elif agent_name == "supervisor":
            node_type = "supervisor"
        else:
            node_type = "agent"

        steps.append(
            create_execution_step(
                step_number=step_number,
                node_type=node_type,
                name=agent_name,
                description=f"Executed by {agent_name}",
                input_data=routing_decision if agent_name == "orchestrator" else None,
                duration_ms=per_agent_duration,
            )
        )
        step_number += 1

    # Final step: Response sent
    steps.append(
        create_execution_step(
            step_number=step_number,
            node_type="end",
            name="response_sent",
            description="Response generated",
            output_data={"response_preview": response[:100]},
            duration_ms=5,
        )
    )

    return steps


def build_webhook_execution_steps(
    message: str,
    response: str,
    phone_number: str,
    user_name: str,
    business_domain: str,
    agent_history: list[str],
    response_time_ms: float,
) -> list[ExecutionStepModel]:
    """
    Build execution steps for /test-webhook endpoint debug mode.

    Args:
        message: Original user message
        response: Agent response text
        phone_number: Simulated phone number
        user_name: Simulated user name
        business_domain: Business domain for routing
        agent_history: List of all agents that processed the message
        response_time_ms: Total response time in milliseconds

    Returns:
        List of ExecutionStepModel for visualization
    """
    steps: list[ExecutionStepModel] = []
    step_number = 1

    # Step 1: Webhook received
    steps.append(
        create_execution_step(
            step_number=step_number,
            node_type="start",
            name="webhook_received",
            description=f"Webhook simulation from {phone_number}",
            input_data={
                "message": message,
                "phone_number": phone_number,
                "user_name": user_name,
                "business_domain": business_domain,
                "channel": "WEB_SIMULATOR",
            },
            duration_ms=10,
        )
    )
    step_number += 1

    # Step 2: Domain routing
    steps.append(
        create_execution_step(
            step_number=step_number,
            node_type="orchestrator",
            name="domain_routing",
            description=f"Routed to {business_domain} domain",
            input_data={"business_domain": business_domain},
            duration_ms=int(response_time_ms * 0.1),
        )
    )
    step_number += 1

    # Steps 3+: Each agent in history (complete execution path)
    # Filter out orchestrator (already shown as domain_routing)
    agents_to_show = [a for a in agent_history if a != "orchestrator"]
    per_agent_duration = int(response_time_ms * 0.8 / max(len(agents_to_show), 1))

    for agent_name in agents_to_show:
        if agent_name == "supervisor":
            node_type = "supervisor"
        else:
            node_type = "agent"

        steps.append(
            create_execution_step(
                step_number=step_number,
                node_type=node_type,
                name=agent_name,
                description=f"Processed by {agent_name}",
                duration_ms=per_agent_duration,
            )
        )
        step_number += 1

    # Final step: Response sent
    steps.append(
        create_execution_step(
            step_number=step_number,
            node_type="end",
            name="response_sent",
            description="Response generated via webhook flow",
            output_data={"response_preview": response[:100] if response else ""},
            duration_ms=5,
        )
    )

    return steps


def get_mock_execution_steps() -> list[ExecutionStepModel]:
    """
    Get mock execution steps for /execution/{message_id}/steps endpoint.

    Returns:
        List of mock ExecutionStepModel for visualization
    """
    return [
        create_execution_step(
            step_number=1,
            node_type="start",
            name="orchestrator",
            description="SuperOrchestrator routing",
            duration_ms=50,
        ),
        create_execution_step(
            step_number=2,
            node_type="decision",
            name="intent_classification",
            description="Classifying user intent",
            duration_ms=100,
        ),
        create_execution_step(
            step_number=3,
            node_type="llm_call",
            name="agent_response",
            description="Generating response",
            duration_ms=500,
        ),
    ]


def get_default_graph() -> ChatGraphResponse:
    """
    Get the default SuperOrchestrator graph structure.

    Returns:
        ChatGraphResponse with nodes and edges for visualization
    """
    nodes = [
        ChatGraphNode(id="start", type="entry", label="Start", data=None),
        ChatGraphNode(id="orchestrator", type="router", label="SuperOrchestrator", data=None),
        ChatGraphNode(id="intent", type="decision", label="Intent Classification", data=None),
        ChatGraphNode(id="greeting_agent", type="agent", label="Greeting", data=None),
        ChatGraphNode(id="excelencia_agent", type="agent", label="Excelencia", data=None),
        ChatGraphNode(id="support_agent", type="agent", label="Support", data=None),
        ChatGraphNode(id="fallback_agent", type="agent", label="Fallback", data=None),
        ChatGraphNode(id="farewell_agent", type="agent", label="Farewell", data=None),
        ChatGraphNode(id="response", type="end", label="Response", data=None),
    ]

    edges = [
        ChatGraphEdge(id="e1", source="start", target="orchestrator"),
        ChatGraphEdge(id="e2", source="orchestrator", target="intent"),
        ChatGraphEdge(id="e3", source="intent", target="greeting_agent"),
        ChatGraphEdge(id="e4", source="intent", target="excelencia_agent"),
        ChatGraphEdge(id="e5", source="intent", target="support_agent"),
        ChatGraphEdge(id="e6", source="intent", target="fallback_agent"),
        ChatGraphEdge(id="e7", source="intent", target="farewell_agent"),
        ChatGraphEdge(id="e8", source="greeting_agent", target="response"),
        ChatGraphEdge(id="e9", source="excelencia_agent", target="response"),
        ChatGraphEdge(id="e10", source="support_agent", target="response"),
        ChatGraphEdge(id="e11", source="fallback_agent", target="response"),
        ChatGraphEdge(id="e12", source="farewell_agent", target="response"),
    ]

    return ChatGraphResponse(
        nodes=nodes,
        edges=edges,
        current_node="response",
        visited_nodes=["start", "orchestrator", "intent", "response"],
    )
