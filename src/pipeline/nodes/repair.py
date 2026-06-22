"""Stage 4b: Targeted Repair Engine.

CRITICAL ARCHITECTURE:
- Repair is UNIDIRECTIONAL — only modifies downstream layers.
- DB schema is NEVER repaired (it is the source of truth).
- Each broken layer gets a targeted re-prompt with ONLY the errors
  and the upstream schemas it must be consistent with.
- temperature=0.0 for repair (maximum determinism).
"""
import time
from google import genai
from google.genai import types

from src.config import GEMINI_API_KEY, MODEL_NAME, REPAIR_TEMPERATURE, MAX_REPAIR_ATTEMPTS
from src.schemas.api import APISchema
from src.schemas.auth import AuthSchema
from src.schemas.business import BusinessLogicSchema
from src.schemas.ui import UISchema
from src.pipeline.state import PipelineState


# Repair prompt template — injected with specific errors and ground truth
REPAIR_PROMPT = """You are a REPAIR agent for an AI app compiler.

A cross-layer validation found errors in the {layer_name} schema.
Your job: fix ONLY the listed errors. Do NOT change anything else.

The schemas listed below as "GROUND TRUTH" are correct and must NOT be contradicted.
Your output must be consistent with them.

ERRORS TO FIX:
{errors}

CURRENT (BROKEN) SCHEMA:
{current_schema}

GROUND TRUTH:
{ground_truth}

Fix the errors and return the corrected schema. Only change what's needed to resolve the errors."""


# Layer order: downstream only. DB is never repaired.
LAYER_ORDER = ["api_schema", "auth_schema", "business_schema", "ui_schema"]

# Map layer names to Pydantic models
LAYER_MODELS = {
    "api_schema": APISchema,
    "auth_schema": AuthSchema,
    "business_schema": BusinessLogicSchema,
    "ui_schema": UISchema,
}


def _get_ground_truth(state: PipelineState, layer: str) -> str:
    """Get the ground truth schemas for a layer's repair prompt."""
    parts = []
    
    # DB schema is always ground truth
    parts.append(f"DB Schema:\n{state['db_schema'].model_dump_json(indent=2)}")
    
    if layer in ("auth_schema", "business_schema", "ui_schema"):
        parts.append(f"API Schema:\n{state['api_schema'].model_dump_json(indent=2)}")
    
    if layer in ("business_schema", "ui_schema"):
        parts.append(f"Auth Schema:\n{state['auth_schema'].model_dump_json(indent=2)}")
    
    return "\n\n".join(parts)


def repair(state: PipelineState) -> dict:
    """Targeted repair of broken schema layers.
    
    Groups errors by layer, repairs each broken layer with a focused prompt.
    Repair flows downstream only — never modifies DB schema.
    """
    events = list(state.get("events", []))
    repair_attempts = dict(state.get("repair_attempts", {}))
    repair_history = list(state.get("repair_history", []))
    total_retries = state.get("total_retries", 0)
    
    # Group critical errors by layer
    critical_errors = [
        e for e in state.get("validation_errors", [])
        if e.get("severity") == "critical"
    ]
    
    errors_by_layer: dict[str, list[dict]] = {}
    for error in critical_errors:
        layer = error.get("layer", "unknown")
        errors_by_layer.setdefault(layer, []).append(error)
    
    events.append({
        "type": "repair_start",
        "stage": "repair",
        "message": f"🔧 Repairing {len(errors_by_layer)} broken layers: {', '.join(errors_by_layer.keys())}",
    })
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Repair each layer in downstream order
    updates = {}
    for layer in LAYER_ORDER:
        if layer not in errors_by_layer:
            continue
        
        layer_errors = errors_by_layer[layer]
        attempt = repair_attempts.get(layer, 0) + 1
        
        if attempt > MAX_REPAIR_ATTEMPTS:
            events.append({
                "type": "repair_skip",
                "stage": "repair",
                "message": f"⏭️ Skipping {layer} — exceeded {MAX_REPAIR_ATTEMPTS} repair attempts",
            })
            continue
        
        repair_attempts[layer] = attempt
        total_retries += 1
        
        start = time.time()
        
        # Build repair prompt
        error_text = "\n".join(
            f"  - [{e['type']}] {e['message']}\n    Fix: {e.get('fix', 'N/A')}"
            for e in layer_errors
        )
        
        current_schema = state[layer]
        prompt = REPAIR_PROMPT.format(
            layer_name=layer,
            errors=error_text,
            current_schema=current_schema.model_dump_json(indent=2),
            ground_truth=_get_ground_truth(state, layer),
        )
        
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=LAYER_MODELS[layer],
                    temperature=REPAIR_TEMPERATURE,
                ),
            )
            
            repaired = response.parsed
            elapsed = round(time.time() - start, 2)
            
            # Record repair history
            repair_history.append({
                "layer": layer,
                "attempt": attempt,
                "errors_fixed": [e["message"] for e in layer_errors],
                "duration": elapsed,
            })
            
            updates[layer] = repaired
            
            events.append({
                "type": "repair_complete",
                "stage": "repair",
                "message": f"✅ Repaired {layer} (attempt {attempt}) — fixed {len(layer_errors)} errors in {elapsed}s",
                "duration": elapsed,
            })
            
        except Exception as e:
            events.append({
                "type": "repair_error",
                "stage": "repair",
                "message": f"❌ Failed to repair {layer}: {str(e)[:200]}",
            })
    
    result = {
        "events": events,
        "repair_attempts": repair_attempts,
        "repair_history": repair_history,
        "total_retries": total_retries,
        "current_stage": "repair",
    }
    result.update(updates)
    
    return result
