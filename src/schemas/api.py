"""API schema — output of Stage 3b.

Generated SECOND, given the DB schema as context.
Every endpoint must reference a real DB table. Request/response fields
must match DB column names exactly.
"""
from pydantic import BaseModel, Field
from typing import Literal


class APIField(BaseModel):
    """A field in an API request body or response."""
    name: str = Field(description="Must match a DB column name exactly")
    type: Literal[
        "string", "integer", "float", "boolean", "uuid", "array", "object"
    ] = Field(description="Field data type")
    required: bool = Field(default=True, description="Whether this field is required")
    description: str = Field(default="", description="What this field represents")


class APIEndpoint(BaseModel):
    """A single REST API endpoint."""
    path: str = Field(description="URL path e.g. '/api/contacts' or '/api/contacts/{id}'")
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = Field(
        description="HTTP method"
    )
    summary: str = Field(description="What this endpoint does")
    request_body: list[APIField] | None = Field(
        default=None,
        description="Request body fields — must match DB columns for the db_table"
    )
    response_fields: list[APIField] = Field(
        description="Fields returned in the response — must match DB columns"
    )
    required_role: str | None = Field(
        default=None,
        description="Role name from IntentIR.roles that can access this endpoint"
    )
    is_protected: bool = Field(default=True, description="Whether authentication is required")
    db_table: str = Field(
        description="Primary DB table this endpoint operates on — must be a real table name"
    )
    status_codes: list[int] = Field(
        default_factory=lambda: [200, 400, 401, 403],
        description="Expected HTTP status codes"
    )


class APISchema(BaseModel):
    """REST API schema — output of Stage 3b.
    
    Every endpoint's db_table must exist in DBSchema.
    Every request_body/response field name must match a column in that table.
    Every required_role must be a real role from IntentIR.
    """
    base_path: str = Field(default="/api", description="API base path prefix")
    endpoints: list[APIEndpoint] = Field(description="All API endpoints")
    confidence_scores: dict[str, str] = Field(
        default_factory=dict,
        description="Per-endpoint confidence: path -> 'high'|'medium'|'low'"
    )
