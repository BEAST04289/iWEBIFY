"""Stage 4: Validation Node.

Runs cross-layer validation checks + smoke tests.
Routes to either execution (pass) or repair (fail).
"""
import time
from src.pipeline.state import PipelineState
from src.validation.cross_layer import run_all_validations


def validation(state: PipelineState) -> dict:
    """Run cross-layer validation on all generated schemas.
    
    Returns validation_errors for the conditional edge to evaluate.
    """
    events = list(state.get("events", []))
    events.append({
        "type": "stage_start",
        "stage": "validation",
        "message": "🔍 Running cross-layer validation checks..."
    })
    
    start = time.time()
    
    critical_errors, warnings = run_all_validations(
        db_schema=state["db_schema"],
        api_schema=state["api_schema"],
        auth_schema=state["auth_schema"],
        business_schema=state["business_schema"],
        ui_schema=state["ui_schema"],
    )
    
    elapsed = round(time.time() - start, 2)
    all_errors = critical_errors + warnings
    
    if not critical_errors:
        events.append({
            "type": "stage_complete",
            "stage": "validation",
            "message": f"✅ Validation passed! {len(warnings)} warnings, 0 critical errors",
            "duration": elapsed,
            "data": {"critical": 0, "warnings": len(warnings)}
        })
    else:
        events.append({
            "type": "stage_error",
            "stage": "validation",
            "message": f"⚠️ Validation found {len(critical_errors)} critical errors, {len(warnings)} warnings — triggering repair",
            "duration": elapsed,
            "data": {
                "critical": len(critical_errors),
                "warnings": len(warnings),
                "errors": [e["message"] for e in critical_errors[:5]],  # First 5 for SSE
            }
        })
    
    timings = dict(state.get("stage_timings", {}))
    timings["validation"] = elapsed
    
    return {
        "validation_errors": all_errors,
        "events": events,
        "stage_timings": timings,
        "current_stage": "validation",
    }
