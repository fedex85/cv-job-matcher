"""Punto de entrada.

    python main.py                       # arranca la API (y la UI en /ui)
    uvicorn main:app --reload            # modo desarrollo
"""

from __future__ import annotations

from app.api import create_app
from src.config import get_settings

app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())
