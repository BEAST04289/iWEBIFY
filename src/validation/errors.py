"""iWebify Validation Error Types and Classification.

Defines the error taxonomy used by the cross-layer validator
and repair engine. Errors are classified by type, severity,
and which layer they originate from.
"""
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class ErrorType(str, Enum):
    """Classification of validation errors."""
    MISSING_FIELD = "missing_field"           # A referenced field doesn't exist
    ORPHANED_REFERENCE = "orphaned_reference" # A reference points to nothing
    HALLUCINATED_FIELD = "hallucinated_field"  # A field exists that shouldn't
    TYPE_MISMATCH = "type_mismatch"           # Field type doesn't match across layers
    ROLE_MISMATCH = "role_mismatch"           # Role referenced doesn't exist in auth
    ENTITY_NOT_FOUND = "entity_not_found"     # Entity referenced doesn't exist in DB
    CIRCULAR_DEPENDENCY = "circular_dependency"  # Circular FK or relationship
    MISSING_ENDPOINT = "missing_endpoint"     # UI references API endpoint that doesn't exist
    MISSING_TABLE = "missing_table"           # API references DB table that doesn't exist
    INCONSISTENT_AUTH = "inconsistent_auth"   # Auth rules conflict
    EXECUTION_FAILURE = "execution_failure"   # Smoke test failed


class ErrorSeverity(str, Enum):
    """Severity levels for validation errors."""
    ERROR = "error"      # Must be fixed before execution
    WARNING = "warning"  # Should be fixed but won't block execution


class SchemaLayer(str, Enum):
    """Which schema layer the error belongs to."""
    DB = "db_schema"
    API = "api_schema"
    AUTH = "auth_schema"
    BUSINESS = "business_schema"
    UI = "ui_schema"


class CrossLayerError(BaseModel):
    """A single cross-layer validation error.
    
    This is the structured error that gets passed to the repair engine.
    It contains enough context for the repair prompt to understand
    exactly what's broken and how to fix it.
    """
    error_type: ErrorType = Field(description="Classification of the error")
    severity: ErrorSeverity = Field(description="How critical this error is")
    layer: SchemaLayer = Field(description="Which layer needs to be repaired")
    description: str = Field(description="Human-readable error description")
    source_layer: str = Field(description="The layer that makes the reference")
    source_ref: str = Field(description="The specific field/path making the reference")
    target_layer: str = Field(description="The layer being referenced")
    target_ref: str = Field(description="The specific field/path that should exist")
    suggested_fix: Optional[str] = Field(
        default=None, 
        description="Suggested fix action for the repair engine"
    )

    def to_repair_context(self) -> str:
        """Format this error as context for a repair prompt."""
        ctx = f"ERROR [{self.error_type.value}] in {self.layer.value}:\n"
        ctx += f"  {self.description}\n"
        ctx += f"  Source: {self.source_layer}.{self.source_ref}\n"
        ctx += f"  Expected target: {self.target_layer}.{self.target_ref}\n"
        if self.suggested_fix:
            ctx += f"  Suggested fix: {self.suggested_fix}\n"
        return ctx


class ValidationReport(BaseModel):
    """Complete validation report from a cross-layer check."""
    passed: bool = Field(description="Whether all checks passed")
    errors: list[CrossLayerError] = Field(default_factory=list, description="All errors found")
    warnings: list[CrossLayerError] = Field(default_factory=list, description="Non-blocking warnings")
    checks_run: int = Field(default=0, description="Total number of checks executed")
    checks_passed: int = Field(default=0, description="Number of checks that passed")
    
    @property
    def error_count(self) -> int:
        return len(self.errors)
    
    @property
    def warning_count(self) -> int:
        return len(self.warnings)
    
    def errors_for_layer(self, layer: SchemaLayer) -> list[CrossLayerError]:
        """Get all errors that need to be repaired in a specific layer."""
        return [e for e in self.errors if e.layer == layer]
    
    def summary(self) -> str:
        """Human-readable summary of the validation report."""
        if self.passed:
            return f"✅ Validation passed: {self.checks_passed}/{self.checks_run} checks OK"
        return (
            f"❌ Validation failed: {self.error_count} errors, "
            f"{self.warning_count} warnings "
            f"({self.checks_passed}/{self.checks_run} checks passed)"
        )
