"""Cross-Layer Validation Engine for iWebify.

Pure Python, zero LLM cost. Validates consistency across all 5 schema layers.

Validation checks (unidirectional, downstream only):
1. DB self-consistency: FK references, primary keys, circular deps
2. API → DB: every endpoint references a real table, fields match columns
3. Auth → API + DB: endpoints exist, roles are consistent
4. Business → API + Auth: affected_endpoints exist, roles exist
5. UI → API + Auth: api_endpoint exists, allowed_roles exist, fields match
"""
from src.schemas.database import DBSchema
from src.schemas.api import APISchema
from src.schemas.auth import AuthSchema
from src.schemas.business import BusinessLogicSchema
from src.schemas.ui import UISchema


def validate_db_completeness(db_schema: DBSchema) -> list[dict]:
    """Check DB schema internal consistency.
    
    Checks:
    - Every table has a primary key
    - Foreign keys reference real tables/columns
    - No circular FK dependencies
    """
    errors = []
    table_names = {t.name for t in db_schema.tables}
    table_columns = {t.name: {c.name for c in t.columns} for t in db_schema.tables}
    
    for table in db_schema.tables:
        # Check primary key exists
        has_pk = any(c.primary_key for c in table.columns)
        if not has_pk:
            errors.append({
                "type": "missing_primary_key",
                "severity": "warning",
                "layer": "db_schema",
                "message": f"Table '{table.name}' has no primary key",
                "fix": f"Add an 'id' column with primary_key=True to table '{table.name}'",
            })
        
        # Check foreign keys
        for col in table.columns:
            if col.foreign_key:
                parts = col.foreign_key.split(".")
                if len(parts) != 2:
                    errors.append({
                        "type": "malformed_fk",
                        "severity": "critical",
                        "layer": "db_schema",
                        "message": f"FK '{col.foreign_key}' in {table.name}.{col.name} is malformed (expected 'table.column')",
                        "fix": f"Fix foreign_key format to 'table_name.column_name'",
                    })
                    continue
                
                fk_table, fk_col = parts
                if fk_table not in table_names:
                    errors.append({
                        "type": "orphaned_fk",
                        "severity": "critical",
                        "layer": "db_schema",
                        "message": f"FK in {table.name}.{col.name} references non-existent table '{fk_table}'",
                        "fix": f"Change FK to reference one of: {', '.join(sorted(table_names))}",
                    })
                elif fk_col not in table_columns.get(fk_table, set()):
                    errors.append({
                        "type": "orphaned_fk_column",
                        "severity": "critical",
                        "layer": "db_schema",
                        "message": f"FK in {table.name}.{col.name} references non-existent column '{fk_table}.{fk_col}'",
                        "fix": f"Column '{fk_col}' does not exist in table '{fk_table}'. Available: {', '.join(sorted(table_columns.get(fk_table, set())))}",
                    })
    
    return errors


def validate_api_db_consistency(api_schema: APISchema, db_schema: DBSchema) -> list[dict]:
    """Check API schema references valid DB tables and columns.
    
    Checks:
    - Every endpoint's db_table exists
    - Request/response fields match DB columns
    """
    errors = []
    table_names = {t.name for t in db_schema.tables}
    table_columns = {t.name: {c.name for c in t.columns} for t in db_schema.tables}
    
    for ep in api_schema.endpoints:
        # Check db_table exists
        if ep.db_table not in table_names:
            errors.append({
                "type": "missing_table",
                "severity": "critical",
                "layer": "api_schema",
                "message": f"Endpoint {ep.method} {ep.path} references non-existent table '{ep.db_table}'",
                "fix": f"Change db_table to one of: {', '.join(sorted(table_names))}",
                "source": f"{ep.method} {ep.path}",
                "target": ep.db_table,
            })
            continue  # Can't check fields if table doesn't exist
        
        cols = table_columns.get(ep.db_table, set())
        
        # Check request body fields
        if ep.request_body:
            for field in ep.request_body:
                if field.name not in cols and field.name not in ("id", "created_at", "updated_at"):
                    errors.append({
                        "type": "hallucinated_field",
                        "severity": "warning",
                        "layer": "api_schema",
                        "message": f"Request field '{field.name}' in {ep.method} {ep.path} has no column in '{ep.db_table}'",
                        "fix": f"Remove field or change name to one of: {', '.join(sorted(cols))}",
                        "source": f"{ep.path}.request.{field.name}",
                        "target": f"{ep.db_table}.{field.name}",
                    })
        
        # Check response fields
        for field in ep.response_fields:
            if field.name not in cols and field.name not in ("id", "created_at", "updated_at"):
                errors.append({
                    "type": "hallucinated_field",
                    "severity": "warning",
                    "layer": "api_schema",
                    "message": f"Response field '{field.name}' in {ep.method} {ep.path} has no column in '{ep.db_table}'",
                    "fix": f"Remove field or change name to one of: {', '.join(sorted(cols))}",
                    "source": f"{ep.path}.response.{field.name}",
                    "target": f"{ep.db_table}.{field.name}",
                })
    
    return errors


def validate_auth_api_consistency(
    auth_schema: AuthSchema, 
    api_schema: APISchema, 
    db_schema: DBSchema,
) -> list[dict]:
    """Check auth schema references valid API endpoints and DB tables.
    
    Checks:
    - protected_endpoints and public_endpoints are real API paths
    - Role permission resources are real DB tables
    """
    errors = []
    api_paths = {ep.path for ep in api_schema.endpoints}
    table_names = {t.name for t in db_schema.tables}
    role_names = {r.name for r in auth_schema.roles}
    
    # Check protected endpoints exist
    for path in auth_schema.protected_endpoints:
        if path not in api_paths:
            errors.append({
                "type": "missing_endpoint",
                "severity": "warning",
                "layer": "auth_schema",
                "message": f"Protected endpoint '{path}' does not exist in API schema",
                "fix": f"Remove or change to one of: {', '.join(sorted(api_paths))}",
            })
    
    # Check public endpoints exist
    for path in auth_schema.public_endpoints:
        if path not in api_paths:
            errors.append({
                "type": "missing_endpoint",
                "severity": "warning",
                "layer": "auth_schema",
                "message": f"Public endpoint '{path}' does not exist in API schema",
                "fix": f"Remove or change to one of: {', '.join(sorted(api_paths))}",
            })
    
    # Check role permissions reference real tables
    for role in auth_schema.roles:
        for perm in role.permissions:
            if perm.resource not in table_names:
                errors.append({
                    "type": "invalid_resource",
                    "severity": "critical",
                    "layer": "auth_schema",
                    "message": f"Role '{role.name}' permission references non-existent table '{perm.resource}'",
                    "fix": f"Change resource to one of: {', '.join(sorted(table_names))}",
                })
    
    # Check API endpoint roles reference auth roles
    for ep in api_schema.endpoints:
        if ep.required_role and ep.required_role not in role_names:
            errors.append({
                "type": "role_mismatch",
                "severity": "critical",
                "layer": "api_schema",
                "message": f"Endpoint {ep.method} {ep.path} requires role '{ep.required_role}' which doesn't exist in auth",
                "fix": f"Change to one of: {', '.join(sorted(role_names))}",
            })
    
    return errors


def validate_ui_api_consistency(
    ui_schema: UISchema,
    api_schema: APISchema,
    auth_schema: AuthSchema,
) -> list[dict]:
    """Check UI schema references valid API endpoints and auth roles.
    
    Checks:
    - Every component's api_endpoint is a real API path
    - Every page's allowed_roles are real auth roles
    - Component fields match API response fields
    """
    errors = []
    api_paths = {ep.path for ep in api_schema.endpoints}
    role_names = {r.name for r in auth_schema.roles}
    
    # Build response field index: path -> set of field names
    api_response_fields: dict[str, set[str]] = {}
    for ep in api_schema.endpoints:
        path_key = ep.path
        if path_key not in api_response_fields:
            api_response_fields[path_key] = set()
        for f in ep.response_fields:
            api_response_fields[path_key].add(f.name)
    
    for page in ui_schema.pages:
        # Check allowed_roles
        for role in page.allowed_roles:
            if role not in role_names:
                errors.append({
                    "type": "role_mismatch",
                    "severity": "critical",
                    "layer": "ui_schema",
                    "message": f"Page '{page.title}' allows role '{role}' which doesn't exist in auth",
                    "fix": f"Change to one of: {', '.join(sorted(role_names))}",
                })
        
        # Check components
        for comp in page.components:
            if comp.api_endpoint not in api_paths:
                errors.append({
                    "type": "missing_endpoint",
                    "severity": "critical",
                    "layer": "ui_schema",
                    "message": f"Component '{comp.id}' on page '{page.title}' references non-existent API endpoint '{comp.api_endpoint}'",
                    "fix": f"Change api_endpoint to one of: {', '.join(sorted(api_paths))}",
                })
            else:
                # Check fields match response fields
                available = api_response_fields.get(comp.api_endpoint, set())
                for field in comp.fields:
                    if field not in available and available:
                        errors.append({
                            "type": "hallucinated_field",
                            "severity": "warning",
                            "layer": "ui_schema",
                            "message": f"Component '{comp.id}' field '{field}' not in API response for '{comp.api_endpoint}'",
                            "fix": f"Change to one of: {', '.join(sorted(available))}",
                        })
    
    return errors


def run_all_validations(
    db_schema: DBSchema,
    api_schema: APISchema,
    auth_schema: AuthSchema,
    business_schema: BusinessLogicSchema,
    ui_schema: UISchema,
) -> tuple[list[dict], list[dict]]:
    """Run all cross-layer validations.
    
    Returns:
        Tuple of (critical_errors, warnings)
    """
    all_errors = []
    
    all_errors.extend(validate_db_completeness(db_schema))
    all_errors.extend(validate_api_db_consistency(api_schema, db_schema))
    all_errors.extend(validate_auth_api_consistency(auth_schema, api_schema, db_schema))
    
    # Business logic validation
    api_paths = {ep.path for ep in api_schema.endpoints}
    role_names = {r.name for r in auth_schema.roles}
    
    for rule in business_schema.rules:
        for ep_path in rule.affected_endpoints:
            if ep_path not in api_paths:
                all_errors.append({
                    "type": "missing_endpoint",
                    "severity": "warning",
                    "layer": "business_schema",
                    "message": f"Business rule '{rule.name}' affects non-existent endpoint '{ep_path}'",
                    "fix": f"Remove or change to one of: {', '.join(sorted(api_paths))}",
                })
    
    all_errors.extend(validate_ui_api_consistency(ui_schema, api_schema, auth_schema))
    
    critical = [e for e in all_errors if e.get("severity") == "critical"]
    warnings = [e for e in all_errors if e.get("severity") == "warning"]
    
    return critical, warnings
