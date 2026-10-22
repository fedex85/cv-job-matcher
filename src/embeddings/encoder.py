"""Motores de similitud. Por defecto TF-IDF (sin descargas, funciona offline);
opcionalmente embeddings multilingües de sentence-transformers."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Protocol

import numpy as np

from src.utils.logger import get_logger

log = get_logger(__name__)

_STOP_ES = [
    "de", "la", "el", "en", "y", "los", "las", "del", "con", "para", "por", "una", "un", "se", "que",
    "como", "al", "su", "sus", "lo", "es", "son", "o", "a", "e", "u", "más", "mas", "sobre", "entre",
    "nuestro", "nuestra", "tu", "te", "le", "este", "esta", "ser", "si", "no", "también", "tambien",
    "ha", "han", "hemos", "he", "muy", "pero", "sin", "desde", "hasta", "durante", "años", "anos",
]


class SimilarityBackend(Protocol):
    name: str
    low: float   # similitud cruda que se considera "sin relación" (→ 0)
    high: float  # similitud cruda que se considera "muy relacionado" (→ 1)

    def raw_similarity(self, cv_text: str, job_text: str) -> float: ...


def split_chunks(text: str, min_len: int = 25, max_chunks: int = 80) -> list[str]:
    parts = [p.strip(" -\t") for p in re.split(r"\n+", text)]
    chunks = [p for p in parts if len(p) >= min_len]
    return (chunks or [text])[:max_chunks]


class TfidfBackend:
    """Coseno TF-IDF (unigramas y bigramas). El IDF se aprende sobre las líneas de
    ambos textos para que términos genéricos pesen poco."""

    name = "tfidf"
    low, high = 0.05, 0.45

    def raw_similarity(self, cv_text: str, job_text: str) -> float:
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

        stop = list(ENGLISH_STOP_WORDS) + _STOP_ES
        vec = TfidfVectorizer(
            ngram_range=(1, 2), sublinear_tf=True, strip_accents="unicode", lowercase=True,
            stop_words=stop, token_pattern=r"(?u)\b[\w#+.]{2,}\b",
        )
        corpus = split_chunks(cv_text, 10) + split_chunks(job_text, 10)
        try:
            vec.fit(corpus)
            m = vec.transform([cv_text, job_text])
        except ValueError:  # vocabulario vacío
            return 0.0
        a, b = m[0], m[1]
        denom = np.sqrt(a.multiply(a).sum()) * np.sqrt(b.multiply(b).sum())
        return float(a.multiply(b).sum() / denom) if denom else 0.0


class SentenceTransformerBackend:
    """Embeddings multilingües. Cada requisito de la oferta se empareja con el
    fragmento más parecido del CV y se promedia (cobertura semántica)."""

    name = "sentence-transformers"
    low, high = 0.20, 0.65

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = _load_st_model(model_name)

    def raw_similarity(self, cv_text: str, job_text: str) -> float:
        cv_chunks, job_chunks = split_chunks(cv_text), split_chunks(job_text)
        emb = self._model.encode(cv_chunks + job_chunks, normalize_embeddings=True, show_progress_bar=False)
        cv_e, job_e = emb[: len(cv_chunks)], emb[len(cv_chunks):]
        sims = job_e @ cv_e.T
        return float(np.mean(np.max(sims, axis=1)))


@lru_cache(maxsize=1)
def _load_st_model(model_name: str):  # pragma: no cover - requiere descargar el modelo
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def build_backend(kind: str, model_name: str) -> SimilarityBackend:
    """Crea el motor pedido; si no se puede, vuelve a TF-IDF avisando en el log."""
    if kind == "sentence-transformers":
        try:
            return SentenceTransformerBackend(model_name)
        except Exception as exc:  # ImportError, sin red para descargar el modelo...
            log.warning("No se pudo cargar sentence-transformers (%s); se usa TF-IDF.", type(exc).__name__)
    return TfidfBackend()
