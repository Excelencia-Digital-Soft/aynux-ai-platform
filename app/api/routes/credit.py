"""
API Routes for Credit System
"""

import logging
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.credit.credit_graph import CreditSystemGraph
from app.agents.credit.schemas import UserRole
from app.api.dependencies import get_current_user
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/credit", tags=["credit"])

# Initialize credit graph
credit_graph = None


async def get_credit_graph():
    """Get or initialize credit graph"""
    global credit_graph
    if credit_graph is None:
        credit_graph = CreditSystemGraph()
        await credit_graph.initialize_checkpointer()
    return credit_graph


# Request/Response Models
class CreditChatRequest(BaseModel):
    """Credit chat request model"""

    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    credit_account_id: Optional[str] = Field(None, description="Credit account ID")


class CreditChatResponse(BaseModel):
    """Credit chat response model"""

    success: bool
    message: str
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    state: Optional[Dict[str, Any]] = None


class CreditBalanceRequest(BaseModel):
    """Credit balance request"""

    account_id: Optional[str] = None


class CreditApplicationRequest(BaseModel):
    """Credit application request"""

    requested_amount: float
    term_months: int
    purpose: str
    monthly_income: float
    employment_status: str


class PaymentRequest(BaseModel):
    """Payment request model"""

    account_id: str
    amount: float
    payment_method: str = "transfer"


class RiskAssessmentRequest(BaseModel):
    """Risk assessment request"""

    account_id: Optional[str] = None
    application_id: Optional[str] = None
    assessment_type: str = "periodic"


# Credit Chat Endpoint
@router.post("/chat", response_model=CreditChatResponse)
async def credit_chat(
    request: CreditChatRequest,
    current_user: Dict = Depends(get_current_user),  # noqa: B008
    graph: CreditSystemGraph = Depends(get_credit_graph),  # noqa: B008
):
    """
    Process credit-related chat messages
    """
    try:
        # Get user role (simplified - in production, get from user profile)
        user_role = current_user.get("role", UserRole.CUSTOMER.value)

        # Process message through credit graph
        result = await graph.process_message(
            message=request.message,
            user_id=current_user["id"],
            user_role=user_role,
            session_id=request.session_id,
            credit_account_id=request.credit_account_id,
        )

        return CreditChatResponse(
            success=result.get("success", False),
            message=result.get("message", ""),
            session_id=result.get("state", {}).get("session_id"),
            metadata=result.get("metadata"),
            state=result.get("state"),
        )

    except Exception as e:
        logger.error(f"Error in credit chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# Credit Balance Endpoint
@router.get("/balance")
async def get_credit_balance(
    account_id: Optional[str] = Query(None),
    current_user: Dict = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get credit balance for user
    """
    try:
        # TODO: Implement actual database query
        # For now, return mock data
        return {
            "success": True,
            "data": {
                "account_id": account_id or current_user["id"],
                "credit_limit": 50000.00,
                "used_credit": 15000.00,
                "available_credit": 35000.00,
                "next_payment_date": "2024-02-15",
                "next_payment_amount": 2500.00,
                "status": "active",
            },
        }

    except Exception as e:
        logger.error(f"Error getting balance: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# Credit Application Endpoint
@router.post("/apply")
async def apply_for_credit(
    application: CreditApplicationRequest,
    current_user: Dict = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Submit a credit application
    """
    try:
        # TODO: Implement actual application processing
        # For now, return mock response
        return {
            "success": True,
            "data": {
                "application_id": "APP-123456",
                "status": "under_review",
                "requested_amount": application.requested_amount,
                "message": "Tu solicitud ha sido recibida y está siendo evaluada.",
            },
        }

    except Exception as e:
        logger.error(f"Error processing application: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# Payment Endpoint
@router.post("/payment")
async def make_payment(
    payment: PaymentRequest,
    current_user: Dict = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Process a credit payment
    """
    try:
        # TODO: Implement actual payment processing
        # For now, return mock response
        return {
            "success": True,
            "data": {
                "payment_id": "PAY-789012",
                "amount": payment.amount,
                "status": "success",
                "transaction_date": datetime.now(UTC).isoformat(),
                "receipt_url": "/receipts/PAY-789012",
            },
        }

    except Exception as e:
        logger.error(f"Error processing payment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# Statement Endpoint
@router.get("/statement")
async def get_statement(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    current_user: Dict = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get credit account statement
    """
    try:
        # Default to current month if not specified
        if not month or not year:
            now = datetime.now()
            month = month or now.month
            year = year or now.year

        # TODO: Implement actual statement generation
        return {
            "success": True,
            "data": {
                "period": f"{month}/{year}",
                "opening_balance": 12000.00,
                "closing_balance": 15000.00,
                "total_charges": 5000.00,
                "total_payments": 2000.00,
                "interest_charged": 250.00,
                "minimum_payment": 750.00,
                "due_date": "2024-02-20",
                "pdf_url": f"/statements/{year}{month:02d}.pdf",
            },
        }

    except Exception as e:
        logger.error(f"Error getting statement: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# Risk Assessment Endpoint (Staff only)
@router.post("/risk-assessment")
async def perform_risk_assessment(
    assessment: RiskAssessmentRequest,
    current_user: Dict = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Perform risk assessment (requires analyst role or higher)
    """
    try:
        # Check user role
        user_role = current_user.get("role", UserRole.CUSTOMER.value)
        if user_role not in [UserRole.CREDIT_ANALYST.value, UserRole.MANAGER.value, UserRole.ADMIN.value]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        # TODO: Implement actual risk assessment
        return {
            "success": True,
            "data": {
                "assessment_id": "RISK-345678",
                "risk_score": 0.72,
                "risk_category": "medium",
                "credit_recommendation": "Approve with standard conditions",
                "suggested_limit": 40000.00,
                "suggested_interest_rate": 18.5,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in risk assessment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# Collection Status Endpoint
@router.get("/collection/status")
async def get_collection_status(
    account_id: Optional[str] = Query(None),
    current_user: Dict = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get collection status for account
    """
    try:
        # TODO: Implement actual collection status query
        return {
            "success": True,
            "data": {
                "account_id": account_id or current_user["id"],
                "is_overdue": False,
                "days_overdue": 0,
                "collection_stage": None,
                "overdue_amount": 0.00,
                "last_contact_date": None,
            },
        }

    except Exception as e:
        logger.error(f"Error getting collection status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# Admin Endpoints
@router.get("/admin/portfolio")
async def get_credit_portfolio(
    current_user: Dict = Depends(get_current_user),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Get credit portfolio overview (admin only)
    """
    try:
        # Check admin role
        user_role = current_user.get("role", UserRole.CUSTOMER.value)
        if user_role not in [UserRole.MANAGER.value, UserRole.ADMIN.value]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        # TODO: Implement actual portfolio query
        return {
            "success": True,
            "data": {
                "total_accounts": 1500,
                "total_credit_extended": 75000000.00,
                "total_outstanding": 45000000.00,
                "average_utilization": 0.60,
                "default_rate": 0.02,
                "collection_rate": 0.98,
                "by_risk_category": {
                    "low": {"count": 800, "amount": 30000000.00},
                    "medium": {"count": 500, "amount": 12000000.00},
                    "high": {"count": 200, "amount": 3000000.00},
                },
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting portfolio: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# Health Check
@router.get("/health")
async def health_check():
    """
    Check credit system health
    """
    return {"status": "healthy", "timestamp": datetime.now(UTC).isoformat(), "service": "credit_system"}

