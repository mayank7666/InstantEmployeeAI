# Instant Employee API (MVP)

First backend stage from the platform plan: talent/company signup and login, profiles with completion percentage, job search and posting, durable applications, and company-side application status updates.

## Run locally
From the repository root:
```bash
cd Instant_Employee_AI/backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```
Open http://127.0.0.1:8000/docs and check /health.

## Endpoints
- POST /auth/signup — create talent/company account
- POST /auth/login — login (OAuth2 form: username=email)
- GET /me — current account
- GET/PUT /profiles/me — view/update profile and completion percentage
- GET /jobs — list/search/filter jobs
- POST /jobs — company creates job
- GET /jobs/mine — company's jobs and application counts
- POST /jobs/{job_id}/apply — talent applies once per job
- GET /applications/me — persistent application history
- GET /jobs/{job_id}/applications — company sees applicants for its own job
- PATCH /applications/{application_id}/status?new_status=Shortlisted — update application status

SQLite is the local default. Set DATABASE_URL to PostgreSQL and a strong SECRET_KEY in deployment secrets for production. This API is not yet deployed or connected to the Streamlit UI. Resume binary storage, chat, contracts, billing, Redis, Elasticsearch, email/SMS, vetting, and production migrations remain later phases.
