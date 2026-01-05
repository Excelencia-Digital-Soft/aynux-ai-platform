"""
Credit Agent for Credit Domain

Clean architecture agent that delegates to use cases.
Follows SOLID principles and implements IAgent interface.
Uses RAG (Knowledge Base Search) for context-aware responses.
"""

import logging
from decimal import Decimal
from typing import Any, Optional

from app.config.settings import get_settings
from app.core.interfaces.agent import AgentType, IAgent
from app.core.interfaces.llm import ILLM
from app.core.interfaces.repository import IRepository
from app.domains.credit.application.use_cases import (
    GetCreditBalanceRequest,
    GetCreditBalanceUseCase,
    GetPaymentScheduleRequest,
    GetPaymentScheduleUseCase,
    ProcessPaymentRequest,
    ProcessPaymentUseCase,
)
from app.domains.excelencia.application.services.support_response import (
    KnowledgeBaseSearch,
    RagQueryLogger,
    SearchMetrics,
)
from app.prompts.manager import PromptManager
from app.prompts.registry import PromptRegistry

logger = logging.getLogger(__name__)
settings = get_settings()


class CreditAgent(IAgent):
    """
    Credit Agent following Clean Architecture.

    Single Responsibility: Coordinate credit-related requests
    Dependency Inversion: Depends on use cases and interfaces
    """

    def __init__(
        self,
        credit_account_repository: IRepository,
        payment_repository: IRepository,
        llm: ILLM,
        config: Optional[dict[str, Any]] = None,
    ):
        """
        Initialize agent with dependencies.

        Args:
            credit_account_repository: Repository for credit accounts
            payment_repository: Repository for payments
            llm: Language model for intent analysis
            config: Optional configuration
        """
        self._config = config or {}
        self._account_repo = credit_account_repository
        self._payment_repo = payment_repository
        self._llm = llm

        # Initialize prompt manager for centralized prompt handling
        self._prompt_manager = PromptManager()

        # Initialize use cases
        self._balance_use_case = GetCreditBalanceUseCase(credit_account_repository=credit_account_repository)
        self._payment_use_case = ProcessPaymentUseCase(
            credit_account_repository=credit_account_repository,
            payment_repository=payment_repository,
        )
        self._schedule_use_case = GetPaymentScheduleUseCase(credit_account_repository=credit_account_repository)

        # RAG integration for knowledge-based responses
        self._knowledge_search = KnowledgeBaseSearch(
            agent_key="credit_agent",
            max_results=3,
        )
        self._rag_logger = RagQueryLogger(agent_key="credit_agent")
        self._last_search_metrics: SearchMetrics | None = None
        self.use_rag = getattr(settings, "KNOWLEDGE_BASE_ENABLED", True)

        logger.info("CreditAgent initialized (RAG enabled: %s)", self.use_rag)

    @property
    def agent_type(self) -> AgentType:
        """Agent type identifier"""
        return AgentType.CREDIT

    @property
    def agent_name(self) -> str:
        """Agent name"""
        return "credit_agent"

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        Execute agent logic.

        Args:
            state: Current conversation state

        Returns:
            Updated state
        """
        try:
            # Extract message and account info
            messages = state.get("messages", [])
            if not messages:
                return self._error_response("No message provided", state)

            user_message = messages[-1].get("content", "")
            account_id = self._extract_account_id(state)

            if not account_id:
                return self._error_response("No credit account found", state)

            # Get RAG context for knowledge-based response
            rag_context = await self._get_rag_context(user_message)
            if rag_context:
                state["rag_context"] = rag_context

            # Analyze intent
            intent = await self._analyze_intent(user_message)
            logger.info(f"Detected credit intent: {intent}")

            # Route to appropriate use case
            if intent == "balance":
                response = await self._handle_balance(account_id, state)
            elif intent == "payment":
                response = await self._handle_payment(user_message, account_id, state)
            elif intent == "schedule":
                response = await self._handle_schedule(account_id, state)
            else:
                response = await self._handle_balance(account_id, state)  # Default

            # Log RAG query with response (fire-and-forget)
            if self._last_search_metrics and self._last_search_metrics.result_count > 0:
                # Extract response text from handler result
                messages = response.get("messages", [])
                if messages:
                    response_text = messages[-1].get("content", "")
                    if response_text:
                        self._rag_logger.log_async(
                            query=user_message,
                            metrics=self._last_search_metrics,
                            response=response_text,
                        )

            return response

        except Exception as e:
            logger.error(f"Error in CreditAgent.execute: {e}", exc_info=True)
            return self._error_response(str(e), state)

    async def _get_rag_context(self, message: str) -> str:
        """
        Get RAG context from knowledge base.

        Args:
            message: User message

        Returns:
            Formatted context string or empty string
        """
        self._last_search_metrics = None

        if not self.use_rag:
            return ""

        try:
            search_result = await self._knowledge_search.search(message, "credit")
            self._last_search_metrics = search_result.metrics
            if search_result.context:
                logger.info(f"RAG context found for credit query: {len(search_result.context)} chars")
            return search_result.context
        except Exception as e:
            logger.warning(f"RAG search failed: {e}")
            return ""

    async def validate_input(self, state: dict[str, Any]) -> bool:
        """
        Validate input state.

        Args:
            state: State to validate

        Returns:
            True if valid, False otherwise
        """
        messages = state.get("messages", [])
        if not messages:
            return False

        last_message = messages[-1]
        if not last_message.get("content"):
            return False

        return True

    async def _analyze_intent(self, message: str) -> str:
        """
        Analyze user intent using LLM with centralized prompt management.

        Args:
            message: User message

        Returns:
            Intent string ('balance', 'payment', 'schedule')
        """
        try:
            # Load prompt from YAML
            prompt = await self._prompt_manager.get_prompt(
                PromptRegistry.CREDIT_INTENT_ANALYSIS, variables={"message": message}
            )

            # Get metadata for LLM configuration
            template = await self._prompt_manager.get_template(PromptRegistry.CREDIT_INTENT_ANALYSIS)
            temperature = template.metadata.get("temperature", 0.2) if template and template.metadata else 0.2
            max_tokens = template.metadata.get("max_tokens", 10) if template and template.metadata else 10

            response = await self._llm.generate(prompt, temperature=temperature, max_tokens=max_tokens)
            intent = response.strip().lower()

            if intent in ["balance", "payment", "schedule"]:
                return intent

            return "balance"  # Default

        except Exception as e:
            logger.warning(f"Error analyzing intent: {e}")
            return "balance"

    async def _handle_balance(self, account_id: str, state: dict[str, Any]) -> dict[str, Any]:
        """Handle balance inquiry"""
        try:
            request = GetCreditBalanceRequest(account_id=account_id)
            response = await self._balance_use_case.execute(request)

            if not response.success:
                return self._error_response(response.error or "Failed to get balance", state)

            # Generate AI response
            ai_response = await self._generate_balance_response(response)

            return {
                "messages": [{"role": "assistant", "content": ai_response}],
                "current_agent": self.agent_name,
                "agent_history": state.get("agent_history", []) + [self.agent_name],
                "retrieved_data": {
                    "credit_limit": float(response.credit_limit),
                    "used_credit": float(response.used_credit),
                    "available_credit": float(response.available_credit),
                    "status": response.status,
                },
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in balance handler: {e}", exc_info=True)
            return self._error_response(str(e), state)

    async def _handle_payment(self, message: str, account_id: str, state: dict[str, Any]) -> dict[str, Any]:
        """Handle payment processing"""
        try:
            # Extract payment amount (simplified - should use NLP)
            amount = await self._extract_amount(message)

            if not amount or amount <= 0:
                return self._error_response("Invalid payment amount", state)

            request = ProcessPaymentRequest(
                account_id=account_id,
                amount=amount,
                payment_type="regular",
            )

            response = await self._payment_use_case.execute(request)

            if not response.success:
                return self._error_response(response.error or "Payment failed", state)

            # Generate AI response
            ai_response = await self._generate_payment_response(response)

            return {
                "messages": [{"role": "assistant", "content": ai_response}],
                "current_agent": self.agent_name,
                "agent_history": state.get("agent_history", []) + [self.agent_name],
                "retrieved_data": {
                    "payment_id": response.payment_id,
                    "amount": float(response.amount),
                    "remaining_balance": float(response.remaining_balance),
                },
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in payment handler: {e}", exc_info=True)
            return self._error_response(str(e), state)

    async def _handle_schedule(self, account_id: str, state: dict[str, Any]) -> dict[str, Any]:
        """Handle payment schedule request"""
        try:
            request = GetPaymentScheduleRequest(account_id=account_id, months_ahead=6)
            response = await self._schedule_use_case.execute(request)

            if not response.success:
                return self._error_response(response.error or "Failed to get schedule", state)

            # Generate AI response
            ai_response = await self._generate_schedule_response(response)

            return {
                "messages": [{"role": "assistant", "content": ai_response}],
                "current_agent": self.agent_name,
                "agent_history": state.get("agent_history", []) + [self.agent_name],
                "retrieved_data": {
                    "schedule": [
                        {
                            "payment_number": item.payment_number,
                            "due_date": item.due_date.isoformat(),
                            "amount": float(item.amount),
                            "status": item.status,
                        }
                        for item in response.schedule
                    ],
                },
                "is_complete": True,
            }

        except Exception as e:
            logger.error(f"Error in schedule handler: {e}", exc_info=True)
            return self._error_response(str(e), state)

    async def _generate_balance_response(self, balance) -> str:
        """Generate AI response for balance inquiry using centralized prompts"""
        try:
            # Load prompt from YAML
            prompt = await self._prompt_manager.get_prompt(
                PromptRegistry.CREDIT_BALANCE_RESPONSE,
                variables={
                    "credit_limit": f"{balance.credit_limit:,.2f}",
                    "used_credit": f"{balance.used_credit:,.2f}",
                    "available_credit": f"{balance.available_credit:,.2f}",
                    "next_payment_amount": f"{balance.next_payment_amount:,.2f}",
                    "next_payment_date": str(balance.next_payment_date),
                    "status": balance.status,
                },
            )

            # Get metadata for LLM configuration
            template = await self._prompt_manager.get_template(PromptRegistry.CREDIT_BALANCE_RESPONSE)
            temperature = template.metadata.get("temperature", 0.7) if template and template.metadata else 0.7
            max_tokens = template.metadata.get("max_tokens", 200) if template and template.metadata else 200

            response = await self._llm.generate(prompt, temperature=temperature, max_tokens=max_tokens)
            return response.strip()

        except Exception as e:
            logger.error(f"Error generating balance response: {e}")
            return f"Tu saldo disponible es ${balance.available_credit:,.2f}"

    async def _generate_payment_response(self, payment) -> str:
        """Generate AI response for payment confirmation using centralized prompts"""
        try:
            # Load prompt from YAML
            prompt = await self._prompt_manager.get_prompt(
                PromptRegistry.CREDIT_PAYMENT_CONFIRMATION,
                variables={
                    "amount": f"{payment.amount:,.2f}",
                    "remaining_balance": f"{payment.remaining_balance:,.2f}",
                    "available_credit": f"{payment.available_credit:,.2f}",
                    "payment_id": payment.payment_id,
                },
            )

            # Get metadata for LLM configuration
            template = await self._prompt_manager.get_template(PromptRegistry.CREDIT_PAYMENT_CONFIRMATION)
            temperature = template.metadata.get("temperature", 0.7) if template and template.metadata else 0.7
            max_tokens = template.metadata.get("max_tokens", 150) if template and template.metadata else 150

            response = await self._llm.generate(prompt, temperature=temperature, max_tokens=max_tokens)
            return response.strip()

        except Exception as e:
            logger.error(f"Error generating payment response: {e}")
            return f"¡Pago procesado! Monto: ${payment.amount:,.2f}"

    async def _generate_schedule_response(self, schedule) -> str:
        """Generate AI response for payment schedule using centralized prompts"""
        try:
            schedule_text = "\n".join(
                [f"{item.payment_number}. {item.due_date} - ${item.amount:,.2f}" for item in schedule.schedule[:3]]
            )

            # Load prompt from YAML
            prompt = await self._prompt_manager.get_prompt(
                PromptRegistry.CREDIT_SCHEDULE_RESPONSE,
                variables={
                    "total_payments": str(len(schedule.schedule)),
                    "schedule_text": schedule_text,
                },
            )

            # Get metadata for LLM configuration
            template = await self._prompt_manager.get_template(PromptRegistry.CREDIT_SCHEDULE_RESPONSE)
            temperature = template.metadata.get("temperature", 0.7) if template and template.metadata else 0.7
            max_tokens = template.metadata.get("max_tokens", 150) if template and template.metadata else 150

            response = await self._llm.generate(prompt, temperature=temperature, max_tokens=max_tokens)
            return response.strip()

        except Exception as e:
            logger.error(f"Error generating schedule response: {e}")
            return f"Tienes {schedule.total_payments} pagos programados"

    async def _extract_amount(self, message: str) -> Decimal:
        """Extract payment amount from message (simplified)"""
        # TODO: Use NLP for better extraction
        # For now, return default amount
        return Decimal("2500.00")

    def _extract_account_id(self, state: dict[str, Any]) -> Optional[str]:
        """Extract credit account ID from state"""
        return state.get("credit_account_id") or state.get("user_id")

    def _error_response(self, error: str, state: dict[str, Any]) -> dict[str, Any]:
        """Generate error response"""
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": "Disculpa, tuve un problema. ¿Podrías reformular tu pregunta?",
                }
            ],
            "current_agent": self.agent_name,
            "error_count": state.get("error_count", 0) + 1,
            "error": error,
        }
