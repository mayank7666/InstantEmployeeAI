from pathlib import Path
import html
import time
import pandas as pd
import requests
import streamlit as st

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
        return None, "API abhi available nahi hai. Thodi der baad dobara try karein."


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
        return "Yeh talent account hai. Company account se login karein."
    st.session_state.company_api_token = token
    st.session_state.company_logged_in = True
    st.session_state.company_email = me.get("email", "")
    return None


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
:root{--blue:#2454f5;--ink:#101828;--muted:#62718a;--line:#e5eaf2}
html,body,[class*="css"]{font-family:Inter,system-ui,sans-serif}
.stApp{background:#f6f8fc;color:#101828}
.main .block-container{max-width:1450px;padding-top:1rem;padding-bottom:2rem}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#101b2d,#16263e)}
[data-testid="stSidebar"] *{color:#f7f9ff}
[data-testid="stSidebarNav"]{display:none}
.hero{padding:30px 32px;border-radius:22px;border:1px solid #dfe7fb;background:linear-gradient(115deg,#f7f9ff,#eaf0ff);margin-bottom:22px}
.kicker{font-size:12px;letter-spacing:1.7px;text-transform:uppercase;font-weight:800;color:#2855e8}
.hero h1{font-size:clamp(32px,4vw,48px);line-height:1.08;letter-spacing:-1.8px;margin:12px 0;color:#101828}
.hero h1 span{color:#2454f5}.hero p{font-size:15px;line-height:1.7;color:#52637e;max-width:700px}
div[data-testid="stMetric"]{background:white;border:1px solid var(--line);border-radius:14px;padding:17px;box-shadow:0 4px 15px #263e7008}
div[data-testid="stMetric"] label{color:#62718a!important}div[data-testid="stMetricValue"]{color:#101828;font-weight:800}
.panel,.jobcard{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:14px}
.jobcard h4{margin:0 0 6px;color:#152541}.jobcard p{margin:4px 0;color:#62718a;font-size:13px}
.pill{display:inline-block;background:#dcfce7;color:#166534;border-radius:20px;padding:3px 9px;font-size:11px;font-weight:700}
.stButton>button{border-radius:9px!important;font-weight:700!important}
.stButton>button[kind="primary"]{background:#2454f5!important;border-color:#2454f5!important}
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
            for key in ("company_api_token", "company_logged_in", "company_email"):
                st.session_state.pop(key, None)
            st.rerun()

if not st.session_state.get("company_logged_in"):
    st.markdown("<div class='hero'><div class='kicker'>Secure company workspace</div><h1>Company <span>Dashboard</span></h1><p>Sign in to manage your own job postings and review applications submitted to your vacancies.</p></div>", unsafe_allow_html=True)
    login_tab, signup_tab = st.tabs(["Company Login", "Create Company Account"])
    with login_tab:
        with st.form("company_login_form"):
            email = st.text_input("Company email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login to Dashboard", type="primary", use_container_width=True)
        if submitted:
            if not email.strip() or not password:
                st.error("Email aur password dono fill karein.")
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
    with signup_tab:
        with st.form("company_signup_form"):
            company_name = st.text_input("Company / recruiter name")
            email = st.text_input("Company email", key="company_signup_email")
            password = st.text_input("Create password (minimum 8 characters)", type="password", key="company_signup_password")
            confirm = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create Company Account", type="primary", use_container_width=True)
        if submitted:
            if not company_name.strip() or not email.strip() or not password:
                st.error("Saare fields fill karein.")
            elif len(password) < 8:
                st.error("Password kam se kam 8 characters ka hona chahiye.")
            elif password != confirm:
                st.error("Passwords match nahi karte.")
            else:
                result, error = api_request("POST", "/auth/signup", json={"email": email.strip().lower(), "password": password, "role": "company", "full_name": company_name.strip()})
                if error:
                    st.error(error)
                else:
                    error = company_session(result["access_token"])
                    if error:
                        st.error(error)
                    else:
                        st.success("Company account create ho gaya.")
                        st.rerun()
    st.info("Company login aur candidate login alag hain. Company workspace ke liye company-role account use karein.")
    st.stop()

token = st.session_state.company_api_token
me, me_error = api_request("GET", "/me", token=token)
if me_error or not me or me.get("role") != "company":
    for key in ("company_api_token", "company_logged_in", "company_email"):
        st.session_state.pop(key, None)
    st.warning("Session expire ho gaya. Dobara login karein.")
    st.stop()

jobs, jobs_error = api_request("GET", "/jobs/mine", token=token)
applications, apps_error = api_request("GET", "/applications/company", token=token)
jobs = jobs if isinstance(jobs, list) else []
applications = applications if isinstance(applications, list) else []
legacy_jobs = read_csv(JOBS_FILE)
shortlist = read_csv(SHORTLIST_FILE)

st.markdown(f"<div class='hero'><div class='kicker'>Company workspace · Signed in as {safe(me.get('email'))}</div><h1>Your hiring <span>overview</span></h1><p>Manage your own vacancies, monitor candidate applications, and move from job posting to shortlist in one workspace.</p></div>", unsafe_allow_html=True)

if jobs_error:
    st.warning("Database jobs load nahi ho paaye: " + jobs_error)
if apps_error:
    st.warning("Applications load nahi ho paaye: " + apps_error)

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
        st.info("Abhi aapke account par database job nahi hai. Post a Job se pehli vacancy create karein.")
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
    st.markdown("<div class='panel'><h4>Application privacy</h4><p>Yahan sirf aapke account ke jobs par aayi database applications dikhengi. Dusri companies ki applications expose nahi hoti.</p></div>", unsafe_allow_html=True)

selected_job_id = st.session_state.get("dashboard_selected_job")
if selected_job_id is not None:
    st.divider()
    st.subheader("Applications for selected job")
    selected_apps = [row for row in applications if row.get("job_id") == selected_job_id]
    if not selected_apps:
        st.info("Is job ke liye abhi koi application nahi hai.")
    else:
        st.dataframe(pd.DataFrame([{
            "Candidate": row.get("candidate_name") or "Name not provided",
            "Email": row.get("candidate_email", ""),
            "Applied On": str(row.get("applied_at", ""))[:19].replace("T", " "),
            "Resume File": row.get("resume_filename", ""),
            "Status": row.get("status", "Applied"),
        } for row in selected_apps]), use_container_width=True, hide_index=True)
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
                st.success("Application status update ho gaya.")
                st.rerun()

if not legacy_jobs.empty:
    st.divider()
    st.subheader("Legacy CSV jobs")
    st.caption("Ye purane jobs.csv workflow ke jobs hain. Inke applications ko company-wise securely connect karna next migration step hai; inhe database application count mein include nahi kiya gaya.")
    st.metric("Legacy jobs in CSV", len(legacy_jobs))

st.divider()
st.caption("Instant Employee · Secure company workspace")
