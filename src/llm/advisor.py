"""Genera el resumen y las recomendaciones finales. Con Groq si está
configurado; si no (o si falla), usa los consejos basados en reglas."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from src.matching.messages import t
from src.matching.scorer import MatchResult
from src.utils.logger import get_logger

from .client import GroqClient, LLMError
from .prompts import SYSTEM, build_user_prompt

log = get_logger(__name__)
MAX_ITEMS = 5
MAX_CHARS = 400


@dataclass
class Advice:
    summary: str
    recommendations: list[str]
    source: str                    # "llm" | "rules"
    llm_error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _payload(result: MatchResult, lang: str) -> dict:
    return {
        "language": lang,
        "score": result.total_score,
        "band": result.band,
        "components": {c.key: c.score for c in result.components if c.applicable},
        "matched_skills": result.matched_skills[:15],
        "missing_required_skills": result.missing_required[:10],
        "missing_nice_skills": result.missing_nice[:8],
    }


def _parse(raw: str) -> tuple[str, list[str]]:
    try:
        data = json.loads(raw)
        summary = data["summary"]
        recs = data["recommendations"]
    except (ValueError, KeyError, TypeError) as exc:
        raise LLMError("La IA devolvió un formato inesperado.") from exc
    if not isinstance(summary, str) or not isinstance(recs, list):
        raise LLMError("La IA devolvió un formato inesperado.")
    clean = [r.strip()[:MAX_CHARS] for r in recs if isinstance(r, str) and r.strip()][:MAX_ITEMS]
    if not clean:
        raise LLMError("La IA no devolvió recomendaciones.")
    return summary.strip()[:MAX_CHARS * 2], clean


class Advisor:
    def __init__(self, client: GroqClient | None) -> None:
        self._client = client

    def advise(self, result: MatchResult, rule_tips: list[str], lang: str, use_llm: bool) -> Advice:
        summary = t(lang, "advice.summary", score=result.total_score, band=result.band_label)
        if not (use_llm and self._client):
            return Advice(summary, rule_tips[:MAX_ITEMS], "rules")
        try:
            raw = self._client.chat_json(SYSTEM.get(lang, SYSTEM["es"]),
                                         build_user_prompt(_payload(result, lang)))
            llm_summary, recs = _parse(raw)
            return Advice(llm_summary, recs, "llm")
        except LLMError as exc:
            log.warning("Asesor LLM no disponible: %s", exc)
            return Advice(summary, rule_tips[:MAX_ITEMS], "rules", llm_error=str(exc))
