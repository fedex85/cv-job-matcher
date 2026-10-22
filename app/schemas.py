"""Modelos de respuesta de la API (documentan el contrato en /docs)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class Component(BaseModel):
    key: str
    label: str
    score: float = Field(ge=0, le=100)
    weight: float
    effective_weight: float
    applicable: bool
    note: str
    detail: dict = {}


class SkillsReport(BaseModel):
    matched: list[str]
    partial: list[dict]
    missing_required: list[str]
    missing_nice: list[str]
    extra: list[str]
    by_category: list[dict] = []


class Advice(BaseModel):
    summary: str
    recommendations: list[str]
    source: str = Field(description="'llm' (Groq) o 'rules' (consejos por reglas)")
    llm_error: str | None = None


class AnalysisResponse(BaseModel):
    score: float = Field(ge=0, le=100, description="Compatibilidad global 0-100")
    band: str
    band_label: str
    language: str
    components: list[Component]
    skills: SkillsReport
    cv_profile: dict
    job_profile: dict
    job_id: str | None = Field(None, description="Identificador de la oferta en el historial")
    seen_before: dict | None = Field(
        None, description="Si la oferta (o una casi idéntica) ya se analizó antes: fechas, veces y nota anterior")
    ats: dict = Field(description="Comprobaciones ATS del CV: nota 0-100 y lista de checks (ok/warn/bad)")
    tips: list[str]
    advice: Advice
    warnings: list[str]
    meta: dict


class CVExtraction(BaseModel):
    skills: dict[str, int]
    years_experience: float
    education_level: int
    languages: dict[str, int]
    languages_inferred: bool
    sections_detected: list[str]


class SkillItem(BaseModel):
    name: str
    category: str
    family: str | None = None


class HistoryItem(BaseModel):
    id: str
    title: str
    first_seen: str
    last_seen: str
    times: int
    last_score: float
    last_band: str


class AssistResponse(BaseModel):
    language: str
    results: dict[str, dict] = Field(
        description="Por tarea: rewrite {items}, summary {text}, cover {text}, interview {questions}; o {error}. "
                    "Cada texto generado lleva 'check' con cifras/tecnologías que no están en el CV.")
