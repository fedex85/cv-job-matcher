import pytest

from src.matching import JobProfile, MatchScorer, band_for
from src.nlp.entity_extractor import CVProfile
from src.nlp.skill_extractor import get_skill_extractor

WEIGHTS = {"skills": 0.45, "semantic": 0.20, "experience": 0.15, "education": 0.10, "languages": 0.10}


@pytest.fixture(scope="module")
def scorer(settings):
    return MatchScorer(WEIGHTS, get_skill_extractor(str(settings.skills_db_path)))


def cv(**kw):
    base = dict(skills={"Docker": 1, "Python": 2}, years_experience=5.0, education_level=2,
                languages={"en": 4})
    base.update(kw)
    return CVProfile(**base)


def job(**kw):
    base = dict(required_skills={"Docker": 1, "Python": 1}, nice_skills={}, required_years=3.0,
                education_level=2, languages={"en": 4})
    base.update(kw)
    return JobProfile(**base)


def test_perfect_match_is_100(scorer):
    r = scorer.score(cv(), job(), semantic=1.0)
    assert r.total_score == 100.0 and r.band == "very_high" and r.missing_required == []


def test_effective_weights_sum_to_one(scorer):
    r = scorer.score(cv(), job(), semantic=0.5)
    assert sum(c.effective_weight for c in r.components) == pytest.approx(1.0, abs=1e-3)


def test_inapplicable_components_redistribute_weight(scorer):
    r = scorer.score(cv(), job(required_years=None, education_level=0, languages={}), semantic=0.0)
    applicable = {c.key for c in r.components if c.applicable}
    assert applicable == {"skills", "semantic"}
    skills = next(c for c in r.components if c.key == "skills")
    assert skills.effective_weight == pytest.approx(0.45 / 0.65, abs=1e-3)
    assert r.total_score == pytest.approx(100 * 0.45 / 0.65, abs=0.1)  # skills 100, semántica 0


def test_missing_required_skill_reduces_score(scorer):
    full = scorer.score(cv(), job(), 0.5).total_score
    missing = scorer.score(cv(skills={"Docker": 1}), job(), 0.5)
    assert missing.total_score < full and missing.missing_required == ["Python"]


def test_nice_skills_weigh_less_than_required(scorer):
    base = job(required_skills={"Docker": 1}, nice_skills={"Helm": 1})
    no_nice = scorer.score(cv(skills={"Docker": 1}), base, 0.5)
    no_req = scorer.score(cv(skills={"Helm": 1}), base, 0.5)
    assert no_nice.total_score > no_req.total_score
    assert no_nice.missing_nice == ["Helm"]


def test_partial_credit_same_family(scorer):
    r = scorer.score(cv(skills={"Azure": 1}), job(required_skills={"AWS": 1}), 0.5)
    sk = next(c for c in r.components if c.key == "skills")
    assert sk.score == 50.0 and r.partial_skills == [{"required": "AWS", "via": "Azure"}]


def test_alternatives_cover_group(scorer):
    r = scorer.score(cv(skills={"Azure": 1}),
                     job(required_skills={"AWS": 1, "Azure": 1}, alternatives=[["AWS", "Azure"]]), 0.5)
    assert next(c for c in r.components if c.key == "skills").score == 100.0


def test_experience_ratio_and_unknown(scorer):
    r = scorer.score(cv(years_experience=1.5), job(required_years=3.0), 0.5)
    assert next(c for c in r.components if c.key == "experience").score == 50.0
    unknown = scorer.score(cv(years_experience=0), job(required_years=3.0), 0.5)
    exp = next(c for c in unknown.components if c.key == "experience")
    assert exp.score == 50.0 and exp.detail["low_confidence"]


def test_education_and_language_gaps(scorer):
    r = scorer.score(cv(education_level=1, languages={"en": 2}), job(education_level=3, languages={"en": 4}), 0.5)
    assert next(c for c in r.components if c.key == "education").score == 0.0
    assert next(c for c in r.components if c.key == "languages").score == 50.0


def test_no_skills_in_job_warns(scorer):
    r = scorer.score(cv(), job(required_skills={}), 0.4)
    assert r.warnings and not next(c for c in r.components if c.key == "skills").applicable


def test_score_always_within_bounds(scorer):
    r = scorer.score(cv(skills={}, years_experience=0, education_level=0, languages={}),
                     job(education_level=4), 0.0)
    assert 0 <= r.total_score <= 100


def test_bands():
    assert [band_for(s) for s in (95, 70, 55, 40, 10)] == ["very_high", "high", "medium", "low", "very_low"]
