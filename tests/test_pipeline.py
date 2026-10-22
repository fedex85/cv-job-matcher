

def test_end_to_end_good_match(pipeline, cv_text, job_text):
    r = pipeline.analyze(cv_text, job_text, use_llm=False)
    assert 65 <= r["score"] <= 100 and r["language"] == "es"
    assert {"Docker", "Kubernetes", "Terraform"} <= set(r["skills"]["matched"])
    assert r["skills"]["missing_nice"] == ["ArgoCD", "Helm"]
    assert r["cv_profile"]["years_experience"] > 10
    assert r["job_profile"]["required_years"] == 5.0
    assert r["advice"]["source"] == "rules" and r["tips"]
    assert abs(sum(c["effective_weight"] for c in r["components"]) - 1) < 1e-3


def test_mismatch_scores_lower_and_lists_gaps(pipeline, cv_text, job_text, job_mismatch):
    good = pipeline.analyze(cv_text, job_text, use_llm=False)["score"]
    bad = pipeline.analyze(cv_text, job_mismatch, use_llm=False)
    assert bad["score"] < good - 20
    assert {"React", "TypeScript"} <= set(bad["skills"]["missing_required"])
    assert any("React" in t for t in bad["tips"])


def test_english_job_gets_english_output(pipeline, cv_text):
    job = ("Senior DevOps Engineer\nRequirements:\n- 5 years of experience with AWS, Docker and Kubernetes\n"
           "- English fluent\nNice to have:\n- Terraform\n")
    r = pipeline.analyze(cv_text, job, use_llm=False)
    assert r["language"] == "en" and "match" in r["band_label"].lower()


def test_result_does_not_echo_cv_text(pipeline, cv_text, job_text):
    r = pipeline.analyze(cv_text, job_text, use_llm=False)
    assert "Ana Ejemplo" not in str(r)


def test_extract_cv(pipeline, cv_text):
    r = pipeline.extract_cv(cv_text)
    assert r["skills"]["Docker"] >= 1 and r["education_level"] == 3 and r["languages"]["en"] == 4


def test_many_missing_skills_are_grouped_in_tips(pipeline, cv_text, job_mismatch):
    tips = pipeline.analyze(cv_text, job_mismatch, use_llm=False, remember=False)["tips"]
    individual = [t for t in tips if t.startswith("Falta «")]
    assert len(individual) == 3 and any("tecnologías que no aparecen" in t for t in tips)


def test_category_coverage_and_timeline(pipeline, cv_text, job_text):
    r = pipeline.analyze(cv_text, job_text, use_llm=False, remember=False)
    cats = {c["category"]: c for c in r["skills"]["by_category"]}
    assert cats["containers"]["covered_pct"] == 67 and cats["containers"]["total"] == 3  # Docker, K8s sí; Helm no
    assert all(0 <= c["covered_pct"] <= 100 for c in cats.values())
    tl = r["cv_profile"]["timeline"]
    assert len(tl) == 2 and tl[0]["period"].endswith("actualidad")


def test_ats_checks_on_good_cv(pipeline, cv_text, job_text):
    ats = pipeline.analyze(cv_text, job_text, use_llm=False, remember=False)["ats"]
    assert 0 <= ats["score"] <= 100 and ats["checks"] and {c["status"] for c in ats["checks"]} <= {"ok", "warn", "bad"}
    ids = {c["id"] for c in ats["checks"]}
    assert {"email", "experience", "dates", "keywords"} <= ids


def test_ats_flags_missing_contact_and_sections(pipeline, job_text):
    from src.matching.ats import check_ats
    cv = "Trabajo con muchas cosas.\n" * 5
    res = pipeline.scorer.score(*_dummy(pipeline, cv, job_text))
    ats = check_ats(cv, job_text, {}, res, "es")
    by = {c["id"]: c["status"] for c in ats["checks"]}
    assert by["email"] == "bad" and by["experience"] == "bad" and by["length"] == "bad"
    assert ats["band"] == "bad" and ats["checks"][0]["status"] == "bad"


def _dummy(pipeline, cv, job):
    from src.embeddings import semantic_similarity
    from src.preprocessing import split_sections
    cvp, _ = pipeline.build_cv_profile(cv, split_sections(cv))
    jp = pipeline.build_job_profile(job)
    sem, _ = semantic_similarity(cv, job, pipeline.backend)
    return cvp, jp, sem


def test_ats_odd_symbols_and_columns():
    from src.matching.ats import _odd_ratio, _short_line_ratio
    assert _odd_ratio("Python 😀📧☎ Docker ✆✉") > 0.1 and _odd_ratio("Python • Docker – AWS") == 0
    assert _short_line_ratio("\n".join(["a b"] * 20)) == 1.0 and _short_line_ratio("a b\nc") == 0.0
