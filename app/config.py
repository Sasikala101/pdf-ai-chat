from dataclasses import dataclass
import os

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    google_api_key: str = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY", "")
    chat_model: str = os.getenv("GEMINI_CHAT_MODEL", "gemini-3.6-flash")
    embedding_model: str = os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001")
    max_upload_bytes: int = 25 * 1024 * 1024
    chunk_size: int = 1200
    chunk_overlap: int = 180
    retrieval_count: int = 5
    session_ttl_seconds: int = 4 * 60 * 60
    max_active_sessions: int = int(os.getenv("MAX_ACTIVE_SESSIONS", "20"))
    max_questions_per_session: int = int(os.getenv("MAX_QUESTIONS_PER_SESSION", "30"))


settings = Settings()
