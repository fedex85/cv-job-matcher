import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from src.history import JobHistory
from src.history.store import extract_title, fingerprint, minhash, similarity
from src.pipeline import AnalysisPipeline


@pytest.fixture
def hist(tmp_path):
    return JobHistory(tmp_path / "h.db")


def test_exact_repeat_is_detected(hist, job_text):
    job_id, prev = hist.record(job_text, 70.0, "high")
    assert prev is None and job_id == fingerprint(job_text)
    _, prev = hist.record(job_text, 75.5, "high")
    assert prev["exact"] and prev["times"] == 1 and prev["last_score"] == 70.0
    assert hist.list()[0]["times"] == 2 and hist.list()[0]["last_score"] == 75.5


def test_formatting_changes_still_exact(hist, job_text):
    hist.record(job_text, 70.0, "high")
    shouted = "  " + job_text.upper().replace("\n", "\n\n") + "  "
    assert hist.lookup(shouted)["exact"]


def test_near_duplicate_detected_but_not_exact(hist, job_text):
    hist.record(job_text, 70.0, "high")
    edited = job_text.replace("Remoto", "Híbrido en Madrid")
    seen = hist.lookup(edited)
    assert seen and not seen["exact"] and seen["similarity"] >= 0.8


def test_different_offer_not_matched(hist, job_text, job_mismatch):
    hist.record(job_text, 70.0, "high")
    assert hist.lookup(job_mismatch) is None


def test_minhash_is_deterministic(job_text):
    assert minhash(job_text) == minhash(job_text)
    assert similarity(minhash(job_text), minhash(job_text)) == 1.0


def test_list_delete_clear_and_cap(tmp_path, job_text, job_mismatch):
    h = JobHistory(tmp_path / "h.db", max_entries=1)
    h.record(job_text, 1, "low")
    h.record(job_mismatch, 2, "low")
    items = h.list()
    assert len(items) == 1 and items[0]["title"].startswith("Desarrollador Frontend")
    assert h.delete(items[0]["id"]) and not h.delete("nope")
    h.record(job_text, 1, "low")
    assert h.clear() == 1 and h.list() == []


def test_disabled_history_is_inert(job_text):
    h = JobHistory(None)
    assert not h.enabled and h.record(job_text, 1, "low") == (None, None)
    assert h.lookup(job_text) is None and h.list() == [] and h.clear() == 0


def test_only_offer_metadata_is_stored(tmp_path, job_text):
    h = JobHistory(tmp_path / "h.db")
    h.record(job_text, 70.0, "high")
    raw = (tmp_path / "h.db").read_bytes()
    assert b"DevOps Engineer" in raw          # el título sí
    assert b"ArgoCD" not in raw and b"GitHub Actions" not in raw  # el cuerpo no


def test_extract_title():
    assert extract_title("\n\n- Senior SRE (Remoto)\nresto") == "Senior SRE (Remoto)"
    assert extract_title("   ") == "(sin título)"


@pytest.fixture
def hist_client(settings, tmp_path):
    from dataclasses import replace
    s = replace(settings, history_enabled=True, history_db_path=tmp_path / "api.db")
    return TestClient(create_app(s, AnalysisPipeline(s)), raise_server_exceptions=False)


def _analyze(client, cv_text, job_text, **extra):
    return client.post("/api/v1/analyze", data={"job_text": job_text, "use_llm": "false", **extra},
                       files={"cv_file": ("cv.txt", cv_text.encode(), "text/plain")})


def test_api_flags_repeated_offer_and_lists_history(hist_client, cv_text, job_text):
    first = _analyze(hist_client, cv_text, job_text).json()
    assert first["seen_before"] is None and first["job_id"]
    second = _analyze(hist_client, cv_text, job_text).json()
    assert second["seen_before"]["exact"] and second["seen_before"]["times"] == 1
    items = hist_client.get("/api/v1/history").json()
    assert len(items) == 1 and items[0]["times"] == 2


def test_api_remember_false_does_not_record(hist_client, cv_text, job_text):
    r = _analyze(hist_client, cv_text, job_text, remember_job="false").json()
    assert r["job_id"] is None
    assert hist_client.get("/api/v1/history").json() == []


def test_api_delete_history(hist_client, cv_text, job_text):
    job_id = _analyze(hist_client, cv_text, job_text).json()["job_id"]
    assert hist_client.delete(f"/api/v1/history/{job_id}").status_code == 200
    assert hist_client.delete(f"/api/v1/history/{job_id}").status_code == 404
    _analyze(hist_client, cv_text, job_text)
    assert hist_client.delete("/api/v1/history").json() == {"deleted": 1}


def test_boolean_form_fields_default_to_true_when_omitted(hist_client, cv_text, job_text):
    # Sin use_llm ni remember_job: deben valer True (no False por ausencia del campo)
    r = hist_client.post("/api/v1/analyze", data={"job_text": job_text},
                         files={"cv_file": ("cv.txt", cv_text.encode(), "text/plain")}).json()
    assert r["job_id"]  # remember_job asumido True
