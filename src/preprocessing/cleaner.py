"""Normalización del texto extraído de PDFs/DOCX."""

from __future__ import annotations

import re
import unicodedata

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​‌‍﻿]")
_BULLETS = re.compile(r"^[\s]*[•●▪■◦·►➢✓✔*–—]+\s*", re.MULTILINE)


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _CONTROL.sub("", text)
    text = text.replace(" ", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # palabras cortadas por guion al final de línea
    text = _BULLETS.sub("- ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
