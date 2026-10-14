from pathlib import Path
import base64
import html
import sys
import time
import pandas as pd
import requests
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from src.matching_engine import match_candidates

st.set_page_config(page_title="Instant Employee | Company Dashboard", page_icon="✦", layout="wide")
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
JOBS_FILE = DATA / "jobs.csv"
SHORTLIST_FILE = DATA / "shortlist.csv"
API_BASE_URL = "https://instant-employee-api.onrender.com"


def api_request(method, path, token=None, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.request(method, f"{API_BASE_URL}{path}", headers=headers, timeout=(8, 30), **kwargs)
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if not response.ok:
            detail = payload.get("detail") if isinstance(payload, dict) else None
            return None, str(detail or f"API request failed (HTTP {response.status_code})")
        return payload, None
    except requests.RequestException:
        return None, "The API is currently unavailable. Please try again shortly."


def read_csv(path):
    try:
        return pd.read_csv(path).fillna("") if path.exists() else pd.DataFrame()
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
        return pd.DataFrame()


def safe(value):
    return html.escape(str(value or "Not specified").strip())


def company_session(token):
    me, error = api_request("GET", "/me", token=token)
    if error:
        return error
    if me.get("role") != "company":
        return "This is a candidate account. Please log in with a company account."
    st.session_state.company_api_token = token
    st.session_state.company_logged_in = True
    st.session_state.company_email = me.get("email", "")
    st.session_state.company_is_employee = bool(me.get("company_id"))
    return None


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
:root{--blue:#2454f5;--ink:#17233b;--muted:#52637e;--line:#dce5f2}
html,body,[class*="css"]{font-family:Inter,system-ui,sans-serif}
.stApp{background:linear-gradient(135deg,#f8faff,#eef4ff);color:#17233b}
.main .block-container{max-width:1450px;padding-top:1rem;padding-bottom:2rem}
[data-testid="stAppViewContainer"],[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#ffffff,#edf3ff);border-right:1px solid #dce5f2}
[data-testid="stSidebar"] *{color:#17233b!important}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"]{color:#61728d!important}
[data-testid="stSidebarNav"]{display:none}
/* Polished company workspace sidebar navigation */
[data-testid="stSidebar"] div[data-testid="stPageLink"]{margin:7px 0!important}
[data-testid="stSidebar"] div[data-testid="stPageLink"] a{
    background:linear-gradient(135deg,#ffffff,#f2f6ff)!important;
    border:1px solid #d9e4f5!important;
    border-radius:12px!important;
    padding:12px 14px!important;
    min-height:44px!important;
    color:#263a59!important;
    font-weight:600!important;
    transition:background .15s ease,border-color .15s ease,transform .15s ease!important;
}
[data-testid="stSidebar"] div[data-testid="stPageLink"] a *{
    color:#263a59!important;-webkit-text-fill-color:#263a59!important;opacity:1!important;
}
[data-testid="stSidebar"] div[data-testid="stPageLink"] a:hover{
    background:#e7efff!important;border-color:#bfd1f3!important;transform:translateY(-1px);
}
[data-testid="stSidebar"] div[data-testid="stPageLink"] a[aria-current="page"]{
    background:#e2ebff!important;border-color:#b9cdf5!important;color:#1f4f9a!important;
    box-shadow:inset 3px 0 0 #6795e8!important;
}
[data-testid="stSidebar"] div[data-testid="stPageLink"] a[aria-current="page"] *{
    color:#1f4f9a!important;-webkit-text-fill-color:#1f4f9a!important;
}
[data-testid="stSidebar"] hr{margin:20px 0!important;border-color:#dce5f2!important}
.hero{padding:30px 32px;border-radius:22px;border:1px solid #dfe7fb;background:linear-gradient(115deg,#f7f9ff,#eaf0ff);margin-bottom:22px}
.kicker{font-size:12px;letter-spacing:1.7px;text-transform:uppercase;font-weight:800;color:#2855e8}
.hero h1{font-size:clamp(32px,4vw,48px);line-height:1.08;letter-spacing:-1.8px;margin:12px 0;color:#101828}
.hero h1 span{color:#2454f5}.hero p{font-size:15px;line-height:1.7;color:#52637e;max-width:700px}
div[data-testid="stMetric"]{background:white;border:1px solid var(--line);border-radius:14px;padding:17px;box-shadow:0 4px 15px #263e7008}
div[data-testid="stMetric"] label{color:#52637e!important}div[data-testid="stMetricValue"]{color:#17233b!important;font-weight:800}
.panel,.jobcard{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:14px}
.jobcard h4{margin:0 0 6px;color:#17233b}.jobcard p{margin:4px 0;color:#52637e;font-size:13px}
.pill{display:inline-block;background:#dcfce7;color:#166534;border-radius:20px;padding:3px 9px;font-size:11px;font-weight:700}
label,[data-testid="stMarkdownContainer"] p,[data-testid="stCaptionContainer"],.stMarkdown{color:#34445e}
input,textarea,[data-baseweb="input"],[data-baseweb="textarea"]{background:#fff!important;color:#17233b!important;border-color:#cbd7e8!important}
[data-baseweb="input"] input{color:#17233b!important;-webkit-text-fill-color:#17233b!important}
[data-baseweb="select"]>div{background:#fff!important;color:#17233b!important;border-color:#cbd7e8!important}
[data-testid="stFileUploader"] section{background:#fff!important;border:1px dashed #b9c9df!important}
[data-testid="stFileUploader"] *{color:#34445e!important}
[data-baseweb="tab-list"]{background:#f0f5ff;border-bottom:1px solid var(--line)}
[data-baseweb="tab"]{color:#52637e!important}
[data-baseweb="tab"][aria-selected="true"]{color:#2454f5!important;border-bottom-color:#2454f5!important}
/* Attractive company/employee login and initial admin setup forms */
[data-testid="stTabs"] [data-baseweb="tab-list"]{
    background:#eaf1ff!important;border:1px solid #d8e4f7!important;
    border-radius:14px!important;padding:5px!important;gap:6px!important;
}
[data-testid="stTabs"] button[data-baseweb="tab"]{
    border-radius:10px!important;padding:10px 16px!important;
    color:#50627e!important;font-weight:650!important;
}
[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"]{
    background:#ffffff!important;color:#2456a6!important;
    box-shadow:0 2px 8px #203d7012!important;border-bottom-color:transparent!important;
}
[data-testid="stForm"]{
    background:linear-gradient(145deg,#ffffff,#f8faff)!important;
    border:1px solid #dce6f5!important;border-radius:18px!important;
    padding:22px!important;box-shadow:0 10px 28px #203d700c!important;
}
[data-testid="stForm"] label{font-weight:600!important;color:#34445e!important}
[data-testid="stForm"] input{border-radius:10px!important;min-height:42px!important}
[data-testid="stForm"] button[kind="primary"]{
    background:#e4edff!important;border:1px solid #c9d9ff!important;
    color:#2456a6!important;border-radius:11px!important;font-weight:700!important;
}
[data-testid="stForm"] button[kind="primary"] *{
    color:#2456a6!important;-webkit-text-fill-color:#2456a6!important;
}
[data-testid="stForm"] button[kind="primary"]:hover{
    background:#d5e3ff!important;border-color:#a9c4ff!important;
}
.stButton>button{border-radius:9px!important;font-weight:700!important;background:#fff!important;color:#17233b!important;border-color:#cbd7e8!important}
.stButton>button[kind="primary"]{background:#2454f5!important;border-color:#2454f5!important;color:#fff!important}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<div style='font-size:24px;font-weight:800;padding:10px 0'>✦ Instant Employee</div><div style='color:#9caec9;font-size:12px;margin-bottom:18px'>AI Talent Platform · Company</div>", unsafe_allow_html=True)
    st.divider()
    st.page_link("app.py", label="⌂  Public Job Portal", use_container_width=True)
    st.page_link("pages/4_Employee_Dashboard.py", label="▦  Company Dashboard", use_container_width=True)
    st.page_link("pages/2_Job_Posting.py", label="＋  Post a Job", use_container_width=True)
    st.page_link("pages/3_Match_Candidates.py", label="⌕  Find Talent", use_container_width=True)
    st.divider()
    if st.session_state.get("company_logged_in"):
        st.caption("SIGNED IN")
        st.write(st.session_state.get("company_email", "Company"))
        if st.button("Log out", use_container_width=True):
            for key in ("company_api_token", "company_logged_in", "company_email", "company_is_employee", "employee_setup_unlocked"):
                st.session_state.pop(key, None)
            st.rerun()

if not st.session_state.get("company_logged_in"):
    st.markdown("<div class='hero'><div class='kicker'>Private company workspace</div><h1>Company <span>Dashboard</span></h1><p>Secure login for the company administrator and company-created employee accounts.</p></div>", unsafe_allow_html=True)
    login_tab, setup_tab = st.tabs(["Company / Employee Login", "Initial Admin Setup"])
    with login_tab:
        with st.form("company_login_form"):
            email = st.text_input("Company email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login to Dashboard", type="primary", use_container_width=True)
        if submitted:
            if not email.strip() or not password:
                st.error("Please enter both email and password.")
            else:
                token_data, error = api_request("POST", "/auth/login", data={"username": email.strip().lower(), "password": password}, headers={"Content-Type": "application/x-www-form-urlencoded"})
                if error:
                    st.error(error)
                else:
                    error = company_session(token_data["access_token"])
                    if error:
                        st.error(error)
                    else:
                        st.success("Company login successful.")
                        st.rerun()
    with setup_tab:
        st.info("This setup is only for creating the initial company admin. An account cannot be created until ADMIN_SETUP_KEY is configured on the Render API. Employee accounts can be created later from the admin dashboard.")
        with st.form("company_bootstrap_form"):
            company_name = st.text_input("Company / admin name", key="bootstrap_company_name")
            admin_email = st.text_input("Admin email", key="bootstrap_admin_email")
            admin_password = st.text_input("Admin password (minimum 8 characters)", type="password", key="bootstrap_admin_password")
            confirm_password = st.text_input("Confirm admin password", type="password", key="bootstrap_confirm_password")
            setup_key = st.text_input("Private setup key", type="password", key="bootstrap_setup_key", help="Must match ADMIN_SETUP_KEY configured privately in Render.")
            submitted = st.form_submit_button("Set Up First Admin", type="primary", use_container_width=True)
        if submitted:
            if not company_name.strip() or not admin_email.strip() or not admin_password or not setup_key:
                st.error("Please complete all fields.")
            elif len(admin_password) < 8:
                st.error("The password must contain at least 8 characters.")
            elif admin_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                result, error = api_request("POST", "/auth/company/bootstrap", json={"email": admin_email.strip().lower(), "password": admin_password, "full_name": company_name.strip(), "setup_key": setup_key})
                if error:
                    st.error(error)
                else:
                    error = company_session(result["access_token"])
                    if error:
                        st.error(error)
                    else:
                        st.success("First company admin successfully set up.")
                        st.rerun()
    st.info("Public sign-up is available only for candidate accounts. Company admin sign-up is protected by a private setup key.")
    st.stop()

token = st.session_state.company_api_token
me, me_error = api_request("GET", "/me", token=token)
if me_error or not me or me.get("role") != "company":
    for key in ("company_api_token", "company_logged_in", "company_email"):
        st.session_state.pop(key, None)
    st.warning("Your session has expired. Please log in again.")
    st.stop()

jobs, jobs_error = api_request("GET", "/jobs/mine", token=token)
applications, apps_error = api_request("GET", "/applications/company", token=token)
jobs = jobs if isinstance(jobs, list) else []
applications = applications if isinstance(applications, list) else []
legacy_jobs = read_csv(JOBS_FILE)
shortlist = read_csv(SHORTLIST_FILE)

st.markdown(f"<div class='hero'><div class='kicker'>Company workspace · Signed in as {safe(me.get('email'))}</div><h1>Your hiring <span>overview</span></h1><p>Manage your own vacancies, monitor candidate applications, and move from job posting to shortlist in one workspace.</p></div>", unsafe_allow_html=True)

if jobs_error:
    st.warning("Database jobs could not be loaded: " + jobs_error)
if apps_error:
    st.warning("Applications could not be loaded: " + apps_error)

# Legacy jobs are stored in jobs.csv, while dashboard metrics use database jobs.
# Let the primary company admin import them once; the API prevents duplicates.
if not me.get("company_id") and not legacy_jobs.empty:
    with st.expander("Move legacy CSV jobs into your company dashboard", expanded=not bool(jobs)):
        st.write(f"Found {len(legacy_jobs)} legacy job(s) in jobs.csv. Import them into the database so they appear in Your Active Jobs and Your Job Postings.")
        if st.button("Import Legacy Jobs to Dashboard", type="primary", use_container_width=True):
            legacy_payload = legacy_jobs.fillna("").to_dict(orient="records")
            import_result, import_error = api_request(
                "POST", "/jobs/import-legacy", token=token, json={"jobs": legacy_payload}
            )
            if import_error:
                st.error("Legacy jobs could not be imported: " + import_error)
            else:
                st.success(
                    f"Imported {import_result.get('imported_count', 0)} job(s). "
                    f"Skipped {len(import_result.get('skipped', []))} duplicate or invalid job(s)."
                )
                if import_result.get("skipped"):
                    with st.expander("Import details"):
                        st.dataframe(pd.DataFrame(import_result["skipped"]), use_container_width=True, hide_index=True)
                st.rerun()

total_applications = len(applications)
shortlisted_count = sum(1 for row in applications if str(row.get("status", "")).lower() == "shortlisted")
active_jobs = sum(bool(row.get("is_active", True)) for row in jobs)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Your Active Jobs", active_jobs)
m2.metric("Applications", total_applications)
m3.metric("Shortlisted", shortlisted_count)
m4.metric("Your Job Postings", len(jobs))

left, right = st.columns([1.35, 1], gap="large")
with left:
    st.subheader("Your Recent Jobs")
    if not jobs:
        st.info("There are no database jobs for your account yet. Select Post a Job to create your first vacancy.")
    else:
        for job in jobs[:8]:
            status = "Active" if job.get("is_active") else "Closed"
            st.markdown(f"<div class='jobcard'><h4>{safe(job.get('title'))} <span class='pill'>{status}</span></h4><p><b>Department:</b> {safe(job.get('department'))} · <b>Applications:</b> {int(job.get('applications_count', 0))}</p></div>", unsafe_allow_html=True)
            if st.button("View applications", key=f"view_apps_{job.get('id')}"):
                st.session_state["dashboard_selected_job"] = job.get("id")
                st.rerun()

with right:
    st.subheader("Quick Actions")
    st.page_link("pages/2_Job_Posting.py", label="＋  Post a Job", use_container_width=True)
    st.page_link("pages/3_Match_Candidates.py", label="⌕  AI Candidate Matching", use_container_width=True)
    st.markdown("<div class='panel'><h4>Application privacy</h4><p>Only database applications for jobs belonging to your account are shown here. Applications from other companies are not exposed.</p></div>", unsafe_allow_html=True)

selected_job_id = st.session_state.get("dashboard_selected_job")
if selected_job_id is not None:
    st.divider()
    st.subheader("Applications for selected job")
    selected_apps = [row for row in applications if row.get("job_id") == selected_job_id]
    if not selected_apps:
        st.info("There are no applications for this job yet.")
    else:
        st.dataframe(pd.DataFrame([{
            "Candidate": row.get("candidate_name") or "Name not provided",
            "Email": row.get("candidate_email", ""),
            "Applied On": str(row.get("applied_at", ""))[:19].replace("T", " "),
            "Resume File": row.get("resume_filename", ""),
            "Status": row.get("status", "Applied"),
        } for row in selected_apps]), use_container_width=True, hide_index=True)

        st.markdown("### Candidate resumes")
        for row in selected_apps:
            candidate_label = row.get("candidate_name") or row.get("candidate_email") or f"Candidate {row.get('candidate_id')}"
            left_resume, right_resume = st.columns([3, 1])
            with left_resume:
                name_col, status_col = st.columns([3, 1.2])
                with name_col:
                    st.write(candidate_label)
                with status_col:
                    if str(row.get("status", "")).strip().casefold() == "shortlisted":
                        st.markdown(
                            "<span style='display:inline-block;background:#e4f6e9;color:#22643b;"
                            "border:1px solid #b8e2c4;border-radius:14px;padding:3px 9px;"
                            "font-size:12px;font-weight:700;white-space:nowrap'>✓ Shortlisted</span>",
                            unsafe_allow_html=True,
                        )
                st.caption(row.get("resume_filename") or "No saved resume filename")
            with right_resume:
                if row.get("resume_filename") and st.button("Load resume", key=f"load_resume_{row.get('id')}"):
                    resume_payload, resume_error = api_request(
                        "GET", f"/applications/{row.get('id')}/resume", token=token
                    )
                    if resume_error:
                        st.error("Resume unavailable: " + resume_error)
                    else:
                        st.session_state[f"resume_download_{row.get('id')}"] = resume_payload
            resume_payload = st.session_state.get(f"resume_download_{row.get('id')}")
            if resume_payload and resume_payload.get("resume_data"):
                try:
                    resume_bytes = base64.b64decode(resume_payload["resume_data"])
                    st.download_button(
                        f"Download {resume_payload.get('filename', 'resume.pdf')}",
                        data=resume_bytes,
                        file_name=resume_payload.get("filename", "candidate_resume.pdf"),
                        mime="application/pdf",
                        key=f"download_resume_{row.get('id')}",
                    )
                except Exception:
                    st.warning("This saved resume could not be decoded.")

        st.markdown("### 🤖 Automatic AI Candidate Ranking")
        matchable_apps = [row for row in selected_apps if str(row.get("resume_text") or "").strip()]
        job_description = next((str(row.get("job_description") or "") for row in selected_apps if row.get("job_description")), "")
        if not matchable_apps:
            st.info("Applicants will appear in AI ranking automatically after they save a readable PDF resume to their profile and apply.")
        elif not job_description.strip():
            st.warning("Job description is not available, so candidate matching cannot run for this job yet.")
        else:
            resumes = {}
            applicant_lookup = {}
            for row in matchable_apps:
                email = str(row.get("candidate_email") or "")
                label = str(row.get("candidate_name") or email or f"Candidate {row.get('candidate_id')}")
                unique_label = f"{label} ({email})" if email else label
                resumes[unique_label] = str(row.get("resume_text") or "")
                applicant_lookup[unique_label] = row
            try:
                ranked = match_candidates(job_description, resumes)
                ranked_rows = []
                for rank, candidate in enumerate(ranked, start=1):
                    row = applicant_lookup.get(candidate.get("name"), {})
                    ranked_rows.append({
                        "Rank": rank,
                        "Candidate": candidate.get("name", "Candidate"),
                        "Match Score": f"{float(candidate.get('final_score', 0)):.1f}%",
                        "Skill Coverage": f"{float(candidate.get('skill_coverage', 0)):.1f}%",
                        "Experience Fit": f"{float(candidate.get('experience_fit', 100)):.1f}%",
                        "Education Fit": f"{float(candidate.get('education_fit', 100)):.1f}%",
                        "Matched Skills": ", ".join(candidate.get("matched_skills") or []),
                        "Missing Skills": ", ".join(candidate.get("missing_skills") or []),
                        "Why this rank": " | ".join(candidate.get("reasons") or []),
                        "Application Status": row.get("status", "Applied"),
                        "Resume": row.get("resume_filename", ""),
                    })
                if ranked_rows:
                    st.dataframe(pd.DataFrame(ranked_rows), use_container_width=True, hide_index=True)
                    best = ranked_rows[0]
                    st.success(f"Best current match: {best['Candidate']} — {best['Match Score']}")
                    st.caption("Ranking updates from all applicants currently saved for this job. Scores are decision support; review each resume before shortlisting.")
                else:
                    st.info("No candidate matches were returned for this job.")
            except Exception as error:
                st.warning("Automatic matching could not run: " + str(error))

        status_options = ["Applied", "Under Review", "Shortlisted", "Rejected", "Selected"]
        chosen = st.selectbox("Update application status", status_options, key=f"status_{selected_job_id}")
        candidate_options = {f"{row.get('candidate_name') or row.get('candidate_email')} · #{row.get('id')}": row for row in selected_apps}
        chosen_candidate = st.selectbox("Candidate", list(candidate_options), key=f"candidate_status_{selected_job_id}")
        if st.button("Save status", type="primary"):
            application = candidate_options[chosen_candidate]
            _, error = api_request("PATCH", f"/applications/{application['id']}/status", token=token, params={"new_status": chosen})
            if error:
                st.error(error)
            else:
                st.success("Application status updated successfully.")
                st.rerun()

if not legacy_jobs.empty:
    st.divider()
    st.subheader("Legacy CSV jobs")
    st.caption("These jobs belong to the legacy jobs.csv workflow. Securely associating their applications with individual companies is a future migration step, so they are not included in database application counts.")
    st.metric("Legacy jobs in CSV", len(legacy_jobs))

if not me.get("company_id"):
    st.divider()
    st.subheader("🔐 Private Admin Verification")
    st.caption("Employee ID creation is locked. Enter the private setup key to unlock this section. The key is checked by the API and is never saved in the repository.")
    if not st.session_state.get("employee_setup_unlocked", False):
        with st.form("employee_setup_key_form"):
            employee_setup_key = st.text_input("Private setup key", type="password", help="Must match ADMIN_SETUP_KEY configured privately on the API host.")
            unlock_setup = st.form_submit_button("Unlock Employee ID Creation", type="primary", use_container_width=True)
        if unlock_setup:
            if not employee_setup_key:
                st.error("Enter the private setup key first.")
            else:
                _, key_error = api_request(
                    "POST",
                    "/auth/company/status",
                    headers={"X-Admin-Setup-Key": employee_setup_key},
                )
                if key_error:
                    st.error("Setup key was not accepted. Check the key and try again.")
                else:
                    st.session_state.employee_setup_unlocked = True
                    st.success("Verified. Employee ID creation is now unlocked for this session.")
                    st.rerun()
    else:
        st.success("Private setup key verified for this session.")
        if st.button("Lock Employee ID Creation", use_container_width=True):
            st.session_state.pop("employee_setup_unlocked", None)
            st.rerun()
        st.subheader("Create Multiple Employee Login IDs")
        st.caption("You can create up to 100 accounts at a time. Enter one account per line in this format: Name, email, password. Leave the password blank to generate a temporary password.")
        with st.form("bulk_company_users_form"):
            employee_rows = st.text_area(
                "Employee details (one employee per line)",
                placeholder="Amit Kumar, amit@company.com, TempPass123!\nNeha Singh, neha@company.com,",
                height=150,
                help="Comma-separated: Name, Email, optional Password. Email unique hona chahiye."
            )
            create_bulk = st.form_submit_button("Create Employee IDs", type="primary", use_container_width=True)
        if create_bulk:
            rows = []
            parse_errors = []
            for line_no, line in enumerate(employee_rows.splitlines(), start=1):
                if not line.strip():
                    continue
                parts = [part.strip() for part in line.split(",", 2)]
                if len(parts) < 2:
                    parse_errors.append(f"Line {line_no}: Separate the name and email with a comma.")
                    continue
                rows.append({"name": parts[0], "email": parts[1], "password": parts[2] if len(parts) > 2 else ""})
            if parse_errors:
                for message in parse_errors:
                    st.error(message)
            elif not rows:
                st.error("Please enter details for at least one employee.")
            elif len(rows) > 100:
                st.error("You can create a maximum of 100 accounts per batch.")
            else:
                result, error = api_request("POST", "/auth/company/bulk-create", token=token, json={"employees": rows})
                if error:
                    st.error("Accounts could not be created: " + error)
                else:
                    st.success(f"{result.get('created_count', 0)} employee account(s) created successfully.")
                    if result.get("created"):
                        st.warning("Copy the temporary passwords now and share them securely with the employees. They will not be displayed again.")
                        st.dataframe(pd.DataFrame(result["created"]), use_container_width=True, hide_index=True)
                        st.download_button(
                            "Download Employee Login Details (CSV)",
                            pd.DataFrame(result["created"]).to_csv(index=False).encode("utf-8-sig"),
                            file_name="employee_login_details.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    for item in result.get("errors", []):
                        st.error(f"Row {item.get('row')}: {item.get('email', '')} — {item.get('error')}")
    st.divider()
    st.caption("Instant Employee · Secure company workspace")

else:
    st.info("You are logged in with an employee account. Only the primary company admin can create employee login IDs.")
