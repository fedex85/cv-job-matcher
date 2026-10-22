from datetime import date

import pytest

from src.nlp import (
    compute_experience_years,
    extract_education_level,
    extract_languages,
    extract_required_years,
    get_skill_extractor,
)


@pytest.fixture(scope="module")
def ex(settings):
    return get_skill_extractor(str(settings.skills_db_path))


def test_detects_aliases_and_symbols(ex):
    found = ex.extract("Experto en Node.js, C++, C#, .NET, k8s y Amazon Web Services")
    assert {"Node.js", "C++", "C#", ".NET", "Kubernetes", "AWS"} <= set(found)


def test_word_boundaries(ex):
    assert "Java" not in ex.extract("Desarrollo en JavaScript")
    assert "JavaScript" in ex.extract("Desarrollo en JavaScript")
    assert "REST" not in ex.extract("Rest of the team")      # palabra común: sensible a mayúsculas
    assert "REST" in ex.extract("Diseño de APIs REST")
    assert "Go" not in ex.extract("let's go") and "Golang" not in ex.extract("let's go")


def test_accents_and_case_insensitive(ex):
    assert "Automatización" in ex.extract("AUTOMATIZACION de procesos")
    assert "Ciberseguridad" in ex.extract("ciberseguridad")


def test_prefix_not_double_counted(ex):
    found = ex.extract("Pipelines en GitLab CI")
    assert "GitLab CI" in found and "GitLab" not in found


def test_job_required_vs_nice_vs_ignored(ex):
    job = ex.extract_job_skills(
        "Requisitos:\n- Docker y Kubernetes\nSe valorará:\n- Helm\n- Ansible\n"
        "Qué ofrecemos:\n- Formación en Terraform\n"
    )
    assert set(job.required) == {"Docker", "Kubernetes"}
    assert set(job.nice) == {"Helm", "Ansible"}
    assert "Terraform" not in job.required and "Terraform" not in job.nice


def test_inline_nice_marker(ex):
    job = ex.extract_job_skills("Requisitos:\n- Python\n- Conocimientos de Go (golang) es un plus\n")
    assert "Python" in job.required and "Golang" in job.nice


def test_alternatives_group(ex):
    job = ex.extract_job_skills("Requisitos:\n- Experiencia en AWS o Azure\n- Docker\n")
    assert ["AWS", "Azure"] in job.alternatives


def test_experience_from_date_ranges_merges_overlap():
    today = date(2026, 10, 20)
    assert compute_experience_years("A: 2015 - 2020", today) == pytest.approx(5.0, abs=0.1)
    overlap = "A: ene 2015 - dic 2018\nB: 2017 - actualidad"
    assert compute_experience_years(overlap, today) == pytest.approx(11.8, abs=0.2)


def test_experience_stated_and_garbage():
    today = date(2026, 10, 20)
    assert compute_experience_years("Más de 10 años de experiencia en IT", today) == 10.0
    assert compute_experience_years("sin fechas", today) == 0.0
    assert compute_experience_years("2030 - 2035", today) == 0.0  # futuro: ignorado


def test_required_years():
    assert extract_required_years("Mínimo 3 años de experiencia en DevOps") == 3.0
    assert extract_required_years("3-5 years of experience with cloud") == 3.0  # mínimo del rango
    assert extract_required_years("Oferta sin requisito de años") is None
    assert extract_required_years("Empresa fundada hace 20 años") is None


def test_education_levels():
    assert extract_education_level("Doctorado en Física") == 4
    assert extract_education_level("Máster en Ciberseguridad") == 3
    assert extract_education_level("Grado en Ingeniería Informática") == 2
    assert extract_education_level("Ciclo formativo de grado superior ASIR") == 1
    assert extract_education_level("Experiencia en ventas") == 0
    assert extract_education_level("Grado o FP en informática", mode="min") == 1


def test_languages():
    langs = extract_languages("Idiomas: Inglés B2, Francés avanzado\nEspañol nativo")
    assert langs == {"en": 4, "fr": 5, "es": 6}
    assert extract_languages("Advanced English and basic German") == {"en": 5, "de": 2}
    assert extract_languages("Inglés, Francés C1") == {"en": 3, "fr": 5}   # C1 es del francés
    assert extract_languages("sin idiomas") == {}


def test_timeline_extraction(ex):
    from datetime import date

    from src.nlp import extract_timeline

    text = ("Ingeniera de Infraestructura - Empresa B (2020 - actualidad)\n- Docker y Terraform en Azure\n"
            "Administradora de Sistemas - Empresa A (ene 2014 - dic 2019)\n- Linux, VMware y Bash\n")
    tl = extract_timeline(text, ex.extract, today=date(2026, 10, 20))
    assert [e["period"] for e in tl] == ["2020 – actualidad", "2014 – 2019"]   # más reciente primero
    assert tl[0]["title"] == "Ingeniera de Infraestructura - Empresa B"
    assert {"Docker", "Terraform", "Azure"} <= set(tl[0]["skills"]) and "Linux" in tl[1]["skills"]
    assert tl[1]["years"] == pytest.approx(6.0, abs=0.1)
    assert extract_timeline("sin fechas aquí", ex.extract) == []
