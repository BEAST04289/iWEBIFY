"""LangGraph Pipeline — the core compiler graph.

Wires all pipeline nodes into a StateGraph with conditional edges
for the validation → repair loop.

Graph structure:
    intent_extraction → system_design → db_schema → api_schema →
    auth_schema → business_schema → ui_schema → validation →
    (conditional: pass → execution, fail → repair → validation loop)
"""
from langgraph.graph import StateGraph, END

from src.config import MAX_REPAIR_ATTEMPTS
from src.pipeline.state import PipelineState
from src.pipeline.nodes.intent_extraction import intent_extraction
from src.pipeline.nodes.system_design import system_design
from src.pipeline.nodes.schema_generation import (
    generate_db_schema,
    generate_api_schema,
    generate_auth_schema,
    generate_business_schema,
    generate_ui_schema,
)
from src.pipeline.nodes.validation import validation
from src.pipeline.nodes.repair import repair
from src.pipeline.nodes.execution import execution


def _should_repair_or_execute(state: PipelineState) -> str:
    """Conditional edge: route to repair if critical errors, else execute.
    
    Also checks total repair attempts to prevent infinite loops.
    """
    errors = state.get("validation_errors", [])
    critical = [e for e in errors if e.get("severity") == "critical"]
    
    if not critical:
        return "execution"
    
    # Check if any layer still has repair budget
    repair_attempts = state.get("repair_attempts", {})
    has_budget = any(
        repair_attempts.get(layer, 0) < MAX_REPAIR_ATTEMPTS
        for layer in set(e.get("layer", "") for e in critical)
    )
    
    if has_budget:
        return "repair"
    
    # All layers exhausted their repair budget — proceed anyway
    return "execution"


def build_pipeline() -> StateGraph:
    """Build and compile the iWebify compiler pipeline.
    
    Returns a compiled LangGraph that can be invoked with:
        result = pipeline.invoke(initial_state)
    or streamed with:
        async for chunk in pipeline.astream(initial_state, stream_mode="values"):
            ...
    """
    graph = StateGraph(PipelineState)
    
    # Add all nodes
    graph.add_node("intent_extraction", intent_extraction)
    graph.add_node("system_design", system_design)
    graph.add_node("db_schema", generate_db_schema)
    graph.add_node("api_schema", generate_api_schema)
    graph.add_node("auth_schema", generate_auth_schema)
    graph.add_node("business_schema", generate_business_schema)
    graph.add_node("ui_schema", generate_ui_schema)
    graph.add_node("validation", validation)
    graph.add_node("repair", repair)
    graph.add_node("execution", execution)
    
    # Sequential edges: the compiler pipeline
    graph.set_entry_point("intent_extraction")
    graph.add_edge("intent_extraction", "system_design")
    graph.add_edge("system_design", "db_schema")
    graph.add_edge("db_schema", "api_schema")
    graph.add_edge("api_schema", "auth_schema")
    graph.add_edge("auth_schema", "business_schema")
    graph.add_edge("business_schema", "ui_schema")
    graph.add_edge("ui_schema", "validation")
    
    # Conditional: validation → repair OR execution
    graph.add_conditional_edges(
        "validation",
        _should_repair_or_execute,
        {
            "repair": "repair",
            "execution": "execution",
        },
    )
    
    # Repair loops back to validation
    graph.add_edge("repair", "validation")
    
    # Execution is the terminal node
    graph.add_edge("execution", END)
    
    return graph.compile()


# Singleton compiled pipeline
pipeline = build_pipeline()
