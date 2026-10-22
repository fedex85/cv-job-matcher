"""Configuración central. Toda la configuración sale de variables de entorno
(o de un archivo ``.env``); no hay secretos en el código."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DB_PATH = PROJECT_ROOT / "data" / "skills" / "skills_db.json"
HISTORY_DB_PATH = PROJECT_ROOT / "data" / "processed" / "history.db"


def _env_str(name: str, default: str = "") -> str:
    # Permite comentarios inline en .env.example ("VALOR   # comentario").
    return os.getenv(name, default).split("#", 1)[0].strip()


def _env_int(name: str, default: int) -> int:
    raw = _env_str(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"La variable {name} debe ser un entero (valor: {raw!r})") from exc


def _env_float(name: str, default: float) -> float:
    raw = _env_str(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"La variable {name} debe ser un número (valor: {raw!r})") from exc


def _env_bool(name: str, default: bool) -> bool:
    raw = _env_str(name).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "si", "sí", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8000
    enable_ui: bool = True
    enable_gradio: bool = False
    cors_origins: tuple[str, ...] = ()
    api_key: str = ""

    max_upload_mb: int = 5
    max_pdf_pages: int = 15
    max_text_chars: int = 60_000
    max_job_chars: int = 20_000
    rate_limit_per_minute: int = 20

    llm_enabled: bool = True
    groq_api_key: str = field(default="", repr=False)  # repr=False: nunca en logs
    groq_model: str = "llama-3.3-70b-versatile"
    groq_timeout_seconds: float = 30.0

    embedding_backend: str = "tfidf"
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"

    weight_skills: float = 0.45
    weight_semantic: float = 0.20
    weight_experience: float = 0.15
    weight_education: float = 0.10
    weight_languages: float = 0.10

    history_enabled: bool = True
    history_db_path: Path = HISTORY_DB_PATH
    history_max_entries: int = 2000

    skills_db_path: Path = SKILLS_DB_PATH

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def llm_available(self) -> bool:
        return self.llm_enabled and bool(self.groq_api_key)

    @property
    def weights(self) -> dict[str, float]:
        return {
            "skills": self.weight_skills,
            "semantic": self.weight_semantic,
            "experience": self.weight_experience,
            "education": self.weight_education,
            "languages": self.weight_languages,
        }

    def validate(self) -> None:
        """Falla pronto con mensajes claros si la configuración es incoherente."""
        if any(w < 0 for w in self.weights.values()) or sum(self.weights.values()) <= 0:
            raise ValueError("Los pesos WEIGHT_* deben ser >= 0 y sumar más de 0.")
        if self.embedding_backend not in {"tfidf", "sentence-transformers"}:
            raise ValueError("EMBEDDING_BACKEND debe ser 'tfidf' o 'sentence-transformers'.")
        if self.max_upload_mb < 1 or self.max_pdf_pages < 1:
            raise ValueError("MAX_UPLOAD_MB y MAX_PDF_PAGES deben ser >= 1.")
        if self.is_production and not self.api_key:
            raise ValueError("En producción (APP_ENV=production) debes definir API_KEY.")


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    origins = tuple(o.strip() for o in _env_str("CORS_ORIGINS").split(",") if o.strip())
    s = Settings(
        app_env=_env_str("APP_ENV", "development") or "development",
        log_level=(_env_str("LOG_LEVEL", "INFO") or "INFO").upper(),
        host=_env_str("HOST", "127.0.0.1") or "127.0.0.1",
        port=_env_int("PORT", 8000),
        enable_ui=_env_bool("ENABLE_UI", True),
        enable_gradio=_env_bool("ENABLE_GRADIO", False),
        cors_origins=origins,
        api_key=_env_str("API_KEY"),
        max_upload_mb=_env_int("MAX_UPLOAD_MB", 5),
        max_pdf_pages=_env_int("MAX_PDF_PAGES", 15),
        max_text_chars=_env_int("MAX_TEXT_CHARS", 60_000),
        max_job_chars=_env_int("MAX_JOB_CHARS", 20_000),
        rate_limit_per_minute=_env_int("RATE_LIMIT_PER_MINUTE", 20),
        llm_enabled=_env_bool("LLM_ENABLED", True),
        groq_api_key=_env_str("GROQ_API_KEY"),
        groq_model=_env_str("GROQ_MODEL", "llama-3.3-70b-versatile") or "llama-3.3-70b-versatile",
        groq_timeout_seconds=_env_float("GROQ_TIMEOUT_SECONDS", 30.0),
        embedding_backend=_env_str("EMBEDDING_BACKEND", "tfidf") or "tfidf",
        embedding_model=_env_str("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"),
        history_enabled=_env_bool("HISTORY_ENABLED", True),
        history_db_path=Path(_env_str("HISTORY_DB_PATH") or HISTORY_DB_PATH),
        history_max_entries=_env_int("HISTORY_MAX_ENTRIES", 2000),
        weight_skills=_env_float("WEIGHT_SKILLS", 0.45),
        weight_semantic=_env_float("WEIGHT_SEMANTIC", 0.20),
        weight_experience=_env_float("WEIGHT_EXPERIENCE", 0.15),
        weight_education=_env_float("WEIGHT_EDUCATION", 0.10),
        weight_languages=_env_float("WEIGHT_LANGUAGES", 0.10),
    )
    s.validate()
    return s


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
