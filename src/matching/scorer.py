"""Puntuación de compatibilidad CV ↔ oferta, explicable por componentes.

score = Σ peso_efectivo_i · puntuación_i      (puntuaciones 0-100)

Los pesos se normalizan sobre los componentes *aplicables*: si la oferta no
pide idiomas, ese bloque no puntúa y su peso se reparte entre los demás.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from src.nlp.entity_extractor import CEFR_LABELS, CVProfile
from src.nlp.skill_extractor import Skill, SkillExtractor
from src.utils.helpers import clamp

from .messages import t

PARTIAL_CREDIT = 0.5          # misma familia tecnológica (p. ej. AWS ↔ Azure)
REQUIRED_SHARE = 0.8          # dentro de habilidades: 80 % imprescindibles, 20 % valorables
NEUTRAL_UNKNOWN_EXPERIENCE = 50.0

BANDS = [(80, "very_high"), (65, "high"), (50, "medium"), (35, "low"), (0, "very_low")]


@dataclass
class JobProfile:
    required_skills: dict[str, int]
    nice_skills: dict[str, int]
    required_years: float | None
    education_level: int
    languages: dict[str, int]
    alternatives: list[list[str]] = field(default_factory=list)  # "AWS o Azure"


@dataclass
class ComponentScore:
    key: str
    label: str
    score: float                 # 0-100
    weight: float                # peso configurado
    effective_weight: float      # peso tras normalizar entre componentes aplicables
    applicable: bool
    note: str
    detail: dict = field(default_factory=dict)


@dataclass
class MatchResult:
    total_score: float
    band: str
    band_label: str
    components: list[ComponentScore]
    matched_skills: list[str]
    partial_skills: list[dict]
    missing_required: list[str]
    missing_nice: list[str]
    extra_skills: list[str]
    warnings: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def band_for(score: float) -> str:
    return next(name for threshold, name in BANDS if score >= threshold)


class MatchScorer:
    def __init__(self, weights: dict[str, float], skills: SkillExtractor) -> None:
        self.weights = weights
        self.skills = skills

    # ------------------------------------------------------------------ skills
    def _credit(self, name: str, cv_skills: dict[str, int],
                alternatives: list[list[str]]) -> tuple[float, str | None]:
        if name in cv_skills:
            return 1.0, None
        for group in alternatives:  # "A o B": tener cualquiera cubre todo el grupo
            if name in group and any(other in cv_skills for other in group):
                return 1.0, None
        fam = self.skills.skills.get(name, Skill(name, "")).family
        if fam:
            for other in cv_skills:
                s = self.skills.skills.get(other)
                if s and s.family == fam:
                    return PARTIAL_CREDIT, other
        return 0.0, None

    def _skills_block(self, cv: CVProfile, job: JobProfile, lang: str) -> tuple[float | None, dict, str]:
        if not job.required_skills and not job.nice_skills:
            return None, {}, t(lang, "skills.none")
        matched, partial, missing_req, missing_nice = [], [], [], []

        def coverage(names: dict[str, int], missing: list[str]) -> float:
            if not names:
                return 0.0
            total = 0.0
            for name in names:
                credit, via = self._credit(name, cv.skills, job.alternatives)
                total += credit
                if credit == 1.0:
                    matched.append(name)
                elif credit > 0:
                    partial.append({"required": name, "via": via})
                else:
                    missing.append(name)
            return total / len(names)

        req_cov = coverage(job.required_skills, missing_req)
        nice_cov = coverage(job.nice_skills, missing_nice)
        if job.required_skills and job.nice_skills:
            score = (REQUIRED_SHARE * req_cov + (1 - REQUIRED_SHARE) * nice_cov) * 100
        else:
            score = (req_cov if job.required_skills else nice_cov) * 100
        n_total = len(job.required_skills) + len(job.nice_skills)
        extra = sorted((s for s in cv.skills if s not in job.required_skills and s not in job.nice_skills),
                       key=lambda s: -cv.skills[s])[:12]
        detail = {
            "matched": sorted(matched), "partial": partial, "missing_required": sorted(missing_req),
            "missing_nice": sorted(missing_nice), "extra": extra,
            "required_coverage": round(req_cov, 3), "nice_coverage": round(nice_cov, 3),
        }
        note = t(lang, "skills.note", m=len(matched), n=n_total, p=len(partial))
        return score, detail, note

    # ------------------------------------------------------- resto de bloques
    @staticmethod
    def _experience_block(cv: CVProfile, job: JobProfile, lang: str) -> tuple[float | None, dict, str]:
        if not job.required_years:
            return None, {}, t(lang, "exp.none")
        detail = {"cv_years": cv.years_experience, "required_years": job.required_years}
        if cv.years_experience <= 0:
            return NEUTRAL_UNKNOWN_EXPERIENCE, {**detail, "low_confidence": True}, t(lang, "exp.unknown")
        score = clamp(cv.years_experience / job.required_years) * 100
        return score, detail, t(lang, "exp.note", cv=cv.years_experience, req=job.required_years)

    @staticmethod
    def _education_block(cv: CVProfile, job: JobProfile, lang: str) -> tuple[float | None, dict, str]:
        if job.education_level <= 0:
            return None, {}, t(lang, "edu.none")
        gap = job.education_level - cv.education_level
        score = 100.0 if gap <= 0 else (50.0 if gap == 1 else 0.0)
        detail = {"cv_level": cv.education_level, "required_level": job.education_level}
        note = t(lang, "edu.note", cv=t(lang, f"edu.level.{cv.education_level}"),
                 req=t(lang, f"edu.level.{job.education_level}"))
        return score, detail, note

    @staticmethod
    def _languages_block(cv: CVProfile, job: JobProfile, lang: str) -> tuple[float | None, dict, str]:
        if not job.languages:
            return None, {}, t(lang, "lang.none")
        rows, total, ok = [], 0.0, 0
        for code, need in job.languages.items():
            have = cv.languages.get(code, 0)
            credit = clamp(have / need)
            total += credit
            ok += have >= need
            rows.append({"language": code, "required": CEFR_LABELS[need],
                         "cv": CEFR_LABELS.get(have), "ok": have >= need})
        score = total / len(job.languages) * 100
        return score, {"languages": rows}, t(lang, "lang.note", ok=ok, n=len(job.languages))

    # ------------------------------------------------------------------ total
    def score(self, cv: CVProfile, job: JobProfile, semantic: float, *, backend: str = "tfidf",
              lang: str = "es") -> MatchResult:
        blocks: dict[str, tuple[float | None, dict, str]] = {
            "skills": self._skills_block(cv, job, lang),
            "semantic": (semantic * 100, {"backend": backend}, t(lang, "semantic.note", backend=backend)),
            "experience": self._experience_block(cv, job, lang),
            "education": self._education_block(cv, job, lang),
            "languages": self._languages_block(cv, job, lang),
        }
        applicable_weight = sum(self.weights[k] for k, (s, _, _) in blocks.items() if s is not None)
        components: list[ComponentScore] = []
        total = 0.0
        for key, (score, detail, note) in blocks.items():
            eff = (self.weights[key] / applicable_weight) if score is not None and applicable_weight else 0.0
            total += eff * (score or 0.0)
            components.append(ComponentScore(
                key=key, label=t(lang, f"comp.{key}"), score=round(score or 0.0, 1),
                weight=round(self.weights[key], 4), effective_weight=round(eff, 4),
                applicable=score is not None, note=note, detail=detail))
        total = round(clamp(total, 0, 100), 1)
        sk = blocks["skills"][1]
        band = band_for(total)
        warnings = [] if sk else [t(lang, "warn.no_job_skills")]
        return MatchResult(
            total_score=total, band=band, band_label=t(lang, f"band.{band}"), components=components,
            matched_skills=sk.get("matched", []), partial_skills=sk.get("partial", []),
            missing_required=sk.get("missing_required", []), missing_nice=sk.get("missing_nice", []),
            extra_skills=sk.get("extra", []), warnings=warnings,
        )
