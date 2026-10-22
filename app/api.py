"""API REST (FastAPI) de CV Matcher."""

from __future__ import annotations

import hmac
import inspect
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.config import Settings, get_settings
from src.ingestion import IngestionError, load_document
from src.llm import TASKS
from src.pipeline import AnalysisPipeline
from src.utils.logger import get_logger, setup_logging

from .schemas import AnalysisResponse, AssistResponse, CVExtraction, ErrorResponse, HistoryItem, SkillItem

log = get_logger(__name__)
MIN_JOB_CHARS = 40
STATIC_DIR = Path(__file__).parent / "static"
# La interfaz solo carga recursos propios; sin scripts ni estilos en línea, sin CDNs.
UI_CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
          "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
ERRORS = {400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}, 413: {"model": ErrorResponse},
          415: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 429: {"model": ErrorResponse}}


class RateLimiter:
    """Ventana deslizante de 60 s por IP, en memoria (suficiente para una sola instancia)."""

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        if self.per_minute <= 0:
            return True
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_minute:
            return False
        q.append(now)
        if len(self._hits) > 10_000:  # evita crecimiento sin límite
            for k in [k for k, v in self._hits.items() if not v or now - v[-1] > 60]:
                del self._hits[k]
        return True


def _error(status: int, code: str, message: str, request: Request | None = None) -> JSONResponse:
    rid = getattr(request.state, "request_id", None) if request else None
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message,
                                                               "request_id": rid}})


def _flag(value: str | None, default: bool = True) -> bool:
    """Interpreta un campo de formulario booleano. Se hace a mano porque, en multipart,
    FastAPI toma un booleano ausente como False en lugar de usar su valor por defecto."""
    if value is None or not value.strip():
        return default
    return value.strip().lower() not in {"false", "0", "no", "off", "n"}


async def _read_upload(file: UploadFile, limit: int) -> bytes:
    data = await file.read(limit + 1)  # lectura acotada: nunca más de limit+1 bytes en memoria
    await file.close()
    return data


def create_app(settings: Settings | None = None, pipeline: AnalysisPipeline | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)
    pipeline = pipeline or AnalysisPipeline(settings)
    limiter = RateLimiter(settings.rate_limit_per_minute)
    app = FastAPI(
        title="CV Matcher API",
        version="1.0.0",
        description="Compara un CV con una oferta de empleo y devuelve una puntuación explicable.",
    )
    app.state.settings = settings
    app.state.pipeline = pipeline

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
            allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-API-Key"],
        )

    max_body = settings.max_upload_bytes * 2 + settings.max_job_chars * 4 + 1_000_000

    @app.middleware("http")
    async def guard(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex[:12]
        path = request.url.path
        if path.startswith("/api/"):
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > max_body:
                return _error(413, "payload_too_large", "La petición es demasiado grande.", request)
            if request.method == "POST":
                client = request.client.host if request.client else "unknown"
                if not limiter.allow(client):
                    resp = _error(429, "rate_limited", "Demasiadas peticiones; espera un minuto.", request)
                    resp.headers["Retry-After"] = "60"
                    return resp
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if path == "/app" or path.startswith("/app/"):
            response.headers["Cache-Control"] = "no-cache"
            response.headers["Content-Security-Policy"] = UI_CSP
            response.headers["X-Frame-Options"] = "DENY"
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Content-Security-Policy"] = "default-src 'none'"
            response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.exception_handler(IngestionError)
    async def _ingestion_error(request: Request, exc: IngestionError):
        return _error(exc.status_code, exc.code, exc.message, request)

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, exc: HTTPException):
        return _error(exc.status_code, "http_error", str(exc.detail), request)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        fields = ", ".join(sorted({str(e["loc"][-1]) for e in exc.errors()}))
        return _error(422, "validation_error", f"Datos de entrada no válidos: {fields}.", request)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        log.exception("Error no controlado [%s]", getattr(request.state, "request_id", "-"))
        return _error(500, "internal_error", "Error interno. Inténtalo de nuevo más tarde.", request)

    def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
        if settings.api_key and not (x_api_key and hmac.compare_digest(x_api_key, settings.api_key)):
            raise HTTPException(status_code=401, detail="API key ausente o incorrecta.")

    async def read_inputs(cv_file: UploadFile, job_text: str | None, job_file: UploadFile | None) -> tuple[str, str]:
        """Lee y valida el CV y la oferta (texto pegado o archivo)."""
        cv_bytes = await _read_upload(cv_file, settings.max_upload_bytes)
        cv_doc = await run_in_threadpool(load_document, cv_file.filename, cv_bytes, settings)
        if job_file is not None and job_file.filename:
            job_bytes = await _read_upload(job_file, settings.max_upload_bytes)
            job = (await run_in_threadpool(load_document, job_file.filename, job_bytes, settings)).text
        else:
            job = (job_text or "").strip()
        if not job:
            raise IngestionError("job_missing", "Indica la oferta: pega el texto o sube un archivo.", 422)
        if len(job) > settings.max_job_chars:
            raise IngestionError("job_too_long",
                                 f"La oferta supera los {settings.max_job_chars} caracteres.", 413)
        if len(job) < MIN_JOB_CHARS:
            raise IngestionError("job_too_short", "La oferta es demasiado corta para analizarla.", 422)
        return cv_doc.text, job

    # ------------------------------------------------------------------ rutas
    @app.get("/health", tags=["sistema"])
    def health() -> dict:
        return {"status": "ok", "llm": settings.llm_available,
                "similarity_backend": pipeline.backend.name, "version": app.version,
                "auth_required": bool(settings.api_key), "weights": settings.weights}

    @app.post("/api/v1/analyze", response_model=AnalysisResponse, responses=ERRORS, tags=["análisis"],
              dependencies=[Depends(require_api_key)], summary="Compara un CV con una oferta")
    async def analyze(
        cv_file: UploadFile = File(..., description="CV en PDF, DOCX o TXT"),
        job_text: str | None = Form(None, description="Texto de la oferta"),
        job_file: UploadFile | None = File(None, description="Oferta en PDF, DOCX o TXT (alternativa a job_text)"),
        use_llm: str | None = Form(None, description="true/false (por defecto true): usar Groq para el resumen"),
        remember_job: str | None = Form(None, description="true/false (por defecto true): guardar la oferta en el historial"),
    ) -> dict:
        cv_text, job = await read_inputs(cv_file, job_text, job_file)
        return await run_in_threadpool(pipeline.analyze, cv_text, job,
                                       _flag(use_llm), _flag(remember_job))

    @app.post("/api/v1/assist", response_model=AssistResponse, responses=ERRORS, tags=["IA"],
              dependencies=[Depends(require_api_key)],
              summary="Asistente de IA: logros, resumen, carta y preguntas de entrevista")
    async def assist(
        cv_file: UploadFile = File(..., description="CV en PDF, DOCX o TXT"),
        job_text: str | None = Form(None),
        job_file: UploadFile | None = File(None),
        tasks: str | None = Form(None, description="Lista separada por comas: rewrite, summary, cover, interview (por defecto, todas)"),
        consent: str | None = Form(None, description="Debe ser 'true': el texto del CV y de la oferta se envía a Groq"),
    ) -> dict:
        if not _flag(consent, default=False):
            raise IngestionError("consent_required", "Esta función envía el texto de tu CV y de la oferta a Groq. "
                                 "Confirma el consentimiento para continuar.", 400)
        if pipeline.assistant is None:
            raise IngestionError("llm_unavailable", "La IA no está configurada: define GROQ_API_KEY en .env.", 503)
        wanted = [x.strip() for x in (tasks or "").split(",") if x.strip()] or list(TASKS)
        bad = [x for x in wanted if x not in TASKS]
        if bad:
            raise IngestionError("bad_task", f"Tarea desconocida: {bad[0]}. Opciones: {', '.join(TASKS)}.", 422)
        cv_text, job = await read_inputs(cv_file, job_text, job_file)
        return await run_in_threadpool(pipeline.assist, cv_text, job, list(dict.fromkeys(wanted)))

    @app.post("/api/v1/cv/extract", response_model=CVExtraction, responses=ERRORS, tags=["análisis"],
              dependencies=[Depends(require_api_key)], summary="Extrae el perfil de un CV")
    async def extract_cv(cv_file: UploadFile = File(...)) -> dict:
        data = await _read_upload(cv_file, settings.max_upload_bytes)
        doc = await run_in_threadpool(load_document, cv_file.filename, data, settings)
        return await run_in_threadpool(pipeline.extract_cv, doc.text)

    @app.get("/api/v1/skills", response_model=list[SkillItem], tags=["datos"],
             dependencies=[Depends(require_api_key)], summary="Busca en el diccionario de habilidades")
    def skills(q: str = "", limit: int = 25) -> list[SkillItem]:
        limit = max(1, min(limit, 200))
        found = pipeline.skills.search(q, limit) if q.strip() else \
            sorted(pipeline.skills.skills.values(), key=lambda s: s.name.lower())[:limit]
        return [SkillItem(name=s.name, category=s.category, family=s.family) for s in found]

    @app.get("/api/v1/history", response_model=list[HistoryItem], tags=["historial"],
             dependencies=[Depends(require_api_key)], summary="Ofertas ya analizadas")
    def history_list(limit: int = 200) -> list[dict]:
        return pipeline.history.list(max(1, min(limit, 1000)))

    @app.delete("/api/v1/history/{job_id}", tags=["historial"], dependencies=[Depends(require_api_key)],
                summary="Olvida una oferta del historial")
    def history_delete(job_id: str) -> dict:
        if not pipeline.history.delete(job_id):
            raise HTTPException(status_code=404, detail="Oferta no encontrada en el historial.")
        return {"deleted": 1}

    @app.delete("/api/v1/history", tags=["historial"], dependencies=[Depends(require_api_key)],
                summary="Vacía el historial de ofertas")
    def history_clear() -> dict:
        return {"deleted": pipeline.history.clear()}

    ui_enabled = settings.enable_ui and STATIC_DIR.is_dir()
    if ui_enabled:
        app.mount("/app", StaticFiles(directory=STATIC_DIR, html=True), name="ui")
        if settings.is_production and not settings.api_key:
            log.warning("La interfaz /app no tiene API_KEY: en producción ponla tras autenticación.")

    if settings.enable_gradio:  # interfaz antigua, opcional (requiere `pip install gradio`)
        try:
            import gradio as gr

            from .gradio_app import build_ui

            ui = build_ui(pipeline, settings)
            accepted = inspect.signature(gr.mount_gradio_app).parameters
            extra = {k: v for k, v in getattr(ui, "cvm_mount_kwargs", {}).items() if k in accepted}
            app = gr.mount_gradio_app(app, ui, path="/ui", **extra)
        except ImportError:
            log.warning("Gradio no está instalado: la interfaz /ui está desactivada.")

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/app/" if ui_enabled else "/docs")

    return app
