"""iWebify Schema Contracts — re-exports all Pydantic models."""

from src.schemas.intent import IntentIR, Feature, UserRole
from src.schemas.design import SystemDesign, EntityRelation, DataFlow
from src.schemas.database import DBSchema, DBTable, DBColumn
from src.schemas.api import APISchema, APIEndpoint, APIField
from src.schemas.auth import AuthSchema, Role, Permission
from src.schemas.business import BusinessLogicSchema, BusinessRule
from src.schemas.ui import UISchema, UIPage, UIComponent

__all__ = [
    # Intent
    "IntentIR", "Feature", "UserRole",
    # Design
    "SystemDesign", "EntityRelation", "DataFlow",
    # Database
    "DBSchema", "DBTable", "DBColumn",
    # API
    "APISchema", "APIEndpoint", "APIField",
    # Auth
    "AuthSchema", "Role", "Permission",
    # Business
    "BusinessLogicSchema", "BusinessRule",
    # UI
    "UISchema", "UIPage", "UIComponent",
]
