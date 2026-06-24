from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    OPENROUTER_API_KEY: str
    MODEL_NAME: str = "google/gemini-2.0-flash-exp:free"
    REPAIR_MODEL: str = "google/gemini-2.0-flash-exp:free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    MAX_REPAIR_ATTEMPTS: int = 3
    SESSIONS_DIR: str = "/tmp/iwebify_sessions"

    class Config:
        env_file = ".env"

settings = Settings()

BASE_DIR = Path(__file__).parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
SESSIONS_DIR = Path(settings.SESSIONS_DIR)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
PORT = 7860
MAX_REPAIR_ATTEMPTS = settings.MAX_REPAIR_ATTEMPTS
