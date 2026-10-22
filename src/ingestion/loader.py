"""Carga y validación de documentos subidos. Todo se procesa en memoria: los CVs
nunca se escriben en disco (minimización de datos, RGPD)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath

from src.config import Settings

from .docx_parser import is_docx, parse_docx
from .errors import IngestionError
from .pdf_parser import parse_pdf

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MIN_TEXT_CHARS = 80


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    kind: str  # "pdf" | "docx" | "txt"
    pages: int | None = None


def _sniff(data: bytes) -> str | None:
    """Tipo real según el contenido."""
    if data[:5] == b"%PDF-":
        return "pdf"
    if is_docx(data):
        return "docx"
    if b"\x00" in data[:4096]:
        return None  # binario desconocido
    try:
        data[:200_000].decode("utf-8")
        return "txt"
    except UnicodeDecodeError:
        try:
            data[:200_000].decode("cp1252")
            return "txt"
        except UnicodeDecodeError:
            return None


def load_document(filename: str | None, data: bytes, settings: Settings) -> ParsedDocument:
    """Valida (extensión, tamaño, contenido real) y extrae el texto."""
    name = PurePath(filename or "").name
    ext = PurePath(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise IngestionError(
            "unsupported_type", "Formato no admitido. Sube un archivo PDF, DOCX o TXT.", 415
        )
    if not data:
        raise IngestionError("empty_file", "El archivo está vacío.", 400)
    if len(data) > settings.max_upload_bytes:
        raise IngestionError(
            "file_too_large", f"El archivo supera el máximo de {settings.max_upload_mb} MB.", 413
        )

    kind = _sniff(data)
    if kind is None or f".{kind}" != ext:
        raise IngestionError(
            "content_mismatch", "El contenido del archivo no coincide con su extensión.", 415
        )

    pages: int | None = None
    if kind == "pdf":
        text, pages = parse_pdf(data, max_pages=settings.max_pdf_pages, max_chars=settings.max_text_chars)
    elif kind == "docx":
        text = parse_docx(data, max_chars=settings.max_text_chars)
    else:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("cp1252", errors="replace")
        if len(text) > settings.max_text_chars:
            raise IngestionError(
                "text_too_long", f"El texto supera los {settings.max_text_chars} caracteres.", 413
            )

    if len(text.strip()) < MIN_TEXT_CHARS:
        raise IngestionError(
            "no_text",
            "No se pudo extraer texto suficiente. Si es un PDF escaneado (imagen), "
            "sube una versión con texto seleccionable.",
        )
    return ParsedDocument(text=text, kind=kind, pages=pages)
