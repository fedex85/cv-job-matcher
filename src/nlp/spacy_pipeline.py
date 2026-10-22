"""Carga *opcional* de spaCy.

El matching actual no depende de spaCy (usa diccionario + reglas, que son más
rápidas y explicables). Este módulo deja preparado el punto de extensión por si
se quiere añadir reconocimiento de entidades; devuelve None si spaCy o el
modelo no están instalados.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from src.utils.logger import get_logger

log = get_logger(__name__)


@lru_cache(maxsize=2)
def load_spacy(model: str = "es_core_news_md") -> Any | None:
    try:
        import spacy

        return spacy.load(model)
    except Exception as exc:  # ImportError u OSError (modelo no descargado)
        log.info("spaCy no disponible (%s): se continúa sin él.", type(exc).__name__)
        return None
