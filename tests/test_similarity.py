import numpy as np
import pytest

from src.embeddings import TfidfBackend, calibrate, cosine, semantic_similarity


def test_cosine_basics():
    a = np.array([1.0, 0.0])
    assert cosine(a, a) == pytest.approx(1.0)
    assert cosine(a, np.array([0.0, 1.0])) == pytest.approx(0.0)
    assert cosine(a, np.zeros(2)) == 0.0


def test_calibrate_bounds():
    assert calibrate(0.0, 0.1, 0.5) == 0.0
    assert calibrate(0.9, 0.1, 0.5) == 1.0
    assert calibrate(0.3, 0.1, 0.5) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        calibrate(0.3, 0.5, 0.5)


def test_related_text_scores_higher_than_unrelated(cv_text, job_text, job_mismatch):
    backend = TfidfBackend()
    good, _ = semantic_similarity(cv_text, job_text, backend)
    bad, _ = semantic_similarity(cv_text, job_mismatch, backend)
    assert 0 <= bad < good <= 1


def test_identical_and_empty_vocab():
    backend = TfidfBackend()
    text = "Administrador de sistemas Linux con Docker y Kubernetes en entornos cloud AWS"
    sim, _ = semantic_similarity(text, text, backend)
    assert sim == 1.0
    assert backend.raw_similarity("de la el", "y en con") == 0.0
