"""UI schema — output of Stage 3e. GENERATED LAST.

Depends on ALL other schemas. Every api_endpoint must be an exact
path from APISchema. Every allowed_role must exist in AuthSchema.
Every field must map to real response_fields from the referenced endpoint.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal


class UIComponent(BaseModel):
    """A UI component on a page."""
    type: Literal[
        "table", "form", "chart", "card", "stat_card",
        "nav", "modal", "button", "input", "select", "badge", "list"
    ] = Field(description="Component type")
    id: str = Field(description="Unique identifier e.g. 'contacts_table'")
    label: str = Field(description="Display label for this component")
    api_endpoint: str = Field(
        description="Exact API path from APISchema that feeds this component"
    )
    fields: list[str] = Field(
        default_factory=list,
        description="Field names from the API response to display — must be real response_fields"
    )
    actions: list[str] = Field(
        default_factory=list,
        description="Actions available e.g. ['create', 'edit', 'delete']"
    )


class UIPage(BaseModel):
    """A page in the application."""
    path: str = Field(description="URL path e.g. '/dashboard'")
    title: str = Field(description="Page display title")
    allowed_roles: list[str] = Field(
        description="Role names from AuthSchema.roles that can see this page"
    )
    components: list[UIComponent] = Field(description="Components on this page")
    layout: Literal["full_width", "sidebar", "centered", "split"] = Field(
        description="Page layout style"
    )


class UISchema(BaseModel):
    """Frontend UI schema — output of Stage 3e. Depends on all other schemas.
    
    This is the final schema generated. Every data reference must point
    to a real API endpoint, every role must exist in AuthSchema.
    """
    pages: list[UIPage] = Field(description="All pages in the application")
    nav_items: list[dict] = Field(
        default_factory=list,
        description="Navigation items with keys: label, path, icon, roles"
    )
    theme: Literal["light", "dark", "system"] = Field(
        default="dark", description="Color theme"
    )
    confidence_scores: dict[str, str] = Field(
        default_factory=dict,
        description="Per-page confidence: page_path -> 'high'|'medium'|'low'"
    )
