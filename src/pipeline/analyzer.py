"""Orquesta el flujo completo: texto del CV + oferta → puntuación explicada."""

from __future__ import annotations

import time

from src.config import Settings
from src.embeddings import SimilarityBackend, build_backend, semantic_similarity
from src.history import JobHistory
from src.llm import Advisor, Assistant, GroqClient, LLMError
from src.matching import JobProfile, MatchScorer, build_tips, check_ats
from src.nlp import (
    compute_experience_years,
    extract_education_level,
    extract_languages,
    extract_required_years,
    extract_timeline,
    get_skill_extractor,
)
from src.nlp.entity_extractor import CVProfile
from src.preprocessing import clean_text, split_sections
from src.utils.helpers import detect_language
from src.utils.logger import get_logger

log = get_logger(__name__)


class AnalysisPipeline:
    def __init__(self, settings: Settings, backend: SimilarityBackend | None = None,
                 llm_client: GroqClient | None = None, history: JobHistory | None = None) -> None:
        self.settings = settings
        self.history = history or JobHistory(
            settings.history_db_path if settings.history_enabled else None, settings.history_max_entries)
        self.skills = get_skill_extractor(str(settings.skills_db_path))
        self.backend = backend or build_backend(settings.embedding_backend, settings.embedding_model)
        self.scorer = MatchScorer(settings.weights, self.skills)
        if llm_client is None and settings.llm_available:
            llm_client = GroqClient(settings.groq_api_key, settings.groq_model, settings.groq_timeout_seconds)
        self.advisor = Advisor(llm_client)
        self.assistant = Assistant(llm_client, self.skills.extract) if llm_client else None

    # --------------------------------------------------------------- perfiles
    def build_cv_profile(self, cv_text: str, sections: dict[str, str]) -> tuple[CVProfile, bool]:
        """Devuelve (perfil, idioma_inferido)."""
        edu_text = sections.get("education")
        exp_text = sections.get("experience")
        if exp_text is None:  # sin sección de experiencia: todo salvo la formación
            exp_text = cv_text.replace(edu_text, "") if edu_text else cv_text
        languages = extract_languages(sections.get("languages") or cv_text)
        cv_lang = detect_language(cv_text)
        inferred = cv_lang not in languages
        if inferred:  # el CV está escrito en ese idioma: se asume nivel C1
            languages[cv_lang] = 5
        profile = CVProfile(
            skills=self.skills.extract(cv_text),
            years_experience=compute_experience_years(exp_text),
            education_level=extract_education_level(edu_text or cv_text, mode="max"),
            languages=languages,
            timeline=extract_timeline(exp_text, self.skills.extract),
        )
        return profile, inferred

    def build_job_profile(self, job_text: str) -> JobProfile:
        js = self.skills.extract_job_skills(job_text)
        return JobProfile(
            required_skills=js.required, nice_skills=js.nice,
            required_years=extract_required_years(job_text),
            education_level=extract_education_level(job_text, mode="min"),
            languages=extract_languages(job_text), alternatives=js.alternatives,
        )

    def category_coverage(self, job: JobProfile, result) -> list[dict]:
        """Cobertura de las habilidades de la oferta agrupadas por categoría (cloud, contenedores...)."""
        credit = {name: 1.0 for name in result.matched_skills}
        credit.update({p["required"]: 0.5 for p in result.partial_skills})
        groups: dict[str, list[float]] = {}
        for name in {**job.required_skills, **job.nice_skills}:
            groups.setdefault(self.skills.skills[name].category, []).append(credit.get(name, 0.0))
        rows = [{"category": c, "covered_pct": round(sum(v) / len(v) * 100), "total": len(v),
                 "matched": sum(1 for x in v if x == 1.0)} for c, v in groups.items()]
        return sorted(rows, key=lambda r: (-r["total"], r["category"]))

    # ------------------------------------------------------------------ flujo
    def extract_cv(self, cv_text: str) -> dict:
        cv_text = clean_text(cv_text)
        sections = split_sections(cv_text)
        profile, inferred = self.build_cv_profile(cv_text, sections)
        return {
            "skills": profile.skills, "years_experience": profile.years_experience,
            "education_level": profile.education_level, "languages": profile.languages,
            "languages_inferred": inferred, "sections_detected": sorted(sections),
        }

    def assist(self, cv_text: str, job_text: str, tasks: list[str]) -> dict:
        """Funciones de IA que SÍ envían el texto del CV y de la oferta a Groq (el consentimiento se exige en la API)."""
        if self.assistant is None:
            raise LLMError("La IA no está configurada: define GROQ_API_KEY en .env.")
        cv_text, job_text = clean_text(cv_text), clean_text(job_text)
        lang = detect_language(job_text)
        cv, _ = self.build_cv_profile(cv_text, split_sections(cv_text))
        job = self.build_job_profile(job_text)
        wanted = {**job.required_skills, **job.nice_skills}
        ctx = {"years": cv.years_experience, "matched": [s for s in wanted if s in cv.skills],
               "missing_required": [s for s in job.required_skills if s not in cv.skills],
               "missing_nice": [s for s in job.nice_skills if s not in cv.skills]}
        results = self.assistant.run(tasks, cv_text, job_text, lang, ctx)
        log.info("Asistente IA: tareas=%s errores=%d cv_chars=%d job_chars=%d", ",".join(tasks),
                 sum(1 for r in results.values() if "error" in r), len(cv_text), len(job_text))
        return {"language": lang, "results": results}

    def analyze(self, cv_text: str, job_text: str, use_llm: bool = True, remember: bool = True) -> dict:
        started = time.perf_counter()
        cv_text, job_text = clean_text(cv_text), clean_text(job_text)
        lang = detect_language(job_text)
        sections = split_sections(cv_text)

        cv, inferred = self.build_cv_profile(cv_text, sections)
        job = self.build_job_profile(job_text)
        semantic, raw = semantic_similarity(cv_text, job_text, self.backend)
        result = self.scorer.score(cv, job, semantic, backend=self.backend.name, lang=lang)
        tips = build_tips(result, cv, job, cv_text, sections, lang)
        advice = self.advisor.advise(result, tips, lang, use_llm)
        # Historial: solo la oferta (huella, título y nota); el CV nunca se guarda.
        if remember:
            job_id, seen_before = self.history.record(job_text, result.total_score, result.band)
        else:
            job_id, seen_before = None, self.history.lookup(job_text)
        elapsed = int((time.perf_counter() - started) * 1000)
        # Solo metadatos en el log: jamás el contenido del CV ni de la oferta.
        log.info("Análisis completado: score=%.1f backend=%s llm=%s cv_chars=%d job_chars=%d %dms",
                 result.total_score, self.backend.name, advice.source == "llm",
                 len(cv_text), len(job_text), elapsed)
        return {
            "score": result.total_score, "band": result.band, "band_label": result.band_label,
            "language": lang, "components": [vars(c) for c in result.components],
            "skills": {"matched": result.matched_skills, "partial": result.partial_skills,
                       "missing_required": result.missing_required, "missing_nice": result.missing_nice,
                       "extra": result.extra_skills,
                       "by_category": self.category_coverage(job, result)},
            "cv_profile": {"years_experience": cv.years_experience, "education_level": cv.education_level,
                           "languages": cv.languages, "languages_inferred": inferred,
                           "sections_detected": sorted(sections), "timeline": cv.timeline},
            "job_profile": {"required_years": job.required_years, "education_level": job.education_level,
                            "languages": job.languages},
            "job_id": job_id, "seen_before": seen_before,
            "ats": check_ats(cv_text, job_text, sections, result, lang),
            "tips": tips, "advice": advice.to_dict(), "warnings": result.warnings,
            "meta": {"similarity_backend": self.backend.name, "similarity_raw": round(raw, 3),
                     "similarity_calibrated": round(semantic, 3), "elapsed_ms": elapsed,
                     "weights": self.settings.weights},
        }
