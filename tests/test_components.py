from app.components import EXAMPLE_JOB, error_html, format_date, history_rows, render_results, seen_banner


def fake_result(pipeline, cv_text, job_text, **over):
    r = pipeline.analyze(cv_text, job_text, use_llm=False, remember=False)
    r.update(over)
    return r


def test_render_has_all_sections(pipeline, cv_text, job_text):
    html = render_results(fake_result(pipeline, cv_text, job_text))
    for needle in ("cvm-gauge", "Resumen rápido", "Perfil de compatibilidad", "<svg", "Fortalezas destacadas",
                   "Cobertura por área", "Palabras clave", "Tu trayectoria detectada",
                   "Recomendaciones personalizadas", "Qué he entendido"):
        assert needle in html


def test_everything_dynamic_is_escaped(pipeline, cv_text, job_text):
    r = fake_result(pipeline, cv_text, job_text)
    r["skills"]["missing_required"] = ["<script>alert(1)</script>"]
    r["advice"]["recommendations"] = ["<img src=x onerror=alert(1)>"]
    r["seen_before"] = {"exact": True, "times": 2, "last_seen": "2026-10-01T10:00:00+00:00",
                        "last_score": 70.0, "title": "<b>Hack</b>", "similarity": 1.0}
    html = render_results(r)
    assert "<script>" not in html and "<img src=x" not in html and "<b>Hack</b>" not in html
    assert "&lt;script&gt;" in html


def test_seen_banner_variants():
    base = {"last_seen": "2026-10-01T10:00:00+00:00", "last_score": 71.4, "title": "SRE", "similarity": 1.0}
    assert seen_banner({"seen_before": None, "job_id": None}) == ""
    assert "Oferta nueva" in seen_banner({"seen_before": None, "job_id": "abc"})
    exact = seen_banner({"seen_before": {**base, "exact": True, "times": 3}})
    assert "Ya viste esta oferta" in exact and "3 veces" in exact and "71/100" in exact
    near = seen_banner({"seen_before": {**base, "exact": False, "times": 1, "similarity": 0.87}})
    assert "Muy parecida" in near and "87 %" in near


def test_inapplicable_components_render_as_dash(pipeline, cv_text):
    html = render_results(fake_result(pipeline, cv_text, "Admin Linux\nRequisitos:\n- Linux y Docker avanzados en producción"))
    assert "cvm-qna" in html and "n/a" in html   # bloques que no aplican: atenuados y "n/a" en el radar


def test_history_rows_and_helpers():
    rows = history_rows([{"last_seen": "2026-10-01T10:00:00+00:00", "title": "SRE", "last_score": 71.6, "times": 2}])
    assert rows[0][1:] == ["SRE", 72, 2]
    assert format_date("no-es-fecha") == "no-es-fecha"
    assert "Error" in error_html("Error <x>") and "<x>" not in error_html("Error <x>")
    assert "Requisitos" in EXAMPLE_JOB


def test_timeline_and_titles_are_escaped(pipeline, cv_text, job_text):
    r = fake_result(pipeline, cv_text, job_text)
    r["cv_profile"]["timeline"] = [{"title": "<script>x</script>", "period": "2020 – actualidad",
                                    "years": 6.0, "skills": ["<b>Docker</b>"]}]
    html = render_results(r)
    assert "<script>x" not in html and "<b>Docker</b>" not in html and "6 años" in html


def test_empty_data_still_renders(pipeline, cv_text):
    r = fake_result(pipeline, cv_text, "Puesto genérico de oficina\nSe requiere puntualidad y buena actitud.")
    r["cv_profile"]["timeline"] = []
    html = render_results(r)
    assert "No detecté periodos" in html and "no menciona habilidades reconocibles" in html
