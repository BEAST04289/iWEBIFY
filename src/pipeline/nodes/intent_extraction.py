"""Stage 1: Intent Extraction.

Parses a natural language prompt into a structured IntentIR.
Uses Gemini's response_schema for guaranteed valid output.
"""
import time
from src.schemas.intent import IntentIR
from src.pipeline.state import PipelineState
from src.utils import clean_json
from src.llm import generate_json_with_fallback, generate_validated_model

INTENT_SYSTEM_PROMPT = """You are the intent extraction stage of an AI app compiler called iWebify.

Your job: Parse the user's application description into a structured intermediate representation.

Rules:
1. Identify ALL entities (data objects) the app needs — users, products, orders, etc.
2. Identify ALL features — authentication, dashboards, CRUD operations, etc.
3. Identify ALL user roles and their permissions.
4. Mark feature priority: must_have (explicitly mentioned), should_have (strongly implied), nice_to_have (would improve the app).
5. Set has_auth=true if ANY role-based access, login, or permissions are mentioned/implied.
6. Set has_payments=true if billing, subscriptions, payments, or pricing is mentioned.
7. Set has_analytics=true if dashboards, reports, charts, or metrics are mentioned.
8. Document EVERY assumption you make in the assumptions list. Be explicit.
9. Flag genuine ambiguities that could change the architecture in ambiguities list.
10. Be conservative: do NOT hallucinate features not mentioned or implied.
11. Use snake_case for entity names (e.g., 'user', 'product_category').
12. Set confidence to 'high' if the prompt is clear and detailed, 'medium' if somewhat vague, 'low' if very underspecified.

Focus on completeness — missing an entity here means a missing DB table later."""


def intent_extraction(state: PipelineState) -> dict:
    """Extract structured intent from the user's natural language prompt.
    
    Args:
        state: Pipeline state containing user_prompt
        
    Returns:
        Dict with intent, events, stage_timings, cost_estimate updates
    """
    events = list(state.get("events", []))
    events.append({
        "type": "stage_start",
        "stage": "intent_extraction",
        "message": "🔍 Extracting intent from your description..."
    })
    
    start = time.time()
    
    import json
    schema_def = json.dumps(IntentIR.model_json_schema(), indent=2)
    prompt = (
        f"{INTENT_SYSTEM_PROMPT}\n\n"
        f"User prompt:\n{state['user_prompt']}\n\n"
        f"REQUIRED JSON SCHEMA:\n{schema_def}\n\n"
        "Return ONLY a valid JSON object INSTANCE that complies with this schema.\n"
        "Do NOT return the JSON schema definition itself. No markdown, no explanation."
    )
    
    intent = generate_validated_model(prompt, IntentIR)
        
    elapsed = round(time.time() - start, 2)
    
    events.append({
        "type": "stage_complete",
        "stage": "intent_extraction",
        "message": f"✅ Intent extracted: {intent.app_name} ({intent.app_type}) — "
                   f"{len(intent.entities)} entities, {len(intent.features)} features, "
                   f"{len(intent.roles)} roles",
        "duration": elapsed,
        "data": {
            "app_name": intent.app_name,
            "app_type": intent.app_type,
            "entity_count": len(intent.entities),
            "feature_count": len(intent.features),
            "assumptions_count": len(intent.assumptions),
            "confidence": intent.confidence,
        }
    })
    
    timings = dict(state.get("stage_timings", {}))
    timings["intent_extraction"] = elapsed
    
    return {
        "intent": intent,
        "events": events,
        "stage_timings": timings,
        "current_stage": "intent_extraction",
        "cost_estimate": state.get("cost_estimate", 0.0) + 0.001,  # Approximate
    }
