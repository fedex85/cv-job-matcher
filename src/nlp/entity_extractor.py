"""Extracción por reglas de años de experiencia, nivel de estudios e idiomas
(español e inglés). Todo es explicable: cada dato sale de un patrón concreto."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from src.utils.helpers import fold

# ---------------------------------------------------------------- experiencia
_MONTH = (
    r"ene|enero|jan|january|feb|febrero|february|mar|marzo|march|abr|abril|apr|april|may|mayo|"
    r"jun|junio|june|jul|julio|july|ago|agosto|aug|august|sep|sept|septiembre|setiembre|september|"
    r"oct|octubre|october|nov|noviembre|november|dic|diciembre|dec|december"
)
_MONTH_NUM = {}
for _i, _names in enumerate(
    [("ene", "jan"), ("feb",), ("mar",), ("abr", "apr"), ("may",), ("jun",), ("jul",),
     ("ago", "aug"), ("sep", "set"), ("oct",), ("nov",), ("dic", "dec")], start=1):
    for _n in _names:
        _MONTH_NUM[_n] = _i

_NOW = r"actualidad|presente|actual|present|current|now|hoy|ahora|la fecha|date"


def _date(suffix: str) -> str:
    return (
        rf"(?:(?:(?P<m{suffix}>{_MONTH})[a-z]*\.?\s*(?:de\s+|del\s+|,\s*)?"
        rf"|(?P<n{suffix}>\d{{1,2}})[/.\-])?(?P<y{suffix}>(?:19|20)\d{{2}}))"
    )


_RANGE = re.compile(
    rf"(?<!\d){_date('1')}\s*(?:-|a|al|hasta|to|until)\s*(?:{_date('2')}|(?P<now>{_NOW}))(?!\d)"
)
_STATED_YEARS = re.compile(
    r"(\d{1,2})\s*\+?\s*(?:anos|years?|yrs)\s+(?:de\s+|of\s+)?(?:experiencia|experience)"
)
_JOB_YEARS = re.compile(
    r"(?<!\d)(\d{1,2})(?:\s*(?:-|a|to)\s*(\d{1,2}))?\s*\+?\s*(?:anos|years?|yrs)\b"
)


def _month_of(token: str | None, num: str | None) -> int:
    if token:
        return _MONTH_NUM.get(token[:3], 7)
    if num and 1 <= int(num) <= 12:
        return int(num)
    return 7  # sin mes: punto medio del año


def compute_experience_years(text: str, today: date | None = None) -> float:
    """Años de experiencia a partir de rangos de fechas (se fusionan los solapes)
    y de afirmaciones explícitas ("10+ años de experiencia"). Devuelve el mayor."""
    today = today or date.today()
    folded = fold(text).replace("–", "-").replace("—", "-")
    now_idx = today.year * 12 + today.month - 1
    spans: list[tuple[int, int]] = []
    for m in _RANGE.finditer(folded):
        y1 = int(m.group("y1"))
        start = y1 * 12 + _month_of(m.group("m1"), m.group("n1")) - 1
        if m.group("now"):
            end = now_idx
        else:
            end = int(m.group("y2")) * 12 + _month_of(m.group("m2"), m.group("n2")) - 1
        end = min(end, now_idx)
        if 1970 <= y1 <= today.year and 0 < end - start <= 45 * 12:
            spans.append((start, end))
    spans.sort()
    merged: list[list[int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    from_dates = sum(e - s for s, e in merged) / 12
    stated = [int(n) for n in _STATED_YEARS.findall(folded)]
    return round(max([from_dates] + [float(x) for x in stated if x <= 50]), 1)


def extract_required_years(job_text: str) -> float | None:
    """Años de experiencia que pide la oferta (el mínimo del rango más exigente)."""
    folded = fold(job_text)
    found: list[float] = []
    for m in _JOB_YEARS.finditer(folded):
        window = folded[max(0, m.start() - 60): m.end() + 60]
        if "experien" in window or "experience" in window:
            n = int(m.group(1))
            if 0 < n <= 30:
                found.append(float(n))
    return max(found) if found else None


def extract_timeline(text: str, skills_of: Callable[[str], dict[str, int]], today: date | None = None,
                     limit: int = 6) -> list[dict]:
    """Línea de tiempo laboral: cada línea con un rango de fechas abre una entrada (título =
    el resto de la línea) y recoge las habilidades de las líneas siguientes hasta el próximo
    rango. Devuelve las más recientes primero."""
    today = today or date.today()
    now_idx = today.year * 12 + today.month - 1
    lines = text.split("\n")
    starts: list[tuple[int, re.Match[str]]] = []
    for i, line in enumerate(lines):
        m = _RANGE.search(fold(line).replace("–", "-").replace("—", "-"))
        if m and len(fold(line)) == len(line) and 1970 <= int(m.group("y1")) <= today.year:
            starts.append((i, m))
    entries = []
    for n, (i, m) in enumerate(starts):
        end_line = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        y1 = int(m.group("y1"))
        start = y1 * 12 + _month_of(m.group("m1"), m.group("n1")) - 1
        current = bool(m.group("now"))
        end = now_idx if current else int(m.group("y2")) * 12 + _month_of(m.group("m2"), m.group("n2")) - 1
        end = min(end, now_idx)
        if end <= start:
            continue
        raw = lines[i]
        title = re.sub(r"[\s(\[\]),;:|–—-]+$|^[\s(\[\]),;:|–—-]+", "", raw[:m.start()] + " " + raw[m.end():])
        title = re.sub(r"\s{2,}", " ", re.sub(r"\(\s*\)|\[\s*\]", "", title)).strip() or "Experiencia"
        counts = skills_of("\n".join(lines[i:end_line]))
        top = sorted(counts, key=lambda k: -counts[k])[:6]
        y2 = "actualidad" if current else str(int(m.group("y2")))
        entries.append({"title": title[:100], "period": f"{y1} – {y2}", "years": round((end - start) / 12, 1),
                        "skills": top, "_start": start})
    entries.sort(key=lambda e: -e["_start"])
    for e in entries:
        del e["_start"]
    return entries[:limit]


# ------------------------------------------------------------------ formación
EDUCATION_LABELS = {0: "none", 1: "vocational", 2: "degree", 3: "master", 4: "phd"}

_EDU_PATTERNS: list[tuple[int, re.Pattern[str]]] = [
    (4, re.compile(r"\b(doctorado|phd|ph\.d|doctorate|doctor en)\b")),
    (3, re.compile(r"\b(master|msc|m\.sc|mba|postgrado|posgrado|master's|maestria)\b")),
    (1, re.compile(
        r"\b(formacion profesional|ciclo formativo|grado superior|grado medio|tecnico superior|"
        r"fp ?(?:ii|2|superior|medio)?|vocational|associate degree|higher national|bachillerato)\b")),
    (2, re.compile(
        r"\b(grado en|grado universitario|graduado|licenciatura|licenciado|licenciada|bachelor|"
        r"bsc|b\.sc|degree|universitari[oa]s?|titulacion universitaria|diplomatura|"
        r"ingenier[oa] (?:en|de|tecnic[oa]|superior|informatic[oa])|ingenieria (?:en|de|tecnica|superior|informatica)|"
        r"ingenieria|engineering)\b")),
]


def extract_education_level(text: str, *, mode: str = "max") -> int:
    """Nivel 0-4. mode='max' para CVs (el mayor logrado); 'min' para ofertas
    (el mínimo aceptado cuando se mencionan varias opciones, p. ej. 'Grado o FP')."""
    folded = fold(text)
    levels = [lvl for lvl, rx in _EDU_PATTERNS if rx.search(folded)]
    if not levels:
        return 0
    return max(levels) if mode == "max" else min(levels)


# ------------------------------------------------------------------- idiomas
_LANGS = {
    "en": ("ingles", "english"),
    "es": ("espanol", "castellano", "spanish"),
    "fr": ("frances", "french"),
    "de": ("aleman", "german"),
    "pt": ("portugues", "portuguese"),
    "it": ("italiano", "italian"),
    "ca": ("catalan",),
    "gl": ("gallego", "galician"),
    "eu": ("euskera", "vasco", "basque"),
    "zh": ("chino", "mandarin", "chinese"),
}
LANG_NAMES_ES = {"en": "inglés", "es": "español", "fr": "francés", "de": "alemán", "pt": "portugués",
                 "it": "italiano", "ca": "catalán", "gl": "gallego", "eu": "euskera", "zh": "chino"}
LANG_NAMES_EN = {"en": "English", "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese",
                 "it": "Italian", "ca": "Catalan", "gl": "Galician", "eu": "Basque", "zh": "Chinese"}
_LANG_RX = re.compile(
    r"(?<![a-z])(" + "|".join(n for names in _LANGS.values() for n in names) + r")(?![a-z])"
)
_NAME_TO_CODE = {n: code for code, names in _LANGS.items() for n in names}
_CEFR = {"a1": 1, "a2": 2, "b1": 3, "b2": 4, "c1": 5, "c2": 6}
_LEVEL_WORDS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"\b(nativo|native|bilingue|bilingual|lengua materna|mother tongue)\b"), 6),
    (re.compile(r"\b(upper[- ]intermediate|intermedio[- ]alto|intermedio alto)\b"), 4),
    (re.compile(r"\b(fluido|fluida|fluent|avanzado|advanced|profesional|professional|alto|proficient|excelente)\b"), 5),
    (re.compile(r"\b(intermedio|intermediate|medio|conversacional|conversational)\b"), 3),
    (re.compile(r"\b(basico|basic|elemental|elementary|beginner|principiante|escolar)\b"), 2),
]
DEFAULT_LANG_LEVEL = 3  # idioma citado sin nivel: se asume B1
CEFR_LABELS = {1: "A1", 2: "A2", 3: "B1", 4: "B2", 5: "C1", 6: "C2"}


_CONJ = re.compile(r"\b(?:and|y|e|with|con)\b|[&/]")


def _level_in(window: str) -> int | None:
    m = re.search(r"\b([abc][12])\b", window)
    if m:
        return _CEFR[m.group(1)]
    for rx, lvl in _LEVEL_WORDS:
        if rx.search(window):
            return lvl
    return None


def extract_languages(text: str) -> dict[str, int]:
    """{código idioma: nivel 1-6 (A1..C2)}. Si el nivel no aparece, B1."""
    folded = fold(text).replace("ñ", "n")
    matches = list(_LANG_RX.finditer(folded))
    result: dict[str, int] = {}
    for i, m in enumerate(matches):
        code = _NAME_TO_CODE[m.group(1)]
        end_limit = matches[i + 1].start() if i + 1 < len(matches) else len(folded)
        after = re.split(r"[\n;.]", folded[m.end(): min(m.end() + 40, end_limit)])[0]
        before = re.split(r"[\n;.,]", folded[max(0, m.start() - 30): m.start()])[-1]
        # "Advanced English and basic German": cada nivel pertenece a su idioma adyacente
        after, before = _CONJ.split(after)[0], _CONJ.split(before)[-1]
        level = _level_in(after) or _level_in(before) or DEFAULT_LANG_LEVEL
        result[code] = max(result.get(code, 0), level)
    return result


@dataclass(frozen=True)
class CVProfile:
    skills: dict[str, int]
    years_experience: float
    education_level: int
    languages: dict[str, int]
    timeline: list[dict] = field(default_factory=list)
