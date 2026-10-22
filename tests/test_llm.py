import json

import httpx
import pytest

from src.llm import Advisor, GroqClient, LLMError


def make_client(handler, **kw):
    return GroqClient("test-key", "m", max_retries=kw.pop("max_retries", 1),
                      transport=httpx.MockTransport(handler), **kw)


def ok_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    assert request.headers["authorization"] == "Bearer test-key"
    assert body["response_format"] == {"type": "json_object"}
    # el prompt solo lleva datos estructurados, nunca el texto del CV
    assert "<analysis>" in body["messages"][1]["content"]
    content = json.dumps({"summary": "Buen encaje.", "recommendations": ["Añade AWS", "  ", 5, "Cuantifica logros"]})
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def _match(pipeline, cv_text, job_text):
    cv, _ = pipeline.build_cv_profile(cv_text, {})
    job = pipeline.build_job_profile(job_text)
    return pipeline.scorer.score(cv, job, 0.5)


def test_llm_success_is_sanitized(pipeline, cv_text, job_text):
    adv = Advisor(make_client(ok_handler)).advise(_match(pipeline, cv_text, job_text), ["regla"], "es", True)
    assert adv.source == "llm" and adv.recommendations == ["Añade AWS", "Cuantifica logros"]


def test_falls_back_to_rules_on_failure(pipeline, cv_text, job_text, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    client = make_client(lambda r: httpx.Response(503))
    adv = Advisor(client).advise(_match(pipeline, cv_text, job_text), ["regla 1"], "es", True)
    assert adv.source == "rules" and adv.recommendations == ["regla 1"] and adv.llm_error


def test_invalid_key_and_bad_format(pipeline, cv_text, job_text):
    with pytest.raises(LLMError):
        make_client(lambda r: httpx.Response(401)).chat_json("s", "u")
    bad = make_client(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "no es json"}}]}))
    adv = Advisor(bad).advise(_match(pipeline, cv_text, job_text), ["regla"], "es", True)
    assert adv.source == "rules"


def test_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = {"n": 0}

    def flaky(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429)
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    assert make_client(flaky).chat_json("s", "u") == "{}" and calls["n"] == 2


def test_disabled_llm_uses_rules(pipeline, cv_text, job_text):
    adv = Advisor(None).advise(_match(pipeline, cv_text, job_text), ["a", "b"], "es", True)
    assert adv.source == "rules"


def test_missing_key_raises():
    with pytest.raises(LLMError):
        GroqClient("", "m")
