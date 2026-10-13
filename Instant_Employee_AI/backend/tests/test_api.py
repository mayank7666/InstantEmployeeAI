import uuid
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}@example.com"

def signup(role: str, email: str):
    response = client.post("/auth/signup", json={
        "email": email,
        "password": "TestPassword123!",
        "role": role,
        "full_name": "Test User",
    })
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_talent_profile_and_completion():
    email = unique_email("talent")
    headers = signup("talent", email)
    me = client.get("/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] == "talent"

    profile = client.put("/profiles/me", headers=headers, json={
        "full_name": "Test Candidate",
        "headline": "Python Developer",
        "skills": "Python, SQL",
        "timezone": "Asia/Kolkata",
        "availability": "Available",
        "portfolio_url": "",
        "resume_filename": "",
    })
    assert profile.status_code == 200
    assert profile.json()["completion_percent"] > 0

def test_company_can_post_job_and_talent_can_apply_once():
    company_headers = signup("company", unique_email("company"))
    talent_headers = signup("talent", unique_email("candidate"))

    created = client.post("/jobs", headers=company_headers, json={
        "title": "Backend Engineer",
        "department": "Engineering",
        "description": "Build and maintain Python API services.",
        "required_skills": "Python, FastAPI, SQL",
        "min_budget": 15000,
        "max_budget": 30000,
        "work_mode": "Remote",
        "timezone": "Asia/Kolkata",
    })
    assert created.status_code == 201, created.text
    job_id = created.json()["id"]

    jobs = client.get("/jobs")
    assert jobs.status_code == 200
    assert any(job["id"] == job_id for job in jobs.json())

    applied = client.post(f"/jobs/{job_id}/apply", headers=talent_headers, json={
        "resume_filename": "test-resume.pdf"
    })
    assert applied.status_code == 201, applied.text
    assert applied.json()["status"] == "Applied"

    duplicate = client.post(f"/jobs/{job_id}/apply", headers=talent_headers, json={
        "resume_filename": "test-resume.pdf"
    })
    assert duplicate.status_code == 409

    history = client.get("/applications/me", headers=talent_headers)
    assert history.status_code == 200
    assert any(item["job_id"] == job_id for item in history.json())

def test_talent_cannot_post_company_job():
    talent_headers = signup("talent", unique_email("talent"))
    response = client.post("/jobs", headers=talent_headers, json={
        "title": "Unauthorized Job",
        "description": "This should not be allowed for a talent account.",
    })
    assert response.status_code == 403
