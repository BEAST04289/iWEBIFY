"""Database schema — output of Stage 3a. THE FOUNDATION LAYER.

Generated FIRST in the sequential dependency chain.
All other schemas build on this. DB schema is NEVER modified by repair —
it is the single source of truth.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal


class DBColumn(BaseModel):
    """A single database column."""
    name: str = Field(description="snake_case column name")
    type: Literal[
        "uuid", "text", "varchar", "integer", "float", 
        "boolean", "timestamp", "jsonb", "enum"
    ] = Field(description="Column data type")
    nullable: bool = Field(default=False, description="Whether NULL is allowed")
    unique: bool = Field(default=False, description="Whether values must be unique")
    primary_key: bool = Field(default=False, description="Whether this is the primary key")
    foreign_key: str | None = Field(
        default=None,
        description="References as 'table_name.column_name' e.g. 'users.id'"
    )
    default: str | None = Field(default=None, description="Default value as string")
    enum_values: list[str] | None = Field(
        default=None, description="Allowed values when type is 'enum'"
    )


class DBTable(BaseModel):
    """A database table with its columns and indexes."""
    name: str = Field(description="snake_case plural table name e.g. 'contacts'")
    columns: list[DBColumn] = Field(description="All columns in this table")
    indexes: list[str] = Field(
        default_factory=list,
        description="Column names to index for query performance"
    )


class DBSchema(BaseModel):
    """Database schema — output of Stage 3a. FOUNDATION — never modified by repair.
    
    Every entity from the SystemDesign must have a corresponding table.
    Use TEXT for UUIDs in SQLite. Add created_at/updated_at to every table.
    Foreign keys must reference real tables.
    """
    tables: list[DBTable] = Field(description="All database tables")
    confidence_scores: dict[str, str] = Field(
        default_factory=dict,
        description="Per-table confidence: table_name -> 'high'|'medium'|'low'"
    )
