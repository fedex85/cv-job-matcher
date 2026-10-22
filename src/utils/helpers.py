"""Utilidades pequeñas y puras."""

from __future__ import annotations

import re
import unicodedata

_STOP_ES = {"de", "la", "el", "en", "y", "los", "las", "del", "con", "para", "por", "una", "un",
            "se", "que", "como", "al", "su", "experiencia", "trabajo", "nuestro", "equipo"}
_STOP_EN = {"the", "and", "of", "to", "in", "for", "with", "a", "an", "is", "are", "on", "our",
            "you", "will", "experience", "work", "team", "we", "your", "as"}


def fold(text: str) -> str:
    """Minúsculas y sin acentos (conserva ñ→n también): comparación robusta ES/EN."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def detect_language(text: str) -> str:
    """Heurística ES/EN por palabras vacías. Devuelve 'es' o 'en' (por defecto 'es')."""
    words = re.findall(r"[a-záéíóúñü]+", text.lower()[:6000])
    es = sum(1 for w in words if w in _STOP_ES)
    en = sum(1 for w in words if w in _STOP_EN)
    return "en" if en > es else "es"
