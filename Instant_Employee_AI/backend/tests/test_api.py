import os
import uuid
from fastapi.testclient import TestClient
from main import app, SessionLocal, User, hash_password

client = TestClient(app)
TEST_SETUP_KEY = "test-only-setup-key"
os.environ["ADMIN_SETUP_KEY"] = TEST_SETUP_KEY
_admin_headers = None

def unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}@example.com"

def save_test_resume(headers, filename="test-resume.pdf"):
    response = client.put("/profiles/me", headers=headers, json={
        "full_name": "Test Candidate",
        "headline": "Python Developer",
        "skills": "Python, FastAPI, SQL, Machine Learning",
        "timezone": "Asia/Kolkata",
        "availability": "Available",
        "portfolio_url": "",
        "resume_filename": filename,
        "resume_text": "Python developer with FastAPI SQL and machine learning project experience.",
        "resume_data": "dGVzdC1wZGY=",
    })
    assert response.status_code == 200, response.text


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

def test_database_health_endpoint():
    response = client.get("/health/database")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "connected"
    assert payload["required_tables_present"] is True
    assert payload["database_dialect"] in {"sqlite", "postgresql"}

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
    save_test_resume(talent_headers)

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

    # Company can update the saved application status and the candidate sees it.
    application_id = applied.json()["id"]
    shortlisted = client.patch(
        f"/applications/{application_id}/status",
        headers=company_headers,
        params={"new_status": "Shortlisted"},
    )
    assert shortlisted.status_code == 200, shortlisted.text
    assert shortlisted.json()["status"] == "Shortlisted"

    updated_history = client.get("/applications/me", headers=talent_headers)
    assert updated_history.status_code == 200
    saved_application = next(
        item for item in updated_history.json() if item["job_id"] == job_id
    )
    assert saved_application["status"] == "Shortlisted"

    invalid_status = client.patch(
        f"/applications/{application_id}/status",
        headers=company_headers,
        params={"new_status": "HiredMaybe"},
    )
    assert invalid_status.status_code == 422

def test_csv_job_applications_are_persisted_and_duplicates_blocked():
    talent_headers = signup("talent", unique_email("csv-candidate"))
    save_test_resume(talent_headers, "candidate-resume.pdf")
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
    save_test_resume(first_headers, "first.pdf")
    save_test_resume(second_headers, "second.pdf")
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
    save_test_resume(candidate)

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
    first_visible_jobs = {row["job_id"] for row in first_company_apps.json()}
    second_visible_jobs = {row["job_id"] for row in second_company_apps.json()}
    # Both employee accounts belong to the same organization and should see
    # applications for jobs posted by that organization.
    assert {first_job_id, second_job_id}.issubset(first_visible_jobs)
    assert {first_job_id, second_job_id}.issubset(second_visible_jobs)
    assert first_visible_jobs == second_visible_jobs


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


def test_primary_admin_password_reset_requires_setup_key_and_updates_password():
    # Use only the isolated test database and the primary admin created by this test suite.
    with SessionLocal() as db:
        admin = db.query(User).filter(
            User.role == "company",
            User.company_id.is_(None),
        ).first()
        if admin is None:
            admin_email = unique_email("reset-test-admin")
            created = client.post("/auth/company/bootstrap", json={
                "email": admin_email,
                "password": "OldTestPassword123!",
                "full_name": "Reset Test Admin",
                "setup_key": TEST_SETUP_KEY,
            })
            assert created.status_code == 201, created.text
        else:
            admin_email = admin.email

    invalid_key = client.post(
        "/auth/company/reset-password",
        headers={"X-Admin-Setup-Key": "wrong-key"},
        json={"email": admin_email, "new_password": "NewTestPassword123!"},
    )
    assert invalid_key.status_code == 403

    reset = client.post(
        "/auth/company/reset-password",
        headers={"X-Admin-Setup-Key": TEST_SETUP_KEY},
        json={"email": admin_email, "new_password": "NewTestPassword123!"},
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["status"] == "password_reset"

    login = client.post("/auth/login", data={
        "username": admin_email,
        "password": "NewTestPassword123!",
    })
    assert login.status_code == 200, login.text
    me = client.get("/me", headers={
        "Authorization": f"Bearer {login.json()['access_token']}"
    })
    assert me.status_code == 200, me.text
    assert me.json()["role"] == "company"

def test_disabled_account_cannot_login():
    email = unique_email("disabled-login")
    signup_response = client.post("/auth/signup", json={
        "email": email,
        "password": "TestPassword123!",
        "full_name": "Disabled Account",
    })
    assert signup_response.status_code == 201, signup_response.text

    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        user.is_active = False
        db.commit()

    login = client.post("/auth/login", data={
        "username": email,
        "password": "TestPassword123!",
    })
    assert login.status_code == 401

def test_closed_job_disappears_from_public_search_and_rejects_applications():
    company_headers = signup("company", unique_email("closed-job-owner"))
    talent_headers = signup("talent", unique_email("closed-job-candidate"))
    save_test_resume(talent_headers)

    created = client.post("/jobs", headers=company_headers, json={
        "title": "Temporary QA Engineer",
        "department": "Engineering",
        "description": "Test and validate application releases.",
        "required_skills": "Python, Testing",
        "min_budget": 10000,
        "max_budget": 20000,
        "work_mode": "Remote",
        "timezone": "Asia/Kolkata",
    })
    assert created.status_code == 201, created.text
    job_id = created.json()["id"]
    assert any(job["id"] == job_id for job in client.get("/jobs").json())

    closed = client.patch(f"/jobs/{job_id}/status", headers=company_headers, params={"is_active": False})
    assert closed.status_code == 200, closed.text

    public_jobs = client.get("/jobs")
    assert public_jobs.status_code == 200
    assert all(job["id"] != job_id for job in public_jobs.json())

    application = client.post(
        f"/jobs/{job_id}/apply",
        headers=talent_headers,
        json={"resume_filename": "test-resume.pdf"},
    )
    assert application.status_code == 404
    assert application.json()["detail"] == "Active job not found"


def test_job_creation_rejects_minimum_budget_above_maximum():
    company_headers = signup("company", unique_email("invalid-budget-owner"))
    response = client.post("/jobs", headers=company_headers, json={
        "title": "Budget Validation Engineer",
        "department": "Engineering",
        "description": "Validate job posting budget boundaries.",
        "required_skills": "Testing",
        "min_budget": 50000,
        "max_budget": 30000,
        "work_mode": "Remote",
        "timezone": "Asia/Kolkata",
    })
    assert response.status_code == 422
    assert response.json()["detail"] == "Minimum budget cannot exceed maximum budget"


def test_company_job_update_close_reopen_and_ownership():
    owner = signup("company", unique_email("job-owner"))
    other_email = unique_email("separate-org")
    with SessionLocal() as db:
        separate_company = User(
            email=other_email,
            password_hash=hash_password("TestPassword123!"),
            role="company",
            company_id=None,
        )
        db.add(separate_company)
        db.commit()
    other_login = client.post("/auth/login", data={
        "username": other_email,
        "password": "TestPassword123!",
    })
    assert other_login.status_code == 200, other_login.text
    other = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    create = client.post("/jobs", headers=owner, json={
        "title": "Original API Engineer",
        "department": "Engineering",
        "description": "Build reliable API services for customers.",
        "required_skills": "Python, FastAPI",
        "min_budget": 20000,
        "max_budget": 40000,
        "work_mode": "Remote",
        "timezone": "Asia/Kolkata",
    })
    assert create.status_code == 201, create.text
    job_id = create.json()["id"]

    update_payload = {
        "title": "Senior API Engineer",
        "department": "Engineering",
        "description": "Build and maintain secure production API services.",
        "required_skills": "Python, FastAPI, PostgreSQL",
        "min_budget": 30000,
        "max_budget": 60000,
        "work_mode": "Hybrid",
        "timezone": "Asia/Kolkata",
    }
    update = client.put(f"/jobs/{job_id}", headers=owner, json=update_payload)
    assert update.status_code == 200, update.text
    assert update.json()["title"] == "Senior API Engineer"

    forbidden_update = client.put(f"/jobs/{job_id}", headers=other, json=update_payload)
    assert forbidden_update.status_code == 404

    close = client.delete(f"/jobs/{job_id}", headers=owner)
    assert close.status_code == 200, close.text
    assert close.json()["status"] == "closed"
    public_ids = {row["id"] for row in client.get("/jobs").json()}
    assert job_id not in public_ids

    reopen = client.patch(f"/jobs/{job_id}/status?is_active=true", headers=owner)
    assert reopen.status_code == 200, reopen.text
    assert reopen.json()["is_active"] is True
    public_ids = {row["id"] for row in client.get("/jobs").json()}
    assert job_id in public_ids

def test_company_cannot_change_or_download_another_company_application():
    owner_headers = signup("company", unique_email("application-owner"))

    # Create a separate root company so this checks cross-organization isolation,
    # not two employee accounts belonging to the same organization.
    other_email = unique_email("application-other-owner")
    with SessionLocal() as db:
        separate_company = User(
            email=other_email,
            password_hash=hash_password("TestPassword123!"),
            role="company",
            company_id=None,
        )
        db.add(separate_company)
        db.commit()
    other_login = client.post("/auth/login", data={
        "username": other_email,
        "password": "TestPassword123!",
    })
    assert other_login.status_code == 200, other_login.text
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    candidate_headers = signup("talent", unique_email("application-owner-candidate"))
    save_test_resume(candidate_headers, "private-candidate.pdf")

    created = client.post("/jobs", headers=owner_headers, json={
        "title": "Private Backend Role",
        "department": "Engineering",
        "description": "Build secure backend services and APIs.",
        "required_skills": "Python, FastAPI",
        "min_budget": 10000,
        "max_budget": 20000,
        "work_mode": "Remote",
        "timezone": "Asia/Kolkata",
    })
    assert created.status_code == 201, created.text
    job_id = created.json()["id"]

    applied = client.post(
        f"/jobs/{job_id}/apply",
        headers=candidate_headers,
        json={"resume_filename": "private-candidate.pdf"},
    )
    assert applied.status_code == 201, applied.text
    application_id = applied.json()["id"]

    forbidden_status = client.patch(
        f"/applications/{application_id}/status",
        headers=other_headers,
        params={"new_status": "Shortlisted"},
    )
    assert forbidden_status.status_code == 404

    forbidden_resume = client.get(
        f"/applications/{application_id}/resume",
        headers=other_headers,
    )
    assert forbidden_resume.status_code == 404

    owner_resume = client.get(
        f"/applications/{application_id}/resume",
        headers=owner_headers,
    )
    assert owner_resume.status_code == 200, owner_resume.text
    assert owner_resume.json()["filename"] == "private-candidate.pdf"

