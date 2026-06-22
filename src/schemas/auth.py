"""Auth schema — output of Stage 3c.

Generated THIRD, given DB + API schemas as context.
Roles must match IntentIR roles. Protected/public endpoints must
be exact paths from the API schema.
"""
from pydantic import BaseModel, Field
from typing import Literal


class Permission(BaseModel):
    """A granular permission on a resource."""
    resource: str = Field(description="DB table name e.g. 'contacts'")
    actions: list[Literal["create", "read", "update", "delete", "list"]] = Field(
        description="Allowed CRUD actions on this resource"
    )
    conditions: str | None = Field(
        default=None,
        description="Access conditions e.g. 'own_records_only', 'same_organization'"
    )


class Role(BaseModel):
    """A role with its permissions."""
    name: str = Field(description="Must match a role from IntentIR.roles")
    description: str = Field(description="What this role represents")
    permissions: list[Permission] = Field(
        description="Each resource must be a real DB table name"
    )
    is_default: bool = Field(
        default=False, description="Default role assigned on registration"
    )


class AuthSchema(BaseModel):
    """Authentication and authorization config — output of Stage 3c.
    
    protected_endpoints and public_endpoints must be exact paths
    from the APISchema. Every role must correspond to a role from IntentIR.
    """
    strategy: Literal["jwt", "session", "oauth", "api_key"] = Field(
        description="Authentication mechanism"
    )
    token_expiry_hours: int = Field(default=24, description="Token expiry in hours")
    refresh_token: bool = Field(default=True, description="Whether to issue refresh tokens")
    roles: list[Role] = Field(description="All role definitions with permissions")
    protected_endpoints: list[str] = Field(
        description="Exact API paths requiring authentication — must exist in APISchema"
    )
    public_endpoints: list[str] = Field(
        description="Exact API paths that are publicly accessible — must exist in APISchema"
    )
    password_policy: str = Field(
        default="min_8_chars_with_uppercase_and_number",
        description="Password requirements"
    )
    confidence_scores: dict[str, str] = Field(
        default_factory=dict,
        description="Per-role confidence: role_name -> 'high'|'medium'|'low'"
    )
