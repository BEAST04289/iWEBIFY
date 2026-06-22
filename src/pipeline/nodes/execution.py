"""Stage 5: Execution Node.

Creates a real running application from the validated schemas:
1. Creates session directory
2. Builds SQLite database with real tables and sample data
3. Runs smoke tests to verify tables
4. Generates HTML preview
"""
import time
from pathlib import Path
from src.config import SESSIONS_DIR
from src.pipeline.state import PipelineState
from src.execution.db_builder import build_database, verify_database
from src.execution.preview_builder import build_preview


def execution(state: PipelineState) -> dict:
    """Execute the compiled schemas into a real application.
    
    Creates SQLite DB, seeds data, generates HTML preview.
    """
    events = list(state.get("events", []))
    events.append({
        "type": "stage_start",
        "stage": "execution",
        "message": "🚀 Building application..."
    })
    
    start = time.time()
    session_id = state["session_id"]
    session_dir = SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    
    db_path = session_dir / "app.db"
    preview_path = session_dir / "preview.html"
    
    errors = []
    
    # Step 1: Build database
    events.append({
        "type": "execution_step",
        "stage": "execution",
        "message": "📦 Creating SQLite database..."
    })
    
    db_result = build_database(state["db_schema"], db_path)
    
    events.append({
        "type": "execution_step",
        "stage": "execution",
        "message": f"✅ Database created: {len(db_result['tables_created'])} tables, "
                   f"{db_result['sample_data_inserted']} sample rows",
    })
    
    if db_result["errors"]:
        errors.extend(db_result["errors"])
        events.append({
            "type": "execution_step",
            "stage": "execution",
            "message": f"⚠️ DB warnings: {'; '.join(db_result['errors'][:3])}",
        })
    
    # Step 2: Smoke tests
    events.append({
        "type": "execution_step",
        "stage": "execution",
        "message": "🔍 Running smoke tests..."
    })
    
    test_results = verify_database(db_path, state["db_schema"])
    passed = sum(1 for t in test_results if t["passed"])
    total = len(test_results)
    
    events.append({
        "type": "execution_step",
        "stage": "execution",
        "message": f"{'✅' if passed == total else '⚠️'} Smoke tests: {passed}/{total} passed",
    })
    
    # Step 3: Generate preview
    events.append({
        "type": "execution_step",
        "stage": "execution",
        "message": "🎨 Generating application preview..."
    })
    
    try:
        build_preview(
            db_schema=state["db_schema"],
            api_schema=state["api_schema"],
            auth_schema=state["auth_schema"],
            ui_schema=state["ui_schema"],
            db_path=db_path,
            output_path=preview_path,
        )
        events.append({
            "type": "execution_step",
            "stage": "execution",
            "message": "✅ Preview generated successfully",
        })
    except Exception as e:
        errors.append(f"Preview generation error: {str(e)}")
        events.append({
            "type": "execution_step",
            "stage": "execution",
            "message": f"⚠️ Preview generation failed: {str(e)[:100]}",
        })
    
    # Save schemas as JSON for download/inspection
    schemas_path = session_dir / "schemas.json"
    import json
    schemas_dump = {
        "intent": state["intent"].model_dump(),
        "design": state["design"].model_dump(),
        "db_schema": state["db_schema"].model_dump(),
        "api_schema": state["api_schema"].model_dump(),
        "auth_schema": state["auth_schema"].model_dump(),
        "business_schema": state["business_schema"].model_dump(),
        "ui_schema": state["ui_schema"].model_dump(),
    }
    schemas_path.write_text(json.dumps(schemas_dump, indent=2, default=str))
    
    elapsed = round(time.time() - start, 2)
    
    execution_result = {
        "success": len(errors) == 0,
        "db_tables_created": db_result["tables_created"],
        "sample_data_rows": db_result["sample_data_inserted"],
        "preview_url": f"/preview/{session_id}",
        "errors": errors,
    }
    
    events.append({
        "type": "stage_complete",
        "stage": "execution",
        "message": f"{'✅' if not errors else '⚠️'} Execution complete in {elapsed}s — "
                   f"{len(db_result['tables_created'])} tables, preview at /preview/{session_id}",
        "duration": elapsed,
        "data": execution_result,
    })
    
    # Final done event
    total_time = sum(state.get("stage_timings", {}).values()) + elapsed
    events.append({
        "type": "done",
        "stage": "done",
        "message": f"🎉 Compilation complete! Total time: {round(total_time, 1)}s",
        "data": {
            "total_time": round(total_time, 1),
            "total_retries": state.get("total_retries", 0),
            "preview_url": f"/preview/{session_id}",
        }
    })
    
    timings = dict(state.get("stage_timings", {}))
    timings["execution"] = elapsed
    
    return {
        "execution_result": execution_result,
        "test_results": test_results,
        "events": events,
        "stage_timings": timings,
        "current_stage": "execution",
    }
