"""Business Logic schema — output of Stage 3d.

Generated FOURTH, given DB + API + Auth schemas as context.
Every affected_endpoint must be an exact path from APISchema.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal


class BusinessRule(BaseModel):
    """A single business rule, gate, or automation."""
    name: str = Field(description="Rule identifier in snake_case")
    type: Literal[
        "access_gate", "payment_gate", "rate_limit",
        "auto_assign", "notification", "validation", "audit_log"
    ] = Field(description="Category of business rule")
    description: str = Field(description="What this rule does")
    trigger: str = Field(
        description="When this rule fires e.g. 'on POST /api/contacts'"
    )
    condition: str = Field(
        description="The condition that activates the rule e.g. 'user.role != admin'"
    )
    action: str = Field(
        description="What happens when the rule fires e.g. 'return 403'"
    )
    affected_endpoints: list[str] = Field(
        default_factory=list,
        description="Exact API paths affected — must exist in APISchema"
    )


class BusinessLogicSchema(BaseModel):
    """Business rules and logic — output of Stage 3d.
    
    All affected_endpoints must be exact paths from the APISchema.
    Only define rules that are explicitly needed by the application.
    """
    rules: list[BusinessRule] = Field(description="All business rules")
    premium_features: list[str] = Field(
        default_factory=list,
        description="Feature names behind a payment/subscription gate"
    )
    free_tier_limits: dict[str, int] = Field(
        default_factory=dict,
        description="Resource name -> max count for free tier e.g. {'contacts': 100}"
    )
    webhook_events: list[str] = Field(
        default_factory=list,
        description="Events that trigger webhooks e.g. ['contact.created', 'order.paid']"
    )
    confidence_scores: dict[str, str] = Field(
        default_factory=dict,
        description="Per-rule confidence: rule_name -> 'high'|'medium'|'low'"
    )
