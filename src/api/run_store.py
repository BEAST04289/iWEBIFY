"""In-memory run store for pipeline state.

In production this would be Redis. For the demo, a simple dict suffices.
Each session_id maps to its events, status, and final result.
"""
from typing import Any

# In-memory store: session_id -> session data
store: dict[str, dict[str, Any]] = {}


def create_session(session_id: str) -> None:
    """Initialize a new session in the store."""
    store[session_id] = {
        "events": [],
        "status": "running",
        "result": None,
        "error": None,
    }


def get_session(session_id: str) -> dict | None:
    """Get session data by ID."""
    return store.get(session_id)


def add_events(session_id: str, events: list[dict]) -> None:
    """Append new events to a session."""
    session = store.get(session_id)
    if session:
        stored = session["events"]
        # Only add truly new events
        for event in events[len(stored):]:
            stored.append(event)


def complete_session(session_id: str, result: dict) -> None:
    """Mark a session as complete with its final result."""
    session = store.get(session_id)
    if session:
        session["status"] = "complete"
        session["result"] = result


def fail_session(session_id: str, error: str) -> None:
    """Mark a session as failed."""
    session = store.get(session_id)
    if session:
        session["status"] = "error"
        session["error"] = error
