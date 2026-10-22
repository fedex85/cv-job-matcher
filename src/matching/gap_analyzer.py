"""Análisis de carencias y consejos basados en reglas (sin LLM)."""

from __future__ import annotations

import re

from src.nlp.entity_extractor import CEFR_LABELS, LANG_NAMES_EN, LANG_NAMES_ES, CVProfile

from .messages import t
from .scorer import JobProfile, MatchResult

CERT_HINTS = {
    "AWS": "AWS Certified Solutions Architect – Associate",
    "Azure": "Microsoft AZ-104",
    "Google Cloud": "Google Associate Cloud Engineer",
    "Kubernetes": "CKA / CKAD",
    "Terraform": "HashiCorp Terraform Associate",
    "Ansible": "Red Hat Certified Specialist in Ansible Automation",
    "Linux": "LPIC-1 / RHCSA",
    "Docker": "Docker Certified Associate",
    "Cisco": "CCNA",
    "ITIL": "ITIL 4 Foundation",
    "Scrum": "PSM I / CSM",
}
MAX_SKILL_TIPS = 3  # consejos individuales; el resto se agrupa en uno


def build_tips(result: MatchResult, cv: CVProfile, job: JobProfile, cv_text: str,
               sections: dict[str, str], lang: str) -> list[str]:
    tips: list[str] = []
    for skill in result.missing_required[:MAX_SKILL_TIPS]:
        cert = t(lang, "tip.cert", c=CERT_HINTS[skill]) if skill in CERT_HINTS else ""
        tips.append(t(lang, "tip.missing_skill", s=skill, cert=cert))
    rest = result.missing_required[MAX_SKILL_TIPS:]
    if rest:
        tips.append(t(lang, "tip.missing_many", n=len(rest), s=", ".join(rest)))
    for p in result.partial_skills[:3]:
        tips.append(t(lang, "tip.partial", via=p["via"], s=p["required"]))
    if result.missing_nice:
        tips.append(t(lang, "tip.nice", s=", ".join(result.missing_nice[:6])))

    if job.required_years and 0 < cv.years_experience < job.required_years:
        tips.append(t(lang, "tip.exp", req=job.required_years, cv=cv.years_experience))
    if job.education_level > cv.education_level:
        tips.append(t(lang, "tip.edu", req=t(lang, f"edu.level.{job.education_level}")))
    names = LANG_NAMES_EN if lang == "en" else LANG_NAMES_ES
    for code, need in job.languages.items():
        if cv.languages.get(code, 0) < need:
            tips.append(t(lang, "tip.lang", language=names.get(code, code), lvl=CEFR_LABELS[need]))

    words = len(cv_text.split())
    if words < 250:
        tips.append(t(lang, "tip.short", w=words))
    if not re.search(r"\d+\s*%|\b\d{2,}\b", sections.get("experience", cv_text)):
        tips.append(t(lang, "tip.no_numbers"))
    if "skills" not in sections:
        tips.append(t(lang, "tip.no_skills_section"))
    if "experience" not in sections:
        tips.append(t(lang, "tip.no_exp_section"))
    if not tips:
        tips.append(t(lang, "tip.good"))
    return tips
