"""Descarga (opcional) el modelo de embeddings multilingüe para EMBEDDING_BACKEND=sentence-transformers.

Uso:  python scripts/download_models.py
Requiere:  pip install -r requirements-ml.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import load_settings  # noqa: E402


def main() -> int:
    settings = load_settings()
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("Falta sentence-transformers. Ejecuta: pip install -r requirements-ml.txt")
        return 1
    print(f"Descargando {settings.embedding_model} ...")
    SentenceTransformer(settings.embedding_model)
    print("Listo. Define EMBEDDING_BACKEND=sentence-transformers en tu .env para usarlo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
