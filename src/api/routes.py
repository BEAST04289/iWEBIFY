"""FastAPI routes — the complete backend API.

Endpoints:
  POST /api/generate — start a compilation
  GET  /api/stream/{session_id} — SSE event stream
  GET  /api/result/{session_id} — full result once complete
  GET  /preview/{session_id} — serve generated HTML preview
  GET  /health — health check
"""
import uuid
import json
import asyncio
import traceback
from pathlib import Path

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.config import FRONTEND_DIR, SESSIONS_DIR, PORT
from src.api import run_store
from src.pipeline.graph import pipeline


# ============================================================
# FastAPI App
# ============================================================

app = FastAPI(
    title="iWebify",
    description="AI-powered compiler for software generation",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Request/Response Models
# ============================================================

class GenerateRequest(BaseModel):
    """Request body for /api/generate."""
    prompt: str
    mode: str = "generate"  # "generate" or "patch"


class GenerateResponse(BaseModel):
    """Response for /api/generate."""
    session_id: str
    message: str


# ============================================================
# Background Task — runs the pipeline
# ============================================================

async def run_pipeline_task(session_id: str, prompt: str, mode: str) -> None:
    """Run the full compilation pipeline as a background task."""
    initial_state = {
        "user_prompt": prompt,
        "mode": mode,
        "session_id": session_id,
        "events": [],
        "stage_timings": {},
        "repair_attempts": {},
        "repair_history": [],
        "total_retries": 0,
        "cost_estimate": 0.0,
        "validation_errors": [],
        "test_results": [],
        "pipeline_failed": False,
    }
    
    try:
        # Run pipeline synchronously in a thread to avoid blocking
        import concurrent.futures
        
        def run_sync():
            last_events = []
            result = None
            for chunk in pipeline.stream(initial_state, stream_mode="values"):
                new_events = chunk.get("events", [])
                # Update store with new events
                if len(new_events) > len(last_events):
                    run_store.add_events(session_id, new_events)
                    last_events = new_events
                result = chunk
            return result
        
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            final_state = await loop.run_in_executor(pool, run_sync)
        
        if final_state:
            # Serialize the final result
            result = {
                "intent": final_state.get("intent", {}).model_dump() if hasattr(final_state.get("intent", {}), "model_dump") else {},
                "design": final_state.get("design", {}).model_dump() if hasattr(final_state.get("design", {}), "model_dump") else {},
                "db_schema": final_state.get("db_schema", {}).model_dump() if hasattr(final_state.get("db_schema", {}), "model_dump") else {},
                "api_schema": final_state.get("api_schema", {}).model_dump() if hasattr(final_state.get("api_schema", {}), "model_dump") else {},
                "auth_schema": final_state.get("auth_schema", {}).model_dump() if hasattr(final_state.get("auth_schema", {}), "model_dump") else {},
                "business_schema": final_state.get("business_schema", {}).model_dump() if hasattr(final_state.get("business_schema", {}), "model_dump") else {},
                "ui_schema": final_state.get("ui_schema", {}).model_dump() if hasattr(final_state.get("ui_schema", {}), "model_dump") else {},
                "execution_result": final_state.get("execution_result", {}),
                "test_results": final_state.get("test_results", []),
                "stage_timings": final_state.get("stage_timings", {}),
                "total_retries": final_state.get("total_retries", 0),
                "cost_estimate": final_state.get("cost_estimate", 0.0),
                "validation_errors": final_state.get("validation_errors", []),
                "repair_history": final_state.get("repair_history", []),
            }
            run_store.complete_session(session_id, result)
        else:
            run_store.fail_session(session_id, "Pipeline returned no result")
            
    except Exception as e:
        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        run_store.fail_session(session_id, error_msg)
        # Also add error event
        session = run_store.get_session(session_id)
        if session:
            session["events"].append({
                "type": "pipeline_error",
                "stage": "pipeline",
                "message": f"❌ Pipeline error: {str(e)[:200]}",
            })


# ============================================================
# Routes
# ============================================================

@app.post("/api/generate", response_model=GenerateResponse)
async def generate(body: GenerateRequest, background_tasks: BackgroundTasks):
    """Start a new compilation pipeline."""
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    
    session_id = str(uuid.uuid4())
    run_store.create_session(session_id)
    
    background_tasks.add_task(run_pipeline_task, session_id, body.prompt, body.mode)
    
    return GenerateResponse(
        session_id=session_id,
        message="Compilation started",
    )


@app.get("/api/stream/{session_id}")
async def stream(session_id: str, request: Request):
    """SSE event stream for pipeline progress."""
    session = run_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    async def event_generator():
        last_index = 0
        
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break
            
            session = run_store.get_session(session_id)
            if not session:
                break
            
            events = session["events"]
            
            # Send new events
            while last_index < len(events):
                event = events[last_index]
                yield {
                    "event": event.get("type", "message"),
                    "data": json.dumps(event),
                }
                last_index += 1
            
            # Check if pipeline is done
            if session["status"] in ("complete", "error"):
                # Send final status
                yield {
                    "event": "pipeline_status",
                    "data": json.dumps({
                        "status": session["status"],
                        "error": session.get("error"),
                    }),
                }
                break
            
            await asyncio.sleep(0.3)
    
    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/result/{session_id}")
async def result(session_id: str):
    """Get full pipeline result once complete."""
    session = run_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session["status"] == "running":
        return JSONResponse(
            content={"status": "running", "message": "Pipeline still running"},
            status_code=202,
        )
    
    if session["status"] == "error":
        return JSONResponse(
            content={"status": "error", "error": session["error"]},
            status_code=500,
        )
    
    return JSONResponse(content={
        "status": "complete",
        "result": session["result"],
    })


@app.get("/preview/{session_id}")
async def preview(session_id: str):
    """Serve the generated HTML preview."""
    preview_path = SESSIONS_DIR / session_id / "preview.html"
    if not preview_path.exists():
        return HTMLResponse(
            "<html><body style='background:#09090b;color:#fafafa;font-family:Inter,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh'>"
            "<div style='text-align:center'><h2>⏳ Preview not ready yet</h2><p style='color:#a1a1aa'>The pipeline is still running...</p></div>"
            "</body></html>",
            status_code=202,
        )
    return HTMLResponse(preview_path.read_text(encoding="utf-8"))


@app.get("/api/download/{session_id}")
async def download_schemas(session_id: str):
    """Download the generated schemas as JSON."""
    schemas_path = SESSIONS_DIR / session_id / "schemas.json"
    if not schemas_path.exists():
        raise HTTPException(status_code=404, detail="Schemas not found")
    return FileResponse(
        str(schemas_path),
        media_type="application/json",
        filename=f"iwebify_{session_id[:8]}_schemas.json",
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "iwebify"}


# ============================================================
# Static files + frontend fallback
# ============================================================

# Mount frontend static files
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def serve_frontend():
    """Serve the main frontend page."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>iWebify — Frontend not built yet</h1>")
