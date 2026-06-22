"""Pipeline state definition for the iWebify compiler.

This TypedDict defines the complete state flowing through the LangGraph pipeline.
Each node reads from and writes to specific fields. Events are appended
for SSE streaming to the frontend.
"""
from typing import TypedDict, Optional, Literal, Any
from src.schemas.intent import IntentIR
from src.schemas.design import SystemDesign
from src.schemas.database import DBSchema
from src.schemas.api import APISchema
from src.schemas.auth import AuthSchema
from src.schemas.business import BusinessLogicSchema
from src.schemas.ui import UISchema


class PipelineEvent(TypedDict, total=False):
    """A single event emitted during pipeline execution for SSE streaming."""
    type: str      # stage_start, stage_complete, stage_error, repair_start, repair_complete, execution_step, done
    stage: str     # Which pipeline stage
    message: str   # Human-readable message
    duration: float  # Seconds elapsed (for stage_complete)
    data: Any      # Optional payload (schema JSON, error details, etc.)


class PipelineState(TypedDict, total=False):
    """Complete state for the iWebify compiler pipeline.
    
    Fields are populated stage-by-stage:
    1. user_prompt, mode, session_id (input)
    2. intent (Stage 1: Intent Extraction)
    3. design (Stage 2: System Design)
    4. db_schema (Stage 3a: DB - foundation)
    5. api_schema (Stage 3b: API - given DB)
    6. auth_schema (Stage 3c: Auth - given DB+API)
    7. business_schema (Stage 3d: Business - given DB+API+Auth)
    8. ui_schema (Stage 3e: UI - given everything)
    9. validation_errors (Stage 4: Validation)
    10. execution_result (Stage 5: Execution)
    """
    # Input
    user_prompt: str
    mode: str  # "generate" or "patch"
    session_id: str
    
    # Stage outputs (sequential dependency injection)
    intent: IntentIR
    design: SystemDesign
    db_schema: DBSchema
    api_schema: APISchema
    auth_schema: AuthSchema
    business_schema: BusinessLogicSchema
    ui_schema: UISchema
    
    # Validation
    validation_errors: list[dict]
    repair_attempts: dict[str, int]  # layer -> attempt count
    repair_history: list[dict]
    
    # Execution
    execution_result: dict
    test_results: list[dict]
    
    # Metrics & streaming
    events: list[dict]  # PipelineEvent dicts for SSE
    stage_timings: dict[str, float]
    total_retries: int
    cost_estimate: float
    current_stage: str
    error_message: str
    pipeline_failed: bool
