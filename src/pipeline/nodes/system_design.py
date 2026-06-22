"""Stage 2: System Design.

Converts IntentIR into a concrete architectural blueprint.
Defines entity relationships, data flows, auth strategy.
"""
import time
from google import genai
from google.genai import types

from src.config import GEMINI_API_KEY, MODEL_NAME, TEMPERATURE
from src.schemas.design import SystemDesign
from src.pipeline.state import PipelineState


DESIGN_SYSTEM_PROMPT = """You are the system design stage of an AI app compiler called iWebify.

Given the extracted intent, design the complete application architecture.

Rules:
1. Confirm and refine entity names — use snake_case plural for table names (e.g., 'users', 'contacts').
2. Define ALL entity relationships with correct cardinality (one_to_one, one_to_many, many_to_many).
3. For many_to_many, include the junction table as an entity.
4. Define key data flows — how data moves between components.
5. Choose auth_strategy based on the app type (jwt for APIs, session for web apps).
6. Set payment_provider only if has_payments is true.
7. storage_strategy should be 'sqlite_per_session' (our execution layer uses SQLite).
8. Record key design decisions and rationale in design_notes.
9. Every entity from the intent MUST appear in the entities list.
10. Think about implicit entities — if there are Orders, there should be OrderItems."""


def system_design(state: PipelineState) -> dict:
    """Generate system architecture from extracted intent.
    
    Args:
        state: Pipeline state containing intent
        
    Returns:
        Dict with design, events, stage_timings updates
    """
    events = list(state.get("events", []))
    events.append({
        "type": "stage_start",
        "stage": "system_design",
        "message": "🏗️ Designing system architecture..."
    })
    
    start = time.time()
    intent = state["intent"]
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Context isolation: only pass what this stage needs
    prompt = (
        f"{DESIGN_SYSTEM_PROMPT}\n\n"
        f"Extracted Intent:\n{intent.model_dump_json(indent=2)}"
    )
    
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SystemDesign,
            temperature=TEMPERATURE,
        ),
    )
    
    design: SystemDesign = response.parsed
    elapsed = round(time.time() - start, 2)
    
    events.append({
        "type": "stage_complete",
        "stage": "system_design",
        "message": f"✅ Architecture designed: {len(design.entities)} entities, "
                   f"{len(design.relations)} relationships, "
                   f"auth={design.auth_strategy}",
        "duration": elapsed,
        "data": {
            "entities": design.entities,
            "relation_count": len(design.relations),
            "auth_strategy": design.auth_strategy,
        }
    })
    
    timings = dict(state.get("stage_timings", {}))
    timings["system_design"] = elapsed
    
    return {
        "design": design,
        "events": events,
        "stage_timings": timings,
        "current_stage": "system_design",
        "cost_estimate": state.get("cost_estimate", 0.0) + 0.001,
    }
