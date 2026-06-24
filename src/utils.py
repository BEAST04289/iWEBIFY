import re

def clean_json(raw: str) -> str:
    """Strip markdown code fences that some LLM providers wrap around JSON."""
    raw = raw.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```\s*$', '', raw)
    return raw.strip()

DB_TO_API_TYPE = {
    "timestamp": "string",
    "varchar": "string",
    "text": "string",
    "jsonb": "object",
    "enum": "string",
    "uuid": "uuid",
    "integer": "integer",
    "float": "float",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
    "string": "string",
}

VALID_API_TYPES = {"string", "integer", "float", "boolean", "uuid", "array", "object"}

def coerce_api_types(data: dict) -> dict:
    """Coerce DB-style types to valid APIField types in a parsed APISchema dict."""
    import copy
    data = copy.deepcopy(data)
    for endpoint in data.get("endpoints", []):
        for field_list_key in ("response_fields", "request_body"):
            field_list = endpoint.get(field_list_key) or []
            for field in field_list:
                if isinstance(field, dict):
                    t = field.get("type", "string")
                    field["type"] = DB_TO_API_TYPE.get(t, "string")
    return data
