import pytest
from fastapi.testclient import TestClient

from app.api import create_app

from .conftest import make_docx, make_pdf


@pytest.fixture
def client(settings, pipeline):
    return TestClient(create_app(settings, pipeline), raise_server_exceptions=False)


def post(client, cv=("cv.txt", b"", "text/plain"), job_text=None, **extra):
    files = {"cv_file": cv}
    data = {"use_llm": "false", **extra}
    if job_text is not None:
        data["job_text"] = job_text
    return client.post("/api/v1/analyze", files=files, data=data)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-request-id"]


@pytest.mark.parametrize("kind", ["txt", "docx", "pdf"])
def test_analyze_ok_all_formats(client, cv_text, job_text, kind):
    payload = {"txt": cv_text.encode(), "docx": make_docx(cv_text), "pdf": make_pdf(cv_text)}[kind]
    r = post(client, (f"cv.{kind}", payload, "application/octet-stream"), job_text)
    assert r.status_code == 200, r.text
    body = r.json()
    assert 0 <= body["score"] <= 100 and len(body["components"]) == 5
    assert body["advice"]["source"] == "rules"
    assert r.headers["cache-control"] == "no-store"


def test_job_as_file(client, cv_text, job_text):
    r = client.post("/api/v1/analyze", data={"use_llm": "false"},
                    files={"cv_file": ("cv.txt", cv_text.encode(), "text/plain"),
                           "job_file": ("oferta.txt", job_text.encode(), "text/plain")})
    assert r.status_code == 200


def test_missing_cv_is_422(client, job_text):
    r = client.post("/api/v1/analyze", data={"job_text": job_text})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_missing_or_short_or_long_job(client, cv_text, settings):
    cv = ("cv.txt", cv_text.encode(), "text/plain")
    assert post(client, cv).json()["error"]["code"] == "job_missing"
    assert post(client, cv, "corta").json()["error"]["code"] == "job_too_short"
    r = post(client, cv, "x" * (settings.max_job_chars + 1))
    assert r.status_code == 413 and r.json()["error"]["code"] == "job_too_long"


def test_rejects_bad_files(client, job_text):
    r = post(client, ("virus.exe", b"MZ" + b"\x00" * 200, "application/octet-stream"), job_text)
    assert r.status_code == 415
    r = post(client, ("cv.pdf", b"no soy un pdf " * 20, "application/pdf"), job_text)
    assert r.status_code == 415 and r.json()["error"]["code"] == "content_mismatch"
    r = post(client, ("cv.txt", b"", "text/plain"), job_text)
    assert r.status_code == 400


def test_upload_too_large(settings, pipeline, make_settings, job_text):
    s = make_settings(max_upload_mb=1)
    c = TestClient(create_app(s, pipeline), raise_server_exceptions=False)
    r = post(c, ("cv.txt", b"a" * (1024 * 1024 + 10), "text/plain"), job_text)
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"


def test_oversized_request_rejected_early(settings, pipeline, make_settings):
    s = make_settings(max_upload_mb=1, max_job_chars=100)
    c = TestClient(create_app(s, pipeline), raise_server_exceptions=False)
    r = c.post("/api/v1/analyze", content=b"x", headers={"content-length": str(50 * 1024 * 1024),
                                                         "content-type": "multipart/form-data; boundary=a"})
    assert r.status_code == 413


def test_api_key_required_when_configured(settings, pipeline, make_settings, cv_text, job_text):
    c = TestClient(create_app(make_settings(api_key="secreto"), pipeline), raise_server_exceptions=False)
    cv = ("cv.txt", cv_text.encode(), "text/plain")
    assert post(c, cv, job_text).status_code == 401
    ok = c.post("/api/v1/analyze", files={"cv_file": cv}, data={"job_text": job_text, "use_llm": "false"},
                headers={"X-API-Key": "secreto"})
    assert ok.status_code == 200
    assert c.get("/health").status_code == 200  # el health check sigue abierto


def test_rate_limit(settings, pipeline, make_settings, cv_text, job_text):
    c = TestClient(create_app(make_settings(rate_limit_per_minute=2), pipeline), raise_server_exceptions=False)
    cv = ("cv.txt", cv_text.encode(), "text/plain")
    codes = [post(c, cv, job_text).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_cors_only_for_allowed_origins(settings, pipeline, make_settings):
    c = TestClient(create_app(make_settings(cors_origins=("http://ok.test",)), pipeline))
    good = c.get("/health", headers={"Origin": "http://ok.test"})
    bad = c.get("/health", headers={"Origin": "http://evil.test"})
    assert good.headers.get("access-control-allow-origin") == "http://ok.test"
    assert "access-control-allow-origin" not in bad.headers


def test_unexpected_error_hides_details(settings, pipeline, cv_text, job_text, monkeypatch):
    c = TestClient(create_app(settings, pipeline), raise_server_exceptions=False)
    monkeypatch.setattr(pipeline, "analyze", lambda *a, **k: 1 / 0)
    r = post(c, ("cv.txt", cv_text.encode(), "text/plain"), job_text)
    assert r.status_code == 500
    assert "division" not in r.text and r.json()["error"]["code"] == "internal_error"


def test_extract_and_skills_endpoints(client, cv_text):
    r = client.post("/api/v1/cv/extract", files={"cv_file": ("cv.txt", cv_text.encode(), "text/plain")})
    assert r.status_code == 200 and "Docker" in r.json()["skills"]
    s = client.get("/api/v1/skills", params={"q": "kube"})
    assert "Kubernetes" in [x["name"] for x in s.json()]


def test_ui_served_with_strict_csp(settings, pipeline, make_settings):
    from dataclasses import replace
    c = TestClient(create_app(replace(settings, enable_ui=True), pipeline), raise_server_exceptions=False)
    r = c.get("/app/")
    assert r.status_code == 200 and "CV Matcher" in r.text
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp and "frame-ancestors 'none'" in csp
    assert c.get("/app/app.js").status_code == 200 and c.get("/app/style.css").status_code == 200
    assert "innerHTML" not in c.get("/app/app.js").text  # todo texto dinámico va con textContent
    assert c.get("/", follow_redirects=False).headers["location"] == "/app/"


def test_health_reports_auth_and_weights(settings, pipeline, make_settings):
    c = TestClient(create_app(make_settings(api_key="k"), pipeline), raise_server_exceptions=False)
    body = c.get("/health").json()
    assert body["auth_required"] is True and abs(sum(body["weights"].values()) - 1) < 1e-6


def test_analyze_returns_category_coverage(client, cv_text, job_text):
    cv = ("cv.txt", cv_text.encode(), "text/plain")
    assert post(client, cv, job_text).json()["skills"]["by_category"]
