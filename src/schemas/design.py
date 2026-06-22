"""System Design schema — output of Stage 2.

Converts the IntentIR into a concrete architectural blueprint:
entity relationships, data flows, auth strategy, storage decisions.
"""
from pydantic import BaseModel, Field
from typing import Literal


class EntityRelation(BaseModel):
    """A relationship between two entities."""
    from_entity: str = Field(description="Source entity name")
    to_entity: str = Field(description="Target entity name")
    relation_type: Literal["one_to_one", "one_to_many", "many_to_many"] = Field(
        description="Cardinality of the relationship"
    )
    description: str = Field(description="What this relationship represents")


class DataFlow(BaseModel):
    """A data flow between application components."""
    from_component: str = Field(description="Source component or entity")
    to_component: str = Field(description="Target component or entity")
    data: str = Field(description="What data flows between them")
    trigger: str = Field(description="What triggers this flow, e.g. 'user_action', 'cron', 'webhook'")


class SystemDesign(BaseModel):
    """System architecture — output of Stage 2.
    
    This is the blueprint that all schema generators build from.
    It defines the structural decisions: what entities exist, how they
    relate, what auth strategy to use, and key design rationale.
    """
    app_name: str = Field(description="Application name")
    entities: list[str] = Field(
        description="Confirmed entity names with proper snake_case naming"
    )
    relations: list[EntityRelation] = Field(
        description="All entity relationships with cardinality"
    )
    data_flows: list[DataFlow] = Field(
        description="Key data flows through the system"
    )
    auth_strategy: Literal["jwt", "session", "oauth", "api_key"] = Field(
        description="Authentication mechanism"
    )
    payment_provider: str | None = Field(
        default=None, description="Payment provider if needed, e.g. 'stripe', 'razorpay'"
    )
    storage_strategy: str = Field(
        default="sqlite_per_session",
        description="Storage approach, e.g. 'sqlite_per_session', 'postgresql'"
    )
    design_notes: list[str] = Field(
        description="Key architectural decisions and rationale"
    )
