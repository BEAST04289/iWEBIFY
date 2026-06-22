"""iWebify configuration — loads from environment variables."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
SESSIONS_DIR = Path(os.getenv("SESSIONS_DIR", "/tmp/iwebify_sessions"))

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.0-flash")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
REPAIR_TEMPERATURE = float(os.getenv("REPAIR_TEMPERATURE", "0.0"))

# Pipeline
MAX_REPAIR_ATTEMPTS = int(os.getenv("MAX_REPAIR_ATTEMPTS", "3"))

# Server
SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "5"))
PORT = int(os.getenv("PORT", "7860"))

# Ensure sessions directory exists
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
