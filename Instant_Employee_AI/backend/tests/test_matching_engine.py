import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from matching_engine import (
    education_fit_score,
    experience_fit_score,
    education_level,
    extract_candidate_experience_years,
    extract_required_experience_years,
    match_candidates,
    match_resume_to_jobs,
)


def test_explicit_experience_years_are_extracted():
    assert extract_required_experience_years("Need 3+ years of relevant experience") == 3
    assert extract_candidate_experience_years("Python engineer with 2 years of experience") == 2


def test_experience_is_neutral_when_job_has_no_requirement():
    score, required, candidate = experience_fit_score("Python developer", "Python developer")
    assert score == 100.0
    assert required is None


def test_education_fit_uses_explicit_qualification():
    assert education_level("Machine Learning Engineer with Python") is None
    score, required, candidate = education_fit_score(
        "Bachelor degree required for this role",
        "B.Tech graduate with Python skills",
    )
    assert required == 3
    assert candidate == 3
    assert score == 100.0


def test_common_words_do_not_inflate_detected_education_level():
    assert education_level("I would be happy to contribute to the team.") is None
    assert education_level("The candidate may be available next month.") is None


def test_resume_to_jobs_returns_explainable_ranked_results():
    resume = "B.Tech graduate with 2 years of experience. Python SQL machine learning project work."
    jobs = [
        {
            "title": "Machine Learning Engineer",
            "description": "Bachelor degree required, 2 years of experience building machine learning models.",
            "required_skills": "Python, SQL, Machine Learning",
        },
        {
            "title": "Frontend Developer",
            "description": "Bachelor degree required, 2 years of experience building websites.",
            "required_skills": "React, JavaScript, CSS",
        },
    ]
    results = match_resume_to_jobs(resume, jobs)
    assert len(results) == 2
    assert results[0]["title"] == "Machine Learning Engineer"
    assert 0 <= results[0]["score"] <= 100
    assert "experience_fit" in results[0]
    assert "education_fit" in results[0]
    assert results[0]["reasons"]


def test_empty_resume_never_receives_a_positive_match_score(monkeypatch):
    import matching_engine

    monkeypatch.setattr(matching_engine, "calculate_semantic_similarity", lambda *_: None)
    results = matching_engine.match_candidates(
        "Python engineer with 3 years of experience and bachelor degree required.",
        {"Empty candidate": "   "},
    )

    assert len(results) == 1
    assert results[0]["final_score"] == 0.0
    assert results[0]["experience_fit"] == 0.0
    assert results[0]["education_fit"] == 0.0
    assert results[0]["reasons"] == ["No readable resume text was provided."]


def test_candidate_ranking_contains_skill_and_explanation_fields():
    results = match_candidates(
        "Python Machine Learning SQL. 2 years of experience. Bachelor degree required.",
        {
            "Relevant": "Python SQL machine learning with 2 years of experience. B.Tech graduate.",
            "Unrelated": "HTML CSS React frontend developer.",
        },
    )
    assert results[0]["name"] == "Relevant"
    assert results[0]["final_score"] >= results[1]["final_score"]
    assert "experience_fit" in results[0]
    assert "education_fit" in results[0]
    assert results[0]["reasons"]


def test_expanded_catalog_recognizes_common_backend_data_and_ai_skills():
    from matching_engine import extract_skills

    found = extract_skills(
        "Built REST APIs with Django, Node.js, MongoDB, Redis, "
        "Apache Spark, Airflow, Snowflake, XGBoost, Hugging Face and LangChain."
    )
    expected = {
        "REST API", "Django", "Node.js", "MongoDB", "Redis",
        "Apache Spark", "Airflow", "Snowflake", "XGBoost",
        "Hugging Face", "LangChain",
    }
    assert expected.issubset(set(found))



def test_matching_score_is_bounded_and_results_are_ranked_without_semantic_model(monkeypatch):
    import matching_engine

    monkeypatch.setattr(
        matching_engine, "calculate_semantic_similarity",
        lambda *_: None,
    )
    results = matching_engine.match_candidates(
        "Python SQL Machine Learning required",
        {
            "Strong fit": "Python SQL machine learning and data analysis",
            "Partial fit": "Python and HTML",
            "No readable resume": "",
        },
    )

    assert [item["name"] for item in results] == [
        "Strong fit", "Partial fit", "No readable resume"
    ]
    assert all(0.0 <= item["final_score"] <= 100.0 for item in results)
    assert results[-1]["final_score"] == 0.0
    assert results[-1]["reasons"] == ["No readable resume text was provided."]


def test_skill_aliases_are_normalized_and_not_substring_matched():
    from matching_engine import extract_skills

    found = set(extract_skills("JavaScript, scikit learn, natural language processing, PostgreSQL"))
    assert {"JavaScript", "Scikit-learn", "NLP", "PostgreSQL"}.issubset(found)
    # "Java" must not be inferred from the word "JavaScript".
    assert "Java" not in found


def test_resume_to_jobs_handles_empty_job_text_and_missing_semantic_model(monkeypatch):
    import matching_engine

    def unavailable_model():
        raise RuntimeError("model intentionally disabled in unit test")

    monkeypatch.setattr(matching_engine, "_get_sentence_transformer_model", unavailable_model)
    results = matching_engine.match_resume_to_jobs(
        "Python SQL developer with 2 years of experience. B.Tech graduate.",
        [
            {
                "title": "Python Developer",
                "description": "2 years of experience. Bachelor degree required.",
                "required_skills": "Python, SQL",
            },
            {
                "title": "Unrelated Designer",
                "description": "",
                "required_skills": "",
            },
        ],
    )

    assert len(results) == 2
    assert results[0]["title"] == "Python Developer"
    assert results[0]["semantic"] is None
    assert results[0]["matched"] == ["Python", "SQL"]
    assert results[0]["missing"] == []
    assert all(0.0 <= item["score"] <= 100.0 for item in results)


def test_resume_to_jobs_rejects_blank_resume_and_handles_no_jobs():
    import pytest

    with pytest.raises(ValueError, match="Resume text cannot be empty"):
        match_resume_to_jobs("   ", [{"title": "Python Developer"}])

    assert match_resume_to_jobs("Python developer", []) == []


def test_candidate_matching_rejects_blank_job_description():
    import pytest

    with pytest.raises(ValueError, match="Job description cannot be empty"):
        match_candidates("  ", {"Candidate": "Python developer"})
