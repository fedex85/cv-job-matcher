"""Similitud semántica calibrada a [0, 1] entre un CV y una oferta."""

from __future__ import annotations

import numpy as np

from src.utils.helpers import clamp

from .encoder import SimilarityBackend


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(np.dot(a, b) / (na * nb)) if na and nb else 0.0


def calibrate(raw: float, low: float, high: float) -> float:
    """Reescala la similitud cruda: ``low`` (o menos) → 0, ``high`` (o más) → 1.
    El coseno crudo rara vez llega a 1 aunque el CV encaje bien."""
    if high <= low:
        raise ValueError("high debe ser mayor que low")
    return clamp((raw - low) / (high - low))


def semantic_similarity(cv_text: str, job_text: str, backend: SimilarityBackend) -> tuple[float, float]:
    """Devuelve (similitud calibrada 0-1, similitud cruda)."""
    raw = backend.raw_similarity(cv_text, job_text)
    return calibrate(raw, backend.low, backend.high), raw
