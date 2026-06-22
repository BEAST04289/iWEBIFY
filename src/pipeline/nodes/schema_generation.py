"""Stage 3: Sequential Schema Generation (3a → 3b → 3c → 3d → 3e).

CRITICAL ARCHITECTURE: Schemas are generated SEQUENTIALLY, not in parallel.
Each layer receives ONLY its direct predecessors as context (context isolation).

Order:
  3a. DB Schema (foundation) — given design + intent
  3b. API Schema — given db_schema + design + intent
  3c. Auth Schema — given db_schema + api_schema + intent
  3d. Business Logic — given db_schema + api_schema + auth_schema + intent
  3e. UI Schema — given everything above
"""
import time
from google import genai
from google.genai import types

from src.config import GEMINI_API_KEY, MODEL_NAME, TEMPERATURE
from src.schemas.database import DBSchema
from src.schemas.api import APISchema
from src.schemas.auth import AuthSchema
from src.schemas.business import BusinessLogicSchema
from src.schemas.ui import UISchema
from src.pipeline.state import PipelineState


# ============================================================
# SYSTEM PROMPTS — each is highly specific to its layer
# ============================================================

DB_PROMPT = """You are the DATABASE SCHEMA generator of an AI app compiler.

Generate a complete SQLite-compatible database schema from the system design.

STRICT RULES:
1. Every entity from the design MUST have a table. Use snake_case plural names (e.g., 'users', 'contacts').
2. Every table MUST have: id (uuid, primary_key), created_at (timestamp), updated_at (timestamp).
3. Use these SQLite-compatible types ONLY: uuid, text, varchar, integer, float, boolean, timestamp, jsonb, enum.
4. For foreign keys, use format 'table_name.column_name' (e.g., 'users.id').
5. For many_to_many relationships, create a junction table.
6. Add indexes for foreign key columns and frequently queried columns.
7. For enum columns, ALWAYS provide enum_values list.
8. Mark nullable=false for required fields, nullable=true for optional fields.
9. Do NOT add tables that aren't in the design entities list.
10. This schema is the FOUNDATION — all other schemas will build on it. Be thorough.

System Design:
{design}

Original Intent:
{intent}"""

API_PROMPT = """You are the API SCHEMA generator of an AI app compiler.

Generate a complete REST API schema from the database schema.

STRICT RULES:
1. Every DB table should have standard CRUD endpoints: GET (list), GET/{id}, POST, PUT/{id}, DELETE/{id}.
2. EVERY endpoint's db_table MUST be an EXACT table name from the DB schema provided below.
3. EVERY field in request_body and response_fields MUST EXACTLY MATCH a column name from that DB table.
4. Use /api/ prefix for all paths.
5. Path parameters use {{id}} format: /api/users/{{id}}.
6. For list endpoints, response_fields should include all readable columns.
7. For create/update endpoints, request_body should include writable columns (NOT id, created_at, updated_at).
8. required_role should be a role name from the intent, or null for public endpoints.
9. Set is_protected=true for endpoints that need authentication, is_protected=false for public ones.
10. Include appropriate status_codes for each endpoint.

AVAILABLE DB TABLES AND THEIR COLUMNS:
{db_tables}

System Design:
{design}

Original Intent:
{intent}"""

AUTH_PROMPT = """You are the AUTH SCHEMA generator of an AI app compiler.

Generate authentication and authorization config from the DB + API schemas.

STRICT RULES:
1. Every role from the intent MUST be defined in the roles list.
2. strategy MUST match the auth_strategy from the system design.
3. protected_endpoints MUST be EXACT paths from the API schema (copy-paste them).
4. public_endpoints MUST be EXACT paths from the API schema (copy-paste them).
5. EVERY endpoint from the API schema must appear in EITHER protected_endpoints OR public_endpoints.
6. Each role's permissions must reference real DB table names as resources.
7. actions must be from: create, read, update, delete, list.
8. Mark exactly ONE role as is_default=true (usually the basic 'user' role).
9. Do NOT invent endpoints that don't exist in the API schema.

AVAILABLE API ENDPOINTS:
{api_endpoints}

DB TABLES:
{db_tables}

Original Intent:
{intent}"""

BUSINESS_PROMPT = """You are the BUSINESS LOGIC generator of an AI app compiler.

Generate business rules, gates, and automations from the existing schemas.

STRICT RULES:
1. EVERY rule's affected_endpoints MUST be EXACT paths from the API schema.
2. Only define rules that are EXPLICITLY needed by the application.
3. Common rules: access_gate (role-based), validation (field checks), audit_log (tracking), notification (alerts).
4. trigger format: 'on METHOD /api/path' (e.g., 'on POST /api/contacts').
5. condition should be a human-readable expression (e.g., 'user.role != admin').
6. action should describe what happens (e.g., 'return 403', 'send email', 'log event').
7. If has_payments=true, add payment_gate rules.
8. Keep it minimal — fewer correct rules beats many hallucinated ones.
9. premium_features should list feature names behind a paywall (empty if no payments).
10. free_tier_limits can specify resource counts (empty if no freemium model).

AVAILABLE API ENDPOINTS:
{api_endpoints}

AUTH ROLES:
{auth_roles}

DB TABLES:
{db_tables}

Original Intent:
{intent}"""

UI_PROMPT = """You are the UI SCHEMA generator of an AI app compiler.

Generate a complete frontend interface from all existing schemas.

STRICT RULES:
1. Every page's components MUST reference EXACT API endpoint paths via api_endpoint field.
2. Every page's allowed_roles MUST be EXACT role names from the auth schema.
3. Every component's fields MUST be EXACT field names from that API endpoint's response_fields.
4. Standard pages: login, register (if auth), dashboard, one list/detail page per major entity, settings.
5. Component types: table (for lists), form (for create/edit), stat_card (for metrics), chart (for analytics).
6. Each component needs a unique id (e.g., 'contacts_table', 'create_contact_form').
7. Layout types: sidebar (main pages), centered (auth pages), full_width (dashboards).
8. nav_items should include all pages visible in navigation with label, path, icon, and roles.
9. theme should be 'dark' by default.
10. Be practical — include pages that make the app functional, not decorative.

AVAILABLE API ENDPOINTS AND THEIR RESPONSE FIELDS:
{api_details}

AUTH ROLES:
{auth_roles}

DB TABLES:
{db_tables}

Original Intent:
{intent}"""


def _make_client():
    """Create a Gemini client."""
    return genai.Client(api_key=GEMINI_API_KEY)


def _format_db_tables(db_schema: DBSchema) -> str:
    """Format DB tables for injection into prompts."""
    lines = []
    for table in db_schema.tables:
        cols = ", ".join(f"{c.name} ({c.type})" for c in table.columns)
        lines.append(f"  - {table.name}: [{cols}]")
    return "\n".join(lines)


def _format_api_endpoints(api_schema: APISchema) -> str:
    """Format API endpoints for injection into prompts."""
    lines = []
    for ep in api_schema.endpoints:
        fields = ", ".join(f.name for f in ep.response_fields)
        lines.append(f"  - {ep.method} {ep.path} → [{fields}] (table: {ep.db_table})")
    return "\n".join(lines)


def _format_api_details(api_schema: APISchema) -> str:
    """Format API endpoints with full response field details."""
    lines = []
    for ep in api_schema.endpoints:
        resp = ", ".join(f"{f.name}:{f.type}" for f in ep.response_fields)
        req = ""
        if ep.request_body:
            req = " | body: " + ", ".join(f"{f.name}:{f.type}" for f in ep.request_body)
        lines.append(f"  - {ep.method} {ep.path} → [{resp}]{req}")
    return "\n".join(lines)


def _format_auth_roles(auth_schema: AuthSchema) -> str:
    """Format auth roles for injection into prompts."""
    lines = []
    for role in auth_schema.roles:
        perms = ", ".join(f"{p.resource}:{','.join(p.actions)}" for p in role.permissions)
        lines.append(f"  - {role.name}: [{perms}]")
    return "\n".join(lines)


# ============================================================
# GENERATOR FUNCTIONS — each is a LangGraph node
# ============================================================

def generate_db_schema(state: PipelineState) -> dict:
    """Stage 3a: Generate DB schema (FOUNDATION).
    
    Context: design + intent only (context isolation).
    """
    events = list(state.get("events", []))
    events.append({
        "type": "stage_start",
        "stage": "db_schema",
        "message": "🗄️ Generating database schema (foundation layer)..."
    })
    
    start = time.time()
    client = _make_client()
    
    prompt = DB_PROMPT.format(
        design=state["design"].model_dump_json(indent=2),
        intent=state["intent"].model_dump_json(indent=2),
    )
    
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=DBSchema,
            temperature=TEMPERATURE,
        ),
    )
    
    db_schema: DBSchema = response.parsed
    elapsed = round(time.time() - start, 2)
    
    table_names = [t.name for t in db_schema.tables]
    events.append({
        "type": "stage_complete",
        "stage": "db_schema",
        "message": f"✅ DB schema: {len(db_schema.tables)} tables — {', '.join(table_names)}",
        "duration": elapsed,
        "data": {"tables": table_names}
    })
    
    timings = dict(state.get("stage_timings", {}))
    timings["db_schema"] = elapsed
    
    return {
        "db_schema": db_schema,
        "events": events,
        "stage_timings": timings,
        "current_stage": "db_schema",
        "cost_estimate": state.get("cost_estimate", 0.0) + 0.001,
    }


def generate_api_schema(state: PipelineState) -> dict:
    """Stage 3b: Generate API schema, given DB schema.
    
    Context: db_schema + design + intent (context isolation).
    """
    events = list(state.get("events", []))
    events.append({
        "type": "stage_start",
        "stage": "api_schema",
        "message": "🔌 Generating API endpoints..."
    })
    
    start = time.time()
    client = _make_client()
    
    prompt = API_PROMPT.format(
        db_tables=_format_db_tables(state["db_schema"]),
        design=state["design"].model_dump_json(indent=2),
        intent=state["intent"].model_dump_json(indent=2),
    )
    
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=APISchema,
            temperature=TEMPERATURE,
        ),
    )
    
    api_schema: APISchema = response.parsed
    elapsed = round(time.time() - start, 2)
    
    events.append({
        "type": "stage_complete",
        "stage": "api_schema",
        "message": f"✅ API schema: {len(api_schema.endpoints)} endpoints",
        "duration": elapsed,
        "data": {"endpoint_count": len(api_schema.endpoints)}
    })
    
    timings = dict(state.get("stage_timings", {}))
    timings["api_schema"] = elapsed
    
    return {
        "api_schema": api_schema,
        "events": events,
        "stage_timings": timings,
        "current_stage": "api_schema",
        "cost_estimate": state.get("cost_estimate", 0.0) + 0.001,
    }


def generate_auth_schema(state: PipelineState) -> dict:
    """Stage 3c: Generate Auth schema, given DB + API.
    
    Context: db_schema + api_schema + intent (context isolation).
    """
    events = list(state.get("events", []))
    events.append({
        "type": "stage_start",
        "stage": "auth_schema",
        "message": "🔐 Generating auth & permissions..."
    })
    
    start = time.time()
    client = _make_client()
    
    prompt = AUTH_PROMPT.format(
        api_endpoints=_format_api_endpoints(state["api_schema"]),
        db_tables=_format_db_tables(state["db_schema"]),
        intent=state["intent"].model_dump_json(indent=2),
    )
    
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AuthSchema,
            temperature=TEMPERATURE,
        ),
    )
    
    auth_schema: AuthSchema = response.parsed
    elapsed = round(time.time() - start, 2)
    
    role_names = [r.name for r in auth_schema.roles]
    events.append({
        "type": "stage_complete",
        "stage": "auth_schema",
        "message": f"✅ Auth schema: {len(auth_schema.roles)} roles — {', '.join(role_names)}",
        "duration": elapsed,
        "data": {"roles": role_names}
    })
    
    timings = dict(state.get("stage_timings", {}))
    timings["auth_schema"] = elapsed
    
    return {
        "auth_schema": auth_schema,
        "events": events,
        "stage_timings": timings,
        "current_stage": "auth_schema",
        "cost_estimate": state.get("cost_estimate", 0.0) + 0.001,
    }


def generate_business_schema(state: PipelineState) -> dict:
    """Stage 3d: Generate Business Logic, given DB + API + Auth.
    
    Context: db_schema + api_schema + auth_schema + intent (context isolation).
    """
    events = list(state.get("events", []))
    events.append({
        "type": "stage_start",
        "stage": "business_schema",
        "message": "⚙️ Generating business logic & rules..."
    })
    
    start = time.time()
    client = _make_client()
    
    prompt = BUSINESS_PROMPT.format(
        api_endpoints=_format_api_endpoints(state["api_schema"]),
        auth_roles=_format_auth_roles(state["auth_schema"]),
        db_tables=_format_db_tables(state["db_schema"]),
        intent=state["intent"].model_dump_json(indent=2),
    )
    
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=BusinessLogicSchema,
            temperature=TEMPERATURE,
        ),
    )
    
    biz_schema: BusinessLogicSchema = response.parsed
    elapsed = round(time.time() - start, 2)
    
    events.append({
        "type": "stage_complete",
        "stage": "business_schema",
        "message": f"✅ Business logic: {len(biz_schema.rules)} rules",
        "duration": elapsed,
        "data": {"rule_count": len(biz_schema.rules)}
    })
    
    timings = dict(state.get("stage_timings", {}))
    timings["business_schema"] = elapsed
    
    return {
        "business_schema": biz_schema,
        "events": events,
        "stage_timings": timings,
        "current_stage": "business_schema",
        "cost_estimate": state.get("cost_estimate", 0.0) + 0.001,
    }


def generate_ui_schema(state: PipelineState) -> dict:
    """Stage 3e: Generate UI schema, given EVERYTHING above.
    
    Context: all schemas + intent (context isolation).
    """
    events = list(state.get("events", []))
    events.append({
        "type": "stage_start",
        "stage": "ui_schema",
        "message": "🎨 Generating UI layout & components..."
    })
    
    start = time.time()
    client = _make_client()
    
    prompt = UI_PROMPT.format(
        api_details=_format_api_details(state["api_schema"]),
        auth_roles=_format_auth_roles(state["auth_schema"]),
        db_tables=_format_db_tables(state["db_schema"]),
        intent=state["intent"].model_dump_json(indent=2),
    )
    
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=UISchema,
            temperature=TEMPERATURE,
        ),
    )
    
    ui_schema: UISchema = response.parsed
    elapsed = round(time.time() - start, 2)
    
    page_names = [p.title for p in ui_schema.pages]
    events.append({
        "type": "stage_complete",
        "stage": "ui_schema",
        "message": f"✅ UI schema: {len(ui_schema.pages)} pages — {', '.join(page_names)}",
        "duration": elapsed,
        "data": {"pages": page_names}
    })
    
    timings = dict(state.get("stage_timings", {}))
    timings["ui_schema"] = elapsed
    
    return {
        "ui_schema": ui_schema,
        "events": events,
        "stage_timings": timings,
        "current_stage": "ui_schema",
        "cost_estimate": state.get("cost_estimate", 0.0) + 0.001,
    }
