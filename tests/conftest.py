"""Fixtures compartidas. Los archivos de prueba se generan en memoria (sin CVs reales)."""

from __future__ import annotations

import io
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import Settings  # noqa: E402
from src.pipeline import AnalysisPipeline  # noqa: E402

CV_TEXT = """Ana Ejemplo
Ingeniera de sistemas

Perfil
Ingeniera de sistemas con más de 10 años de experiencia en infraestructura y cloud. Orientada a DevOps.

Experiencia
Administradora de Sistemas - Empresa A (ene 2014 - dic 2019)
- Gestión de 120 servidores Linux y Windows Server, VMware y Active Directory
- Automatización con Bash y PowerShell; reducción del 30% de incidencias
Ingeniera de Infraestructura - Empresa B (2020 - actualidad)
- Despliegue de Docker, Kubernetes y Terraform en Azure; pipelines con GitLab CI/CD y Jenkins
- Monitorización con Prometheus y Grafana, backups con Veeam

Formación
Ingeniería de Sistemas, Universidad X (2004 - 2009)
Máster en Ciberseguridad (2012)

Habilidades
Linux, Docker, Kubernetes, Terraform, Ansible, Python, Azure, Git, Networking, Cisco, VPN

Idiomas
Español: nativo
Inglés: B2
"""

JOB_TEXT = """DevOps Engineer - Remoto

Requisitos:
- 5 años de experiencia en entornos cloud (AWS o Azure)
- Docker, Kubernetes y Terraform
- CI/CD con GitHub Actions o Jenkins
- Scripting en Python o Bash
- Inglés nivel B2
- Grado en Ingeniería Informática o similar

Se valorará:
- Certificación CKA, Helm, ArgoCD, Prometheus

Qué ofrecemos:
- Trabajo remoto con Go y Rust
"""

JOB_MISMATCH = """Desarrollador Frontend React
Requisitos:
- 4 años de experiencia con React, TypeScript, HTML y CSS
- Conocimientos de Angular y Vue
- Inglés C1
Se valorará:
- Cypress, GraphQL
"""


def make_docx(text: str) -> bytes:
    from docx import Document

    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_pdf(text: str) -> bytes:
    """PDF mínimo válido (Helvetica, una página) sin dependencias externas."""
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    lines = [esc(ln.encode("latin-1", "replace").decode("latin-1")) for ln in text.split("\n")][:60]
    content = "BT /F1 9 Tf 40 800 Td 11 TL\n" + "\n".join(f"({ln}) Tj T*" for ln in lines) + "\nET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


@pytest.fixture(scope="session")
def settings() -> Settings:
    # Sin clave de Groq ni .env: los tests nunca llaman a servicios externos.
    return Settings(groq_api_key="", llm_enabled=False, rate_limit_per_minute=0, enable_ui=False,
                    history_enabled=False)


@pytest.fixture(scope="session")
def pipeline(settings: Settings) -> AnalysisPipeline:
    return AnalysisPipeline(settings)


@pytest.fixture
def cv_text() -> str:
    return CV_TEXT


@pytest.fixture
def job_text() -> str:
    return JOB_TEXT


@pytest.fixture
def job_mismatch() -> str:
    return JOB_MISMATCH


@pytest.fixture
def make_settings(settings: Settings):
    def _make(**changes) -> Settings:
        return replace(settings, **changes)
    return _make
