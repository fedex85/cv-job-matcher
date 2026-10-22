import io
import zipfile

import pytest

from src.ingestion import IngestionError, load_document
from src.preprocessing import clean_text, split_sections

from .conftest import make_docx, make_pdf


def test_txt_ok(settings, cv_text):
    doc = load_document("cv.txt", cv_text.encode("utf-8"), settings)
    assert doc.kind == "txt" and "Kubernetes" in doc.text


def test_docx_ok(settings, cv_text):
    doc = load_document("cv.docx", make_docx(cv_text), settings)
    assert doc.kind == "docx" and "Terraform" in doc.text


def test_pdf_ok(settings, cv_text):
    doc = load_document("cv.pdf", make_pdf(cv_text), settings)
    assert doc.kind == "pdf" and doc.pages == 1
    assert "Kubernetes" in doc.text


@pytest.mark.parametrize("name", ["cv.exe", "cv", "cv.png", "cv.pdf.exe"])
def test_extension_rejected(settings, name):
    with pytest.raises(IngestionError) as e:
        load_document(name, b"hola mundo " * 20, settings)
    assert e.value.status_code == 415


def test_content_must_match_extension(settings):
    # un ejecutable renombrado a .pdf
    with pytest.raises(IngestionError) as e:
        load_document("cv.pdf", b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 200, settings)
    assert e.value.code == "content_mismatch"
    # texto plano con extensión .docx
    with pytest.raises(IngestionError) as e:
        load_document("cv.docx", b"texto plano " * 30, settings)
    assert e.value.code == "content_mismatch"


def test_empty_and_too_large(settings, make_settings):
    with pytest.raises(IngestionError) as e:
        load_document("cv.txt", b"", settings)
    assert e.value.status_code == 400
    small = make_settings(max_upload_mb=1)
    with pytest.raises(IngestionError) as e:
        load_document("cv.txt", b"a" * (1024 * 1024 + 1), small)
    assert e.value.status_code == 413


def test_scanned_pdf_without_text(settings):
    with pytest.raises(IngestionError) as e:
        load_document("cv.pdf", make_pdf(" "), settings)
    assert e.value.code == "no_text"


def test_pdf_too_many_pages(make_settings, cv_text):
    with pytest.raises(IngestionError) as e:
        load_document("cv.pdf", make_pdf(cv_text), make_settings(max_pdf_pages=1, max_text_chars=10))
    assert e.value.status_code == 413  # demasiado texto


def test_corrupt_pdf(settings):
    with pytest.raises(IngestionError) as e:
        load_document("cv.pdf", b"%PDF-1.4\n" + b"basura" * 50, settings)
    assert e.value.code in {"corrupt_pdf", "no_text"}


def test_docx_zip_bomb(settings):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", "<w/>")
        zf.writestr("relleno.bin", b"\x00" * (60 * 1024 * 1024))  # comprime a unos KB
    assert len(buf.getvalue()) < settings.max_upload_bytes
    with pytest.raises(IngestionError) as e:
        load_document("cv.docx", buf.getvalue(), settings)
    assert e.value.code == "unsafe_docx"


def test_cleaner_and_sections(cv_text):
    cleaned = clean_text("Admin sis-\ntemas  \x00\n\n\n\n• Linux")
    assert "sistemas" in cleaned and "\x00" not in cleaned and "\n\n\n" not in cleaned
    sections = split_sections(cv_text)
    assert {"experience", "education", "skills", "languages"} <= set(sections)
    assert "Terraform" in sections["skills"]


def test_encrypted_pdf_message(settings, monkeypatch, cv_text):
    from pdfminer.pdfdocument import PDFPasswordIncorrect

    def boom(*a, **k):
        raise PDFPasswordIncorrect()

    monkeypatch.setattr("pdfplumber.open", boom)
    with pytest.raises(IngestionError) as e:
        load_document("cv.pdf", make_pdf(cv_text), settings)
    assert e.value.code == "encrypted_pdf"
