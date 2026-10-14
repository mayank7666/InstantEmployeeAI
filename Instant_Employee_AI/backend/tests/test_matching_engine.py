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
