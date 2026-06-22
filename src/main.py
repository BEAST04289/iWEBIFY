"""iWebify — AI App Compiler.

Main entry point. Import the app from routes.
"""
from src.api.routes import app

if __name__ == "__main__":
    import uvicorn
    from src.config import PORT
    uvicorn.run("src.main:app", host="0.0.0.0", port=PORT, reload=True)
