"""Database Builder — creates real SQLite tables from DBSchema.

Generates DDL from the schema, executes it, and optionally seeds sample data.
NO eval() or exec() — uses safe SQL construction from validated schema fields only.
"""
import sqlite3
import uuid
from pathlib import Path
from src.schemas.database import DBSchema, DBTable, DBColumn


# SQLite type mapping from schema types
TYPE_MAP = {
    "uuid": "TEXT",
    "text": "TEXT",
    "varchar": "TEXT",
    "integer": "INTEGER",
    "float": "REAL",
    "boolean": "INTEGER",
    "timestamp": "TEXT",
    "jsonb": "TEXT",
    "enum": "TEXT",
}


def _column_ddl(col: DBColumn) -> str:
    """Generate DDL for a single column."""
    parts = [f'"{col.name}"', TYPE_MAP.get(col.type, "TEXT")]
    
    if col.primary_key:
        parts.append("PRIMARY KEY")
    if not col.nullable and not col.primary_key:
        parts.append("NOT NULL")
    if col.unique and not col.primary_key:
        parts.append("UNIQUE")
    if col.default is not None:
        parts.append(f"DEFAULT '{col.default}'")
    
    return " ".join(parts)


def _table_ddl(table: DBTable) -> str:
    """Generate CREATE TABLE DDL for a table."""
    col_lines = [_column_ddl(c) for c in table.columns]
    
    # Add foreign key constraints
    for col in table.columns:
        if col.foreign_key:
            parts = col.foreign_key.split(".")
            if len(parts) == 2:
                fk_table, fk_col = parts
                col_lines.append(
                    f'FOREIGN KEY ("{col.name}") REFERENCES "{fk_table}" ("{fk_col}")'
                )
    
    cols = ",\n    ".join(col_lines)
    return f'CREATE TABLE IF NOT EXISTS "{table.name}" (\n    {cols}\n);'


def _index_ddl(table: DBTable) -> list[str]:
    """Generate CREATE INDEX statements for a table."""
    stmts = []
    for idx_col in table.indexes:
        # Validate the index column exists
        col_names = {c.name for c in table.columns}
        if idx_col in col_names:
            idx_name = f"idx_{table.name}_{idx_col}"
            stmts.append(
                f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table.name}" ("{idx_col}");'
            )
    return stmts


def _generate_sample_value(col: DBColumn) -> str:
    """Generate a realistic sample value for a column."""
    if col.primary_key and col.type == "uuid":
        return str(uuid.uuid4())
    if col.type == "uuid":
        return str(uuid.uuid4())
    if col.type in ("text", "varchar"):
        return f"Sample {col.name}"
    if col.type == "integer":
        return "1"
    if col.type == "float":
        return "0.0"
    if col.type == "boolean":
        return "1"
    if col.type == "timestamp":
        return "2025-01-01T00:00:00Z"
    if col.type == "enum" and col.enum_values:
        return col.enum_values[0]
    if col.type == "jsonb":
        return "{}"
    return "sample"


def build_database(db_schema: DBSchema, db_path: Path) -> dict:
    """Build a real SQLite database from a DBSchema.
    
    Args:
        db_schema: The validated database schema
        db_path: Where to create the .db file
        
    Returns:
        Dict with tables_created, sample_data_inserted, errors
    """
    result = {
        "tables_created": [],
        "sample_data_inserted": 0,
        "errors": [],
        "ddl_statements": [],
    }
    
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()
    
    try:
        # Create tables
        for table in db_schema.tables:
            ddl = _table_ddl(table)
            result["ddl_statements"].append(ddl)
            try:
                cursor.execute(ddl)
                result["tables_created"].append(table.name)
            except sqlite3.Error as e:
                result["errors"].append(f"Error creating table '{table.name}': {str(e)}")
            
            # Create indexes
            for idx_stmt in _index_ddl(table):
                try:
                    cursor.execute(idx_stmt)
                except sqlite3.Error:
                    pass  # Non-critical
        
        conn.commit()
        
        # Seed sample data (2 rows per table)
        for table in db_schema.tables:
            if table.name not in result["tables_created"]:
                continue
                
            for _ in range(2):
                cols = []
                vals = []
                for col in table.columns:
                    val = _generate_sample_value(col)
                    cols.append(f'"{col.name}"')
                    vals.append(val)
                
                placeholders = ", ".join("?" for _ in vals)
                col_str = ", ".join(cols)
                insert = f'INSERT INTO "{table.name}" ({col_str}) VALUES ({placeholders})'
                
                try:
                    cursor.execute(insert, vals)
                    result["sample_data_inserted"] += 1
                except sqlite3.Error:
                    pass  # Sample data is best-effort
        
        conn.commit()
        
    except Exception as e:
        result["errors"].append(f"Database build error: {str(e)}")
    finally:
        conn.close()
    
    return result


def verify_database(db_path: Path, db_schema: DBSchema) -> list[dict]:
    """Smoke test: verify all tables exist and are queryable.
    
    Returns list of test results.
    """
    results = []
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        for table in db_schema.tables:
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{table.name}"')
                count = cursor.fetchone()[0]
                results.append({
                    "test_name": f"table_exists_{table.name}",
                    "passed": True,
                    "details": f"Table '{table.name}' exists with {count} rows",
                })
            except sqlite3.Error as e:
                results.append({
                    "test_name": f"table_exists_{table.name}",
                    "passed": False,
                    "details": f"Table '{table.name}' error: {str(e)}",
                })
    finally:
        conn.close()
    
    return results
