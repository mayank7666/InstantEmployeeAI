import os
import uuid
from fastapi.testclient import TestClient
from main import app, SessionLocal, User

client = TestClient(app)
TEST_SETUP_KEY = "test-only-setup-key"
os.environ["ADMIN_SETUP_KEY"] = TEST_SETUP_KEY
_admin_headers = None

def unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}@example.com"

def signup(role: str, email: str):
    global _admin_headers
    if role == "company":
        if _admin_headers is None:
            # Clean up only test-created root admins so this suite can run repeatedly.
            with SessionLocal() as db:
                roots = db.query(User).filter(User.role == "company", User.company_id.is_(None)).all()
                for root in roots:
                    db.delete(root)
                db.commit()
            admin_email = unique_email("test-admin")
            response = client.post("/auth/company/bootstrap", json={
                "email": admin_email,
                "password": "TestPassword123!",
                "full_name": "Test Admin",
                "setup_key": TEST_SETUP_KEY,
            })
            assert response.status_code == 201, response.text
            _admin_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        response = client.post("/auth/company/bulk-create", headers=_admin_headers, json={
            "employees": [{"name": "Test Company", "email": email, "password": "TestPassword123!"}]
        })
        assert response.status_code == 200, response.text
        login_response = client.post("/auth/login", data={
            "username": email, "password": "TestPassword123!"
        })
        assert login_response.status_code == 200, login_response.text
        return {"Authorization": f"Bearer {login_response.json()['access_token']}"}
    response = client.post("/auth/signup", json={
        "email": email,
        "password": "TestPassword123!",
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

def test_csv_job_applications_are_persisted_and_duplicates_blocked():
    talent_headers = signup("talent", unique_email("csv-candidate"))
    payload = {
        "job_key": "csv-job-abc123",
        "job_title": "Machine Learning Engineer",
        "company_name": "Instant Employee",
        "resume_filename": "candidate-resume.pdf",
    }

    applied = client.post("/applications/external", headers=talent_headers, json=payload)
    assert applied.status_code == 201, applied.text
    assert applied.json()["job_title"] == payload["job_title"]
    assert applied.json()["resume_filename"] == payload["resume_filename"]

    duplicate = client.post("/applications/external", headers=talent_headers, json=payload)
    assert duplicate.status_code == 409

    history = client.get("/applications/external/me", headers=talent_headers)
    assert history.status_code == 200, history.text
    assert any(item["job_key"] == payload["job_key"] for item in history.json())


def test_external_application_history_is_private_to_each_candidate():
    first_headers = signup("talent", unique_email("first-candidate"))
    second_headers = signup("talent", unique_email("second-candidate"))
    payload = {
        "job_key": "private-csv-job",
        "job_title": "Data Analyst",
        "company_name": "Example Company",
        "resume_filename": "first.pdf",
    }
    response = client.post("/applications/external", headers=first_headers, json=payload)
    assert response.status_code == 201, response.text

    first_history = client.get("/applications/external/me", headers=first_headers)
    second_history = client.get("/applications/external/me", headers=second_headers)
    assert first_history.status_code == 200
    assert any(item["job_key"] == payload["job_key"] for item in first_history.json())
    assert second_history.status_code == 200
    assert all(item["job_key"] != payload["job_key"] for item in second_history.json())


def test_talent_cannot_post_company_job():
    talent_headers = signup("talent", unique_email("talent"))
    response = client.post("/jobs", headers=talent_headers, json={
        "title": "Unauthorized Job",
        "description": "This should not be allowed for a talent account.",
    })
    assert response.status_code == 403

def test_external_application_endpoints_require_talent_authentication():
    payload = {
        "job_key": "auth-required-job",
        "job_title": "Python Developer",
        "company_name": "Example Company",
        "resume_filename": "candidate.pdf",
    }
    create_response = client.post("/applications/external", json=payload)
    history_response = client.get("/applications/external/me")
    assert create_response.status_code == 401
    assert history_response.status_code == 401


def test_company_cannot_use_talent_external_application_endpoints():
    company_headers = signup("company", unique_email("company-external-access"))
    payload = {
        "job_key": "company-role-check",
        "job_title": "Python Developer",
        "company_name": "Example Company",
        "resume_filename": "candidate.pdf",
    }
    create_response = client.post(
        "/applications/external", headers=company_headers, json=payload
    )
    history_response = client.get(
        "/applications/external/me", headers=company_headers
    )
    assert create_response.status_code == 403
    assert history_response.status_code == 403

def test_company_application_list_only_returns_owned_job_applications():
    first_company = signup("company", unique_email("first-company"))
    second_company = signup("company", unique_email("second-company"))
    candidate = signup("talent", unique_email("company-dashboard-candidate"))

    def create_job(headers, title):
        response = client.post("/jobs", headers=headers, json={
            "title": title,
            "department": "Engineering",
            "description": "Build and maintain backend API services.",
            "required_skills": "Python, FastAPI",
            "min_budget": 10000,
            "max_budget": 20000,
            "work_mode": "Remote",
            "timezone": "Asia/Kolkata",
        })
        assert response.status_code == 201, response.text
        return response.json()["id"]

    first_job_id = create_job(first_company, "First Company API Engineer")
    second_job_id = create_job(second_company, "Second Company API Engineer")

    for job_id in (first_job_id, second_job_id):
        response = client.post(
            f"/jobs/{job_id}/apply",
            headers=candidate,
            json={"resume_filename": "candidate.pdf"},
        )
        assert response.status_code == 201, response.text

    first_company_apps = client.get("/applications/company", headers=first_company)
    second_company_apps = client.get("/applications/company", headers=second_company)
    assert first_company_apps.status_code == 200, first_company_apps.text
    assert second_company_apps.status_code == 200, second_company_apps.text
    assert [row["job_id"] for row in first_company_apps.json()] == [first_job_id]
    assert [row["job_id"] for row in second_company_apps.json()] == [second_job_id]


def test_company_application_list_rejects_talent_and_unauthenticated_users():
    talent_headers = signup("talent", unique_email("company-app-list-talent"))
    assert client.get("/applications/company").status_code == 401
    assert client.get("/applications/company", headers=talent_headers).status_code == 403



def test_public_signup_cannot_create_company_admin():
    response = client.post("/auth/signup", json={
        "email": unique_email("public-company"),
        "password": "TestPassword123!",
        "full_name": "Unauthorized Company",
        "role": "company",
    })
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    me = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "talent"


def test_admin_bootstrap_requires_private_setup_key():
    response = client.post("/auth/company/bootstrap", json={
        "email": unique_email("wrong-key"),
        "password": "TestPassword123!",
        "full_name": "Test Admin",
        "setup_key": "incorrect-key",
    })
    assert response.status_code == 403
