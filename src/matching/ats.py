"""Comprobaciones de compatibilidad ATS (sistemas de filtrado automático de CVs).

Es una estimación basada en reglas habituales —contacto legible, secciones estándar, fechas, texto
limpio y palabras clave literales—, no la simulación de ningún ATS concreto. Todo es determinista y se
calcula solo con el texto ya extraído: no se guarda ni se envía nada.
"""

from __future__ import annotations

import re
import unicodedata

from src.utils.helpers import fold

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,3}\)?[\s.-]?){2,4}\d{2,4}(?!\d)")
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
STOP = {"de", "la", "el", "en", "y", "a", "con", "para", "the", "and", "of", "for", "in", "remoto", "remote",
        "hibrido", "hybrid", "senior", "junior", "m", "h", "f"}

# (peso, textos es/en)
TEXTS = {
    "es": {
        "email": ("Correo electrónico", "Aparece un correo de contacto.", "No encuentro un correo electrónico. Ponlo en texto plano al inicio del CV."),
        "phone": ("Teléfono", "Aparece un teléfono de contacto.", "No encuentro un teléfono. Añádelo en texto plano junto al correo."),
        "experience": ("Sección de experiencia", "Detecto la sección de experiencia.", "No detecto un encabezado de experiencia. Usa uno estándar: «Experiencia profesional»."),
        "education": ("Sección de formación", "Detecto la sección de formación.", "No detecto un encabezado de formación. Usa uno estándar: «Formación»."),
        "skills": ("Sección de habilidades", "Detecto una sección de habilidades.", "No detecto una sección de habilidades. Añade «Habilidades» con las tecnologías literales."),
        "dates": ("Fechas legibles", "Hay fechas en tus puestos.", "Veo pocas fechas. Indica cada puesto con un periodo como «2019 – 2022»."),
        "length": ("Longitud del texto", "La longitud es adecuada ({n} palabras).", "El CV tiene {n} palabras; lo habitual es entre 250 y 1000."),
        "chars": ("Texto limpio", "El texto se extrae sin símbolos raros.", "Hay símbolos o iconos que algunos ATS leen mal ({pct} %). Usa viñetas simples y evita iconos."),
        "layout": ("Maquetación lineal", "El texto sigue un orden lineal.", "Muchas líneas muy cortas: parece haber columnas o tablas que pueden mezclar el orden. Usa una sola columna."),
        "keywords": ("Palabras clave de la oferta", "Aparece el {pct} % de las palabras clave imprescindibles.", "Solo aparece el {pct} % de las palabras clave imprescindibles. Incluye literalmente las que domines."),
        "title": ("Título del puesto", "El título de la oferta aparece en tu CV.", "El título «{t}» no aparece en tu CV. Si encaja contigo, inclúyelo en tu perfil."),
    },
    "en": {
        "email": ("Email", "A contact email is present.", "No email found. Put it in plain text at the top."),
        "phone": ("Phone", "A contact phone is present.", "No phone found. Add it in plain text next to the email."),
        "experience": ("Experience section", "Experience section detected.", "No experience heading detected. Use a standard one: “Work experience”."),
        "education": ("Education section", "Education section detected.", "No education heading detected. Use a standard one: “Education”."),
        "skills": ("Skills section", "Skills section detected.", "No skills section detected. Add “Skills” with literal technology names."),
        "dates": ("Readable dates", "Your roles have dates.", "Few dates found. Give each role a period such as “2019 – 2022”."),
        "length": ("Text length", "Length is appropriate ({n} words).", "The CV has {n} words; 250–1000 is typical."),
        "chars": ("Clean text", "Text extracts without odd symbols.", "Some symbols or icons may be misread by ATS ({pct} %). Use simple bullets and avoid icons."),
        "layout": ("Linear layout", "Text reads in a linear order.", "Many very short lines: columns or tables may scramble the order. Use a single column."),
        "keywords": ("Job keywords", "{pct} % of the must-have keywords appear.", "Only {pct} % of the must-have keywords appear. Include the ones you know, literally."),
        "title": ("Job title", "The job title appears in your CV.", "The title “{t}” is not in your CV. If it fits you, include it in your profile."),
    },
}
WEIGHTS = {"email": 12, "phone": 6, "experience": 12, "education": 6, "skills": 8, "dates": 10, "length": 6,
           "chars": 6, "layout": 8, "keywords": 22, "title": 4}
CREDIT = {"ok": 1.0, "warn": 0.5, "bad": 0.0}
NOTE = {"es": "Estimación por reglas habituales; cada empresa usa su propio ATS.",
        "en": "Rule-based estimate; every company uses its own ATS."}


def _odd_ratio(text: str) -> float:
    """Proporción de caracteres que suelen fallar en un ATS: iconos, emojis, dibujo de cajas, uso privado."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    odd = sum(1 for c in chars if unicodedata.category(c) in {"So", "Co", "Cn", "Cs"} and c not in "•·–—−→€°©®™")
    return odd / len(chars)


def _short_line_ratio(text: str) -> float:
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if len(lines) < 15:
        return 0.0
    return sum(1 for ln in lines if len(ln.split()) <= 2) / len(lines)


def _title_of(job_text: str) -> str | None:
    first = next((ln.strip(" -–—•*#\t") for ln in job_text.split("\n") if ln.strip()), "")
    return first if 3 <= len(first) <= 80 and not first.endswith((":", ".")) else None


def _title_coverage(title: str, cv_text: str) -> float | None:
    words = [w for w in re.findall(r"[a-z0-9+#.]+", fold(title)) if len(w) > 1 and w not in STOP]
    if not words:
        return None
    cv = fold(cv_text)
    return sum(1 for w in words if re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", cv)) / len(words)


def check_ats(cv_text: str, job_text: str, sections: dict[str, str], skills_result, lang: str = "es") -> dict:
    """skills_result: el MatchResult del scorer (para las palabras clave imprescindibles)."""
    tx = TEXTS["en" if lang == "en" else "es"]
    words = len(cv_text.split())
    results: dict[str, tuple[str, dict]] = {}

    results["email"] = ("ok" if EMAIL_RE.search(cv_text) else "bad", {})
    phones = [m.group() for m in PHONE_RE.finditer(cv_text) if len(re.sub(r"\D", "", m.group())) >= 9]
    results["phone"] = ("ok" if phones else "warn", {})
    for key in ("experience", "education", "skills"):
        results[key] = ("ok" if key in sections else ("bad" if key == "experience" else "warn"), {})
    years = len(YEAR_RE.findall(cv_text))
    results["dates"] = ("ok" if years >= 4 else "warn" if years >= 2 else "bad", {})
    results["length"] = ("ok" if 250 <= words <= 1000 else "bad" if words < 120 or words > 1800 else "warn", {"n": words})
    odd = _odd_ratio(cv_text)
    results["chars"] = ("ok" if odd < 0.005 else "warn" if odd < 0.03 else "bad", {"pct": f"{odd * 100:.1f}"})
    short = _short_line_ratio(cv_text)
    results["layout"] = ("ok" if short < 0.5 else "warn" if short < 0.7 else "bad", {})

    matched = len(skills_result.matched_skills) + len(skills_result.partial_skills)
    total_req = matched + len(skills_result.missing_required)
    if total_req:
        pct = round(len(skills_result.matched_skills) / total_req * 100)
        results["keywords"] = ("ok" if pct >= 80 else "warn" if pct >= 50 else "bad", {"pct": pct})
    title = _title_of(job_text)
    cover = _title_coverage(title, cv_text) if title else None
    if cover is not None:
        results["title"] = ("ok" if cover >= 0.6 else "warn", {"t": title})

    checks, earned, possible = [], 0.0, 0
    for key, (status, vars_) in results.items():
        label, good, fix = tx[key]
        checks.append({"id": key, "label": label, "status": status,
                       "detail": (good if status == "ok" else fix).format(**vars_)})
        earned += WEIGHTS[key] * CREDIT[status]
        possible += WEIGHTS[key]
    score = round(earned / possible * 100) if possible else 0
    order = {"bad": 0, "warn": 1, "ok": 2}
    checks.sort(key=lambda c: (order[c["status"]], -WEIGHTS[c["id"]]))
    return {"score": score, "band": "ok" if score >= 80 else "warn" if score >= 60 else "bad",
            "checks": checks, "note": NOTE["en" if lang == "en" else "es"]}
