"""Divide un CV en secciones (experiencia, formación, habilidades, idiomas...)
reconociendo encabezados en español e inglés."""

from __future__ import annotations

import re

from src.utils.helpers import fold

SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "summary": ("perfil", "resumen", "sobre mi", "summary", "profile", "about me", "objetivo"),
    "experience": ("experiencia", "experience", "historial laboral", "work history",
                   "employment", "trayectoria", "professional experience"),
    "education": ("formacion", "educacion", "estudios", "education", "academic", "titulacion"),
    "skills": ("habilidades", "competencias", "skills", "tecnologias", "technologies",
               "conocimientos", "stack", "technical skills", "tecnico"),
    "languages": ("idiomas", "languages", "lenguas"),
    "certifications": ("certificaciones", "certificados", "certifications", "cursos", "courses",
                       "licenses"),
    "projects": ("proyectos", "projects"),
}


def _heading_of(line: str) -> str | None:
    stripped = line.strip().rstrip(":").strip()
    if not stripped or len(stripped) > 45 or re.search(r"[.;]$", stripped):
        return None
    folded = fold(stripped)
    words = folded.split()
    if len(words) > 5:
        return None
    for section, keys in SECTION_KEYWORDS.items():
        for key in keys:
            if folded == key or folded.startswith(key + " ") or folded.endswith(" " + key) \
                    or (len(words) <= 3 and key in folded):
                return section
    return None


def split_sections(text: str) -> dict[str, str]:
    """Devuelve {sección: texto}. Lo previo al primer encabezado va en 'header'."""
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in text.split("\n"):
        heading = _heading_of(line)
        if heading:
            current = heading
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items() if "".join(lines).strip()}
