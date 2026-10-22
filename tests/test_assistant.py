import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from src.llm import GroqClient
from src.pipeline import AnalysisPipeline

from .conftest import make_pdf

SEEN: list[dict] = []


def handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    system, user = body["messages"][0]["content"], body["messages"][1]["content"]
    SEEN.append({"system": system, "user": user})
    if "Pick 4" in system or "Elige de 4" in system:
        out = {"items": [
            {"original": "Despliegue de Docker, Kubernetes y Terraform en Azure; pipelines con GitLab CI/CD y Jenkins",
             "rewritten": "Desplegué Docker, Kubernetes y Terraform en Azure y mejoré un 45% el tiempo de entrega con ArgoCD.",
             "keywords": ["Kubernetes", "Terraform"]},
            {"original": "Lideré un equipo de 50 personas en Marte", "rewritten": "Inventado", "keywords": []}]}
    elif "resumen de perfil" in system or "profile summary" in system:
        out = {"summary": "Ingeniera de sistemas con 10 años de experiencia en Docker, Kubernetes y Terraform."}
    elif "carta" in system or "cover letter" in system:
        out = {"letter": "Estimado equipo de selección:\nMe interesa el puesto.\nAna Ejemplo"}
    else:
        out = {"questions": [{"question": "¿Has usado Helm?", "why": "Lo pide la oferta.", "tip": "Sé honesta."}]}
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(out)}}]})


@pytest.fixture(scope="module")
def ai_pipeline(settings):
    client = GroqClient("k", "m", max_retries=0, transport=httpx.MockTransport(handler))
    return AnalysisPipeline(settings, llm_client=client)


@pytest.fixture
def client(settings, ai_pipeline):
    return TestClient(create_app(settings, ai_pipeline), raise_server_exceptions=False)


def call(client, cv_text, job_text, **data):
    return client.post("/api/v1/assist", files={"cv_file": ("cv.pdf", make_pdf(cv_text), "application/pdf")},
                       data={"job_text": job_text, **data})


def test_consent_is_required(client, cv_text, job_text):
    SEEN.clear()
    r = call(client, cv_text, job_text)
    assert r.status_code == 400 and r.json()["error"]["code"] == "consent_required"
    assert call(client, cv_text, job_text, consent="false").status_code == 400
    assert not SEEN  # sin consentimiento no sale nada hacia Groq


def test_unavailable_without_llm(settings, pipeline, cv_text, job_text):
    c = TestClient(create_app(settings, pipeline), raise_server_exceptions=False)
    r = call(c, cv_text, job_text, consent="true")
    assert r.status_code == 503 and r.json()["error"]["code"] == "llm_unavailable"


def test_bad_task_is_422(client, cv_text, job_text):
    r = call(client, cv_text, job_text, consent="true", tasks="rewrite,hack")
    assert r.status_code == 422 and r.json()["error"]["code"] == "bad_task"


def test_all_tasks_and_guards(client, cv_text, job_text):
    SEEN.clear()
    r = call(client, cv_text, job_text, consent="true")
    assert r.status_code == 200
    res = r.json()["results"]
    assert set(res) == {"rewrite", "summary", "cover", "interview"}
    # viñeta inventada descartada; la real se mantiene y se avisa de lo que el CV no respalda
    items = res["rewrite"]["items"]
    assert len(items) == 1 and "Marte" not in items[0]["original"]
    assert "45" in items[0]["check"]["numbers"] and "ArgoCD" in items[0]["check"]["skills"]
    # «10 años» sí está en el CV; Docker/Kubernetes/Terraform también: sin avisos
    assert res["summary"]["check"] == {"skills": [], "numbers": []}
    assert res["cover"]["text"].startswith("Estimado") and res["interview"]["questions"][0]["question"]
    # el CV y la oferta van como datos delimitados y el prompt prohíbe inventar
    assert all("<cv>" in s["user"] and "<job>" in s["user"] and "no inventes" in s["system"] for s in SEEN)


def test_single_task_and_isolated_failure(settings, cv_text, job_text):
    def flaky(request):
        if "carta" in json.loads(request.content)["messages"][0]["content"]:
            return httpx.Response(401)
        return handler(request)
    p = AnalysisPipeline(settings, llm_client=GroqClient("k", "m", max_retries=0, transport=httpx.MockTransport(flaky)))
    out = p.assist(cv_text, job_text, ["cover", "summary"])["results"]
    assert "error" in out["cover"] and out["summary"]["text"]


def test_garbled_output_gives_friendly_error(settings, cv_text, job_text):
    bad = lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "[1,2]"}}]})  # noqa: E731
    p = AnalysisPipeline(settings, llm_client=GroqClient("k", "m", max_retries=0, transport=httpx.MockTransport(bad)))
    assert "formato" in p.assist(cv_text, job_text, ["summary"])["results"]["summary"]["error"]
