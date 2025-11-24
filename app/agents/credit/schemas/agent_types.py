"""
Credit Agent Types and User Roles
"""

from enum import Enum


class CreditAgentType(str, Enum):
    """Types of credit agents"""

    SUPERVISOR = "supervisor"
    CREDIT_BALANCE = "credit_balance"
    CREDIT_APPLICATION = "credit_application"
    PAYMENT = "payment"
    STATEMENT = "statement"
    PRODUCT_CREDIT = "product_credit"
    RISK_ASSESSMENT = "risk_assessment"
    COLLECTION = "collection"
    COMPLIANCE = "compliance"
    FRAUD_DETECTION = "fraud_detection"
    CREDIT_INQUIRY = "credit_inquiry"
    DISPUTE_RESOLUTION = "dispute_resolution"
    REFINANCING = "refinancing"
    PORTFOLIO_ANALYTICS = "portfolio_analytics"
    REPORTING = "reporting"
    PREDICTIVE_ANALYTICS = "predictive_analytics"
    FALLBACK = "fallback"


class UserRole(str, Enum):
    """User roles in credit system"""

    CUSTOMER = "customer"
    CREDIT_ANALYST = "credit_analyst"
    MANAGER = "manager"
    ADMIN = "admin"
    COLLECTION_AGENT = "collection_agent"
    COMPLIANCE_OFFICER = "compliance_officer"
