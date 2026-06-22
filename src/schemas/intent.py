"""Intent Intermediate Representation — output of Stage 1.

The IntentIR captures the structured understanding of what the user wants to build.
Every Field description guides Gemini's response_schema constrained decoding.
"""
from pydantic import BaseModel, Field
from typing import Literal


class Feature(BaseModel):
    """A feature the application should support."""
    name: str = Field(description="Feature name, e.g. 'user_authentication', 'dashboard'")
    description: str = Field(description="What this feature does")
    priority: Literal["must_have", "should_have", "nice_to_have"] = Field(
        description="Feature priority level"
    )


class UserRole(BaseModel):
    """A user role within the application."""
    name: str = Field(description="Role name in snake_case, e.g. 'admin', 'premium_user'")
    description: str = Field(description="What this role can do")
    permissions: list[str] = Field(
        description="High-level permissions like 'read_contacts', 'manage_users'"
    )


class IntentIR(BaseModel):
    """Intermediate Representation of user intent — output of Stage 1.
    
    This is the first structured artifact in the pipeline. All downstream
    stages consume this IR to generate their respective schemas.
    """
    app_name: str = Field(description="Short snake_case name for the application")
    app_type: Literal[
        "crm", "ecommerce", "saas", "marketplace", 
        "dashboard", "social", "blog", "inventory",
        "booking", "lms", "portal", "other"
    ] = Field(description="Application category")
    description: str = Field(description="One-paragraph description of what the app does")
    entities: list[str] = Field(
        description="Core data entities e.g. ['User', 'Product', 'Order']"
    )
    features: list[Feature] = Field(description="All features mentioned or implied")
    roles: list[UserRole] = Field(
        description="All user roles and their high-level permissions"
    )
    has_auth: bool = Field(description="Whether the app requires authentication")
    has_payments: bool = Field(description="Whether the app has payment/billing features")
    has_analytics: bool = Field(description="Whether the app has analytics/reporting")
    assumptions: list[str] = Field(
        description="Every assumption made for underspecified inputs, "
        "e.g. 'Assumed Stripe for payments since no provider specified'"
    )
    ambiguities: list[str] = Field(
        description="Unresolved ambiguities that could change the architecture"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="Overall confidence in the interpretation"
    )
