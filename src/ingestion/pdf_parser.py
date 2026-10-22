"""Extracción de texto de PDF con pdfplumber (licencia MIT)."""

from __future__ import annotations

import io

from .errors import IngestionError


def parse_pdf(data: bytes, *, max_pages: int, max_chars: int) -> tuple[str, int]:
    """Devuelve (texto, nº de páginas). Lanza IngestionError ante PDFs problemáticos."""
    import pdfplumber
    from pdfminer.pdfdocument import PDFPasswordIncorrect

    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            n_pages = len(pdf.pages)
            if n_pages == 0:
                raise IngestionError("empty_pdf", "El PDF no contiene páginas.")
            if n_pages > max_pages:
                raise IngestionError(
                    "too_many_pages",
                    f"El PDF tiene {n_pages} páginas; el máximo permitido es {max_pages}.",
                    413,
                )
            chunks: list[str] = []
            total = 0
            for page in pdf.pages:
                text = page.extract_text() or ""
                chunks.append(text)
                total += len(text)
                if total > max_chars:
                    raise IngestionError(
                        "text_too_long",
                        f"El documento supera los {max_chars} caracteres de texto permitidos.",
                        413,
                    )
            return "\n".join(chunks), n_pages
    except IngestionError:
        raise
    except PDFPasswordIncorrect as exc:
        raise IngestionError(
            "encrypted_pdf", "El PDF está protegido con contraseña; sube una versión sin cifrar."
        ) from exc
    except Exception as exc:  # pdfminer lanza muchos tipos distintos con PDFs corruptos
        if type(exc).__name__ in {"PdfminerException", "PDFSyntaxError", "PSEOF", "PDFEncryptionError"}:
            msg = str(exc).lower()
            if "password" in msg or "encrypt" in msg:
                raise IngestionError(
                    "encrypted_pdf", "El PDF está protegido con contraseña; sube una versión sin cifrar."
                ) from exc
        raise IngestionError("corrupt_pdf", "No se pudo leer el PDF: el archivo parece dañado.") from exc
