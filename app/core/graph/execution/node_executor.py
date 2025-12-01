"""
Executor for managing node operations and agent execution
"""

import logging
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage

from app.core.schemas import AgentType
from app.core.graph.state_schema import LangGraphState
from app.core.utils.tracing import trace_async_method

logger = logging.getLogger(__name__)


class NodeExecutor:
    """Handles node execution and state transformations"""

    def __init__(self, agents: Dict[str, Any], conversation_tracers: Dict[str, Any]):
        self.agents = agents
        self.conversation_tracers = conversation_tracers

    @trace_async_method(
        name="execute_orchestrator",
        run_type="chain",
        metadata={"node_type": "orchestrator", "role": "intent_routing"},
        extract_state=True,
    )
    async def execute_orchestrator(self, state: LangGraphState) -> Dict[str, Any]:
        """Execute orchestrator node for intent analysis and routing"""
        try:
            messages = state.get("messages", [])
            if not messages:
                return {"next_agent": "fallback_agent", "error": "No messages in state"}

            # Find last user message
            user_message = self._extract_user_message(messages) or ""
            if not user_message:
                user_message = messages[-1].content if messages else ""

            logger.info(f"Orchestrator processing: {user_message[:100] if user_message else 'Empty'}...")

            # Prepare state for orchestrator
            state_dict = self._prepare_state_dict(state, messages)

            # Process with orchestrator
            orchestrator = self.agents.get("orchestrator")
            if not orchestrator:
                logger.error("Orchestrator agent not found")
                return {"next_agent": "fallback_agent", "error": "Orchestrator not available"}

            result = await orchestrator._process_internal(message=user_message, state_dict=state_dict)

            # Update state with orchestrator decision
            return {
                "current_agent": "orchestrator",
                "next_agent": result.get("next_agent", "fallback_agent"),
                "routing_decision": result.get("routing_decision", {}),
                "orchestrator_analysis": result.get("orchestrator_analysis", {}),
                "routing_attempts": result.get("routing_attempts", 0),
            }

        except Exception as e:
            logger.error(f"Error in orchestrator node: {str(e)}")
            return {"next_agent": "fallback_agent", "error": str(e), "error_count": state.get("error_count", 0) + 1}

    @trace_async_method(
        name="execute_supervisor",
        run_type="chain",
        metadata={"node_type": "supervisor", "role": "response_evaluation"},
        extract_state=True,
    )
    async def execute_supervisor(self, state: LangGraphState) -> Dict[str, Any]:
        """Execute supervisor node for response evaluation"""
        try:
            messages = state.get("messages", [])
            if not messages:
                return {"is_complete": True, "error": "No messages in state"}

            # Find last user message
            user_message = self._extract_user_message(messages) or ""
            if not user_message:
                user_message = ""

            logger.info(f"Supervisor evaluating: {user_message[:100] if user_message else 'Empty'}...")

            # Prepare full state for supervisor
            state_dict = self._prepare_supervisor_state(state, messages)

            # Process with supervisor
            supervisor = self.agents.get("supervisor")
            if not supervisor:
                logger.error("Supervisor agent not found")
                return {"is_complete": True, "error": "Supervisor not available"}

            result = await supervisor._process_internal(message=user_message, state_dict=state_dict)

            # Prepare updates
            updates = {
                "current_agent": "supervisor",
                "supervisor_evaluation": result.get("supervisor_evaluation", {}),
                "conversation_flow": result.get("conversation_flow", {}),
                "supervisor_analysis": result.get("supervisor_analysis", {}),
                "is_complete": result.get("is_complete", False),
                "needs_re_routing": result.get("needs_re_routing", False),
                "human_handoff_requested": result.get("human_handoff_requested", False),
                "supervisor_retry_count": state.get("supervisor_retry_count", 0) + 1,
            }

            # Handle enhanced response if provided
            enhanced_response = result.get("enhanced_response")
            if enhanced_response and result.get("is_complete"):
                updates["messages"] = self._replace_last_assistant_message(messages, enhanced_response)
                logger.info("Supervisor enhanced the final response")

            # Handle re-routing
            if result.get("needs_re_routing"):
                updates["routing_attempts"] = state.get("routing_attempts", 0) + 1
                updates["next_agent"] = "orchestrator"

            # Handle human handoff
            if result.get("human_handoff_requested"):
                updates["is_complete"] = True
                updates["requires_human"] = True

            return updates

        except Exception as e:
            logger.error(f"Error in supervisor node: {str(e)}")
            return {"is_complete": True, "error": str(e), "error_count": state.get("error_count", 0) + 1}

    @trace_async_method(
        name="execute_agent",
        run_type="chain",
        metadata={"operation": "agent_execution"},
        extract_state=True,
    )
    async def execute_agent(self, state: LangGraphState, agent_name: str) -> Dict[str, Any]:
        """Execute a specialized agent"""
        try:
            # Track conversation transition if needed
            self._track_agent_transition(state, agent_name)

            messages = state.get("messages", [])
            if not messages:
                logger.error(f"No messages to process for {agent_name}")
                return {"error": "No messages to process", "current_agent": agent_name}

            # Find last user message
            user_message = self._extract_user_message(messages) or ""
            if not user_message:
                user_message = messages[-1].content if messages else ""

            logger.info(f"Executing {agent_name} for: {user_message[:100] if user_message else 'Empty'}...")

            # Prepare state for agent
            state_dict = self._prepare_state_dict(state, messages)

            # Execute agent
            agent = self.agents.get(agent_name)
            if not agent:
                logger.error(f"Agent '{agent_name}' not found. Available agents: {list(self.agents.keys())}")
                raise ValueError(f"Agent '{agent_name}' not found")

            # Support both legacy agents with _process_internal and new agents with process
            # EcommerceAgent uses process() which calls its subgraph
            if hasattr(agent, "process"):
                result = await agent.process(message=user_message, state_dict=state_dict)
            elif hasattr(agent, "_process_internal"):
                result = await agent._process_internal(message=user_message, state_dict=state_dict)
            else:
                raise ValueError(f"Agent '{agent_name}' has no process or _process_internal method")

            # Prepare updates
            updates: Dict[str, Any] = {
                "current_agent": agent_name,
                "agent_history": state.get("agent_history", []) + [agent_name],
            }

            # Add response messages if present
            if "messages" in result:
                updates["messages"] = self._convert_messages(result["messages"])

            # Copy other fields
            for key in ["retrieved_data", "is_complete", "error_count"]:
                if key in result:
                    updates[key] = result[key]

            # Handle farewell agent special case
            if agent_name == AgentType.FAREWELL_AGENT.value:
                updates["is_complete"] = True

            return updates

        except Exception as e:
            logger.error(f"Error in {agent_name} node: {str(e)}")
            return {
                "error": str(e),
                "error_count": state.get("error_count", 0) + 1,
                "current_agent": agent_name,
                "messages": [
                    AIMessage(content="Disculpa, tuve un problema procesando tu solicitud. ¿Podrías intentar de nuevo?")
                ],
            }

    def _extract_user_message(self, messages: list) -> Optional[str]:
        """Extract last user message from message list"""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                if isinstance(msg.content, str):
                    return msg.content
                elif isinstance(msg.content, list):
                    return " ".join(
                        part.get("text", "") if isinstance(part, dict) else str(part) for part in msg.content
                    )
        return None

    def _prepare_state_dict(self, state: LangGraphState, messages: list) -> Dict[str, Any]:
        """Prepare state dictionary for agent processing"""
        messages_dict = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                messages_dict.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                messages_dict.append({"role": "assistant", "content": msg.content})

        return {
            "messages": messages_dict,
            "customer_data": state.get("customer_data", {}),
            "current_agent": state.get("current_agent"),
            "agent_history": state.get("agent_history", []),
            "error_count": state.get("error_count", 0),
            "routing_attempts": state.get("routing_attempts", 0),
        }

    def _prepare_supervisor_state(self, state: LangGraphState, messages: list) -> Dict[str, Any]:
        """Prepare full state for supervisor evaluation"""
        base_state = self._prepare_state_dict(state, messages)
        base_state.update(
            {
                "customer": state.get("customer"),
                "conversation": state.get("conversation"),
                "supervisor_retry_count": state.get("supervisor_retry_count", 0),
                "agent_responses": state.get("agent_responses", []),
                "retrieved_data": state.get("retrieved_data", {}),
            }
        )
        return base_state

    def _convert_messages(self, messages: list) -> list:
        """Convert message dictionaries to LangChain message objects"""
        new_messages = []
        for msg_dict in messages:
            if msg_dict.get("role") == "assistant":
                new_messages.append(AIMessage(content=msg_dict["content"]))
            elif msg_dict.get("role") == "user":
                new_messages.append(HumanMessage(content=msg_dict["content"]))
        return new_messages

    def _replace_last_assistant_message(self, messages: list, enhanced_response: str) -> list:
        """Replace last assistant message with enhanced version"""
        messages_copy = list(messages)
        for i in range(len(messages_copy) - 1, -1, -1):
            if isinstance(messages_copy[i], AIMessage):
                messages_copy[i] = AIMessage(content=enhanced_response)
                break
        return messages_copy

    def _track_agent_transition(self, state: LangGraphState, agent_name: str):
        """Track agent transitions in conversation tracker"""
        conv_id = state.get("conversation_id")
        current_agent = state.get("current_agent")
        conv_tracker = self.conversation_tracers.get(conv_id) if conv_id else None

        if conv_tracker and current_agent:
            conv_tracker.add_agent_transition(
                from_agent=current_agent, to_agent=agent_name, reason="Supervisor routing decision"
            )
