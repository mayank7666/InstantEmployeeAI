from pathlib import Path
import html
import re
import sys
import pandas as pd
import requests
import streamlit as st
from pypdf import PdfReader

st.set_page_config(page_title="Instant Employee | AI Talent Platform", page_icon="✦", layout="wide")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DATA = ROOT / "data"
JOBS_FILE = DATA / "jobs.csv"
API_BASE_URL = "https://instant-employee-api.onrender.com"


def api_request(method, path, *, token=None, **kwargs):
    """Call the deployed FastAPI backend and return (data, error)."""
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.request(method, f"{API_BASE_URL}{path}", headers=headers, timeout=60, **kwargs)
        try:
            payload = response.json()
        except ValueError:
            payload = {"detail": response.text[:300]}
        if not response.ok:
            detail = payload.get("detail", f"API request failed ({response.status_code})") if isinstance(payload, dict) else f"API request failed ({response.status_code})"
            return None, str(detail)
        return payload, None
    except requests.RequestException:
        return None, "Backend is temporarily unavailable. Please try again in a moment."


def set_candidate_session(token):
    me, error = api_request("GET", "/me", token=token)
    if error:
        return error
    if me.get("role") != "talent":
        return "This login belongs to a company account. Please use the correct account type."
    st.session_state.candidate_api_token = token
    st.session_state.candidate_logged_in = True
    st.session_state.candidate_name = (me.get("profile") or {}).get("full_name") or me.get("email", "Candidate")
    st.session_state.candidate_email = me.get("email", "").lower()
    return None

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
:root{
  --bg:#070d18;--surface:#0c1526;--surface2:#111e33;--line:#203451;
  --ink:#f4f7ff;--muted:#a8b8d0;--blue:#1764ff;--cyan:#35b8ff;
}
html,body,[class*="css"]{font-family:Inter,system-ui,sans-serif}
.stApp{background:radial-gradient(circle at 85% 0%,#10234a 0%,transparent 32%),var(--bg);color:var(--ink)}
[data-testid="stAppViewContainer"],[data-testid="stHeader"]{background:transparent}
.main .block-container{max-width:1240px;padding-top:1rem;padding-bottom:3rem}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#080f1d,#0e1a2e);border-right:1px solid var(--line)}
[data-testid="stSidebar"] *{color:#f4f7ff}
[data-testid="stSidebarNav"]{display:none}
.stMarkdown,.stText,[data-testid="stCaptionContainer"],label,p,li{color:var(--muted)}
h1,h2,h3,h4,h5,h6,[data-testid="stMarkdownContainer"] strong{color:var(--ink)!important}
.hero{padding:42px;border-radius:24px;border:1px solid #203c68;background:radial-gradient(circle at 90% 5%,#102d70 0%,transparent 32%),linear-gradient(115deg,#0a1221,#0d1930);margin:12px 0 24px;box-shadow:0 16px 50px #0003}
.kicker{font-size:12px;letter-spacing:1.6px;text-transform:uppercase;font-weight:800;color:var(--cyan)}
.hero h1{font-size:clamp(36px,5vw,58px);line-height:1.04;letter-spacing:-2px;margin:13px 0;color:#f7faff}
.hero h1 span{color:#278bff}
.hero p{font-size:16px;line-height:1.75;color:#b5c6df;max-width:690px}
.panel{background:linear-gradient(145deg,#0b1424,#0b1527);border:1px solid var(--line);border-radius:17px;padding:22px;margin-bottom:16px}
.step{background:linear-gradient(145deg,#0c172a,#0a1221);border:1px solid var(--line);border-radius:14px;padding:18px;min-height:125px}
.stepnum{font-size:12px;color:#278bff;font-weight:900;letter-spacing:1px}
.jobcard{background:#0c1729;border:1px solid var(--line);border-radius:14px;padding:17px;margin:10px 0}
.smallmuted{color:#a8b8d0;font-size:13px}
div[data-testid="stMetric"]{background:#0c1729;border:1px solid var(--line);border-radius:14px;padding:16px}
div[data-testid="stMetric"] label,div[data-testid="stMetricValue"],div[data-testid="stMetricDelta"]{color:var(--ink)!important}
.stButton>button,[data-testid="stFormSubmitButton"] button{border-radius:10px!important;font-weight:750!important;min-height:43px;background:#17263d!important;color:#f4f7ff!important;border:1px solid #2a4264!important}
.stButton>button:hover,[data-testid="stFormSubmitButton"] button:hover{border-color:#278bff!important;color:#fff!important}
.stButton>button[kind="primary"],[data-testid="stFormSubmitButton"] button[kind="primary"]{background:linear-gradient(90deg,#0757f5,#176dff)!important;border-color:#176dff!important;color:#fff!important}
input,textarea,[data-baseweb="input"],[data-baseweb="textarea"]{background:#111827!important;color:#f7faff!important;border-color:#2a3c58!important}
[data-baseweb="input"] input{color:#f7faff!important;-webkit-text-fill-color:#f7faff!important}
[data-baseweb="select"]>div{background:#111827!important;color:#f7faff!important;border-color:#2a3c58!important}
[data-testid="stFileUploader"] section{background:#0c1729!important;border:1px dashed #2b4b78!important}
[data-testid="stFileUploader"] *{color:#d8e5fa!important}
[data-baseweb="tab-list"]{gap:8px;background:#0a1424;border-bottom:1px solid var(--line)}
[data-baseweb="tab"]{color:#a8b8d0!important}
[data-baseweb="tab"][aria-selected="true"]{color:#53baff!important;border-bottom-color:#278bff!important}
[data-testid="stAlert"]{background:#101f35!important;color:#dceaff!important;border:1px solid #29476c!important}
[data-testid="stAlert"] p{color:#dceaff!important}
hr{border-color:var(--line)!important}
a{color:#55baff!important}
@media(max-width:700px){.hero{padding:24px}.hero h1{letter-spacing:-1px}}
</style>
""", unsafe_allow_html=True)

def load_jobs():
    try:
        frame = pd.read_csv(JOBS_FILE).fillna("") if JOBS_FILE.exists() else pd.DataFrame()
        if "Status" in frame.columns:
            frame = frame[frame["Status"].astype(str).str.lower().isin(["active", "open", "published", ""])]
        return frame
    except Exception:
        return pd.DataFrame()

def extract_pdf_text(uploaded_file):
    reader = PdfReader(uploaded_file)
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()

def get_skills(text):
    from src.matching_engine import extract_skills
    return extract_skills(text)

def get_match_score(job_text, resume_text):
    from src.matching_engine import calculate_similarity, extract_skills
    lexical = calculate_similarity(job_text, [resume_text])[0] * 100
    required = extract_skills(job_text)
    candidate = set(extract_skills(resume_text))
    matched = [s for s in required if s in candidate]
    missing = [s for s in required if s not in candidate]
    coverage = len(matched) / len(required) * 100 if required else lexical
    score = (0.5 * lexical + 0.5 * coverage) if required else lexical
    return round(score, 1), round(lexical, 1), matched, missing

jobs = load_jobs()
if "view" not in st.session_state:
    st.session_state.view = "home"

with st.sidebar:
    st.markdown("<div style='font-size:23px;font-weight:900;padding:8px 0'>✦ Instant Employee</div><div style='color:#aab8cf;font-size:12px'>AI Talent Platform</div>", unsafe_allow_html=True)
    st.divider()
    st.caption("CANDIDATE")
    if st.button("⌂  Home", use_container_width=True):
        st.session_state.view = "home"; st.rerun()
    if st.button("⇧  Upload Resume", use_container_width=True):
        st.session_state.view = "candidate"; st.rerun()
    if st.session_state.get("candidate_logged_in"):
        if st.button("▦  My Profile", use_container_width=True):
            st.session_state.view = "candidate_dashboard"; st.rerun()
        if st.button("✓  Applied Jobs", use_container_width=True):
            st.session_state.view = "applied_jobs"; st.rerun()
    else:
        if st.button("👤  Candidate Login / Signup", use_container_width=True):
            st.session_state.view = "candidate_auth"; st.rerun()
    st.divider()
    st.caption("COMPANY ACCESS")
    if st.button("▣  Employee Login", use_container_width=True):
        st.session_state.view = "employee"; st.rerun()
    if st.session_state.get("candidate_logged_in"):
        st.caption("Signed in: " + st.session_state.get("candidate_name", "Candidate"))
        if st.button("Log out", use_container_width=True):
            for key in ["candidate_logged_in","candidate_name","candidate_email","candidate_api_token","resume_text","resume_filename","match_results"]:
                st.session_state.pop(key, None)
            st.session_state.view = "home"; st.rerun()

view = st.session_state.view

if view == "home":
    st.markdown("<div style='font-size:23px;font-weight:900'>✦ Instant Employee <span style='font-size:12px;color:#a8b8d0;font-weight:500;margin-left:8px'>AI CAREER PLATFORM</span></div>", unsafe_allow_html=True)
    st.markdown("""<div class="hero"><div class="kicker">YOUR NEXT OPPORTUNITY STARTS HERE</div>
    <h1>Find work that fits<br> <span>your skills.</span></h1>
    <p>Explore opportunities, discover roles that match your experience, and use AI-assisted resume matching to find your next career move.</p></div>""", unsafe_allow_html=True)

    # Job search controls
    st.markdown("### Find your next role")
    search_col, dept_col, mode_col = st.columns([2, 1, 1])
    with search_col:
        search_text = st.text_input("Search jobs", placeholder="Job title, skill, or keyword", key="home_job_search")
    title_col = next((c for c in jobs.columns if str(c).strip().lower() in {"job title", "title", "job_title"}), None)
    desc_col = next((c for c in jobs.columns if str(c).strip().lower() in {"description", "job description", "job_description"}), None)
    skills_col = next((c for c in jobs.columns if str(c).strip().lower() in {"required skills", "required_skills", "skills"}), None)
    dept_col_name = next((c for c in jobs.columns if str(c).strip().lower() in {"department", "category", "job category"}), None)
    work_mode_col = next((c for c in jobs.columns if str(c).strip().lower() in {"work mode", "work_mode", "mode"}), None)
    with dept_col:
        departments = sorted({str(x).strip() for x in jobs[dept_col_name].tolist() if str(x).strip()}) if dept_col_name and not jobs.empty else []
        category_options = ["All categories"] + departments
        selected_department = st.selectbox(
            "Category",
            category_options,
            index=0,
            key="home_category_filter",
            help="Choose a category from the jobs currently posted.",
        )
    with mode_col:
        modes = sorted({str(x).strip() for x in jobs[work_mode_col].tolist() if str(x).strip()}) if work_mode_col and not jobs.empty else []
        selected_mode = st.selectbox("Work mode", ["All modes"] + modes, index=0, key="home_work_mode_filter")

    filtered_jobs = jobs.copy()
    if search_text.strip() and not filtered_jobs.empty:
        searchable_cols = [c for c in [title_col, desc_col, skills_col, dept_col_name] if c]
        if searchable_cols:
            # Match individual query terms across title, skills, category and description.
            # Then rank exact/strong title matches above weaker description matches.
            query = search_text.strip()
            terms = [term for term in query.split() if term]
            searchable_text = filtered_jobs[searchable_cols].astype(str).apply(
                lambda row: " ".join(row.values), axis=1
            )
            term_mask = searchable_text.apply(
                lambda value: all(term.casefold() in value.casefold() for term in terms)
            )
            filtered_jobs = filtered_jobs[term_mask].copy()

            if not filtered_jobs.empty:
                def _job_relevance(row):
                    title = str(row.get(title_col, "")) if title_col else ""
                    skills = str(row.get(skills_col, "")) if skills_col else ""
                    category = str(row.get(dept_col_name, "")) if dept_col_name else ""
                    description = str(row.get(desc_col, "")) if desc_col else ""
                    q = query.casefold()
                    score = 0
                    if title.casefold() == q:
                        score += 100
                    if q in title.casefold():
                        score += 60
                    score += sum(12 for term in terms if term.casefold() in title.casefold())
                    score += sum(8 for term in terms if term.casefold() in skills.casefold())
                    score += sum(5 for term in terms if term.casefold() in category.casefold())
                    score += sum(2 for term in terms if term.casefold() in description.casefold())
                    return score

                filtered_jobs["_search_relevance"] = filtered_jobs.apply(_job_relevance, axis=1)
                filtered_jobs = filtered_jobs.sort_values(
                    "_search_relevance", ascending=False, kind="stable"
                ).drop(columns=["_search_relevance"])

    # Category dropdown filters only categories that actually exist in jobs.csv.
    if selected_department != "All categories" and dept_col_name:
        filtered_jobs = filtered_jobs[
            filtered_jobs[dept_col_name].astype(str).str.casefold()
            == str(selected_department).casefold()
        ]

    if selected_mode != "All modes" and work_mode_col:
        filtered_jobs = filtered_jobs[
            filtered_jobs[work_mode_col].astype(str).str.casefold() == str(selected_mode).casefold()
        ]

    count_a, count_b = st.columns([3, 1])
    with count_a:
        st.markdown("### Latest opportunities")
        st.caption("Open a job to read the full description and apply.")
    with count_b:
        st.metric("Available jobs", len(filtered_jobs))

    if filtered_jobs.empty:
        st.info(
            "No jobs match these filters yet. Try another keyword, choose All categories / All modes, "
            "or check back after new jobs are posted."
        )
    else:
        for row_index, job in filtered_jobs.iterrows():
            title = str(job.get(title_col, "Open role")) if title_col else "Open role"
            department = str(job.get(dept_col_name, "Technology")) if dept_col_name else "Technology"
            description = str(job.get(desc_col, "")) if desc_col else ""
            skills = str(job.get(skills_col, "Skills listed in job description")) if skills_col else "Skills listed in job description"
            mode = str(job.get(work_mode_col, "Not specified")) if work_mode_col else "Not specified"
            low_col = next((c for c in jobs.columns if str(c).strip().lower() in {"minimum budget", "min budget", "minimum_budget"}), None)
            high_col = next((c for c in jobs.columns if str(c).strip().lower() in {"maximum budget", "max budget", "maximum_budget"}), None)
            low = str(job.get(low_col, "")) if low_col else ""
            high = str(job.get(high_col, "")) if high_col else ""
            budget = f"₹{low or '—'} – ₹{high or '—'}" if low or high else "Budget discussed during hiring"
            st.markdown(f"""<div class='jobcard'><div style='display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap'><div><div class='kicker'>{html.escape(department)}</div><h3 style='margin:7px 0'>{html.escape(title)}</h3></div><span style='height:fit-content;border:1px solid #29476c;border-radius:20px;padding:5px 10px;color:#d7e7ff;font-size:12px'>{html.escape(mode)}</span></div><p>{html.escape(description[:240] + ('…' if len(description)>240 else '') or 'Open this role to view the complete job description.')}</p><p><b>Required skills:</b> {html.escape(skills[:180])}</p><p><b>Budget:</b> {html.escape(budget)}</p></div>""", unsafe_allow_html=True)
            view_col, apply_col = st.columns([1, 1])
            with view_col:
                if st.button("View job details  →", key=f"view_job_{row_index}", use_container_width=True):
                    st.session_state.selected_job_index = row_index
                    st.session_state.view = "job_details"
                    st.rerun()
            with apply_col:
                if st.button("Apply now  →", key=f"apply_job_card_{row_index}", type="primary", use_container_width=True):
                    st.session_state.apply_job_index = row_index
                    st.session_state.pop("application_submitted", None)
                    if st.session_state.get("candidate_logged_in"):
                        st.session_state.view = "apply_resume"
                    else:
                        st.session_state.view = "candidate_auth"
                    st.rerun()

    st.markdown("### How it works")
    columns = st.columns(4)
    steps = [("01", "Explore jobs", "Search roles and review job details."), ("02", "Create account", "Sign in when you are ready to apply."), ("03", "Upload resume", "Share a readable PDF resume."), ("04", "AI job matching", "Review relevant skills and match estimates.")]
    for box, (number, title, desc) in zip(columns, steps):
        with box:
            st.markdown(f"<div class='step'><div class='stepnum'>{number}</div><h4>{title}</h4><div class='smallmuted'>{desc}</div></div>", unsafe_allow_html=True)
    st.caption("Candidate accounts and the company workspace are separate.")

elif view == "job_details":
    selected_index = st.session_state.get("selected_job_index")
    if selected_index not in jobs.index:
        st.warning("This job is no longer available. Please return to the job list.")
    else:
        job = jobs.loc[selected_index]
        def job_col(names):
            return next((c for c in jobs.columns if str(c).strip().lower() in names), None)
        title_col = job_col({"job title", "title", "job_title"})
        desc_col = job_col({"description", "job description", "job_description"})
        skills_col = job_col({"required skills", "required_skills", "skills"})
        dept_col = job_col({"department", "category", "job category"})
        mode_col = job_col({"work mode", "work_mode", "mode"})
        low_col = job_col({"minimum budget", "min budget", "minimum_budget"})
        high_col = job_col({"maximum budget", "max budget", "maximum_budget"})
        title = str(job.get(title_col, "Open role")) if title_col else "Open role"
        description = str(job.get(desc_col, "Description not provided.")) if desc_col else "Description not provided."
        skills = str(job.get(skills_col, "Not specified")) if skills_col else "Not specified"
        department = str(job.get(dept_col, "Technology")) if dept_col else "Technology"
        mode = str(job.get(mode_col, "Not specified")) if mode_col else "Not specified"
        low = str(job.get(low_col, "")) if low_col else ""
        high = str(job.get(high_col, "")) if high_col else ""
        st.button("← Back to jobs", on_click=lambda: st.session_state.update(view="home"))
        st.markdown(f"<div class='hero'><div class='kicker'>{html.escape(department)} · {html.escape(mode)}</div><h1>{html.escape(title)}</h1><p>Review the role requirements and apply when you are ready.</p></div>", unsafe_allow_html=True)
        st.markdown("### Job description")
        st.write(description or "Description not provided.")
        st.markdown("### Required skills")
        st.write(skills or "Not specified")
        st.markdown("### Budget")
        st.write(f"₹{low or '—'} – ₹{high or '—'}" if low or high else "Budget discussed during hiring")
        if st.button("Apply for this job  →", type="primary", use_container_width=True):
            st.session_state.apply_job_index = selected_index
            st.session_state.pop("application_submitted", None)
            if st.session_state.get("candidate_logged_in"):
                st.session_state.view = "apply_resume"
            else:
                st.session_state.view = "candidate_auth"
            st.rerun()

elif view == "candidate_auth":
    st.markdown("## Candidate account")
    st.caption("Sign in with the live Instant Employee API. Use at least 8 characters for your password.")
    login, signup = st.tabs(["Login", "Create account"])
    with login:
        with st.form("candidate_login"):
            email = st.text_input("Email address", key="candidate_login_email")
            password = st.text_input("Password", type="password", key="candidate_login_password")
            submit = st.form_submit_button("Login", type="primary", use_container_width=True)
        if submit:
            if not email.strip() or not password:
                st.error("Enter your email and password.")
            else:
                token_data, error = api_request(
                    "POST", "/auth/login",
                    data={"username": email.strip().lower(), "password": password},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                if error:
                    st.error(error)
                else:
                    error = set_candidate_session(token_data["access_token"])
                    if error:
                        st.error(error)
                    else:
                        st.session_state.view = "apply_resume" if st.session_state.get("apply_job_index") is not None else "candidate_dashboard"
                        st.rerun()
    with signup:
        with st.form("candidate_signup"):
            name = st.text_input("Full name", key="candidate_signup_name")
            email = st.text_input("Email address", key="candidate_signup_email")
            password = st.text_input("Create password", type="password", key="candidate_signup_password")
            confirm = st.text_input("Confirm password", type="password", key="candidate_signup_confirm")
            submit = st.form_submit_button("Create candidate account", type="primary", use_container_width=True)
        if submit:
            if not name.strip() or not email.strip() or not password:
                st.error("Please fill in every field.")
            elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()):
                st.error("Enter a valid email address.")
            elif len(password) < 8:
                st.error("Password must contain at least 8 characters.")
            elif password != confirm:
                st.error("Passwords do not match.")
            else:
                token_data, error = api_request(
                    "POST", "/auth/signup",
                    json={"email": email.strip().lower(), "password": password, "role": "talent", "full_name": name.strip()},
                )
                if error:
                    st.error(error)
                else:
                    error = set_candidate_session(token_data["access_token"])
                    if error:
                        st.error(error)
                    else:
                        st.success("Candidate account created successfully.")
                        st.session_state.view = "apply_resume" if st.session_state.get("apply_job_index") is not None else "candidate_dashboard"
                        st.rerun()
    if st.button("← Back to home"):
        st.session_state.view = "home"; st.rerun()

elif view == "apply_resume":
    if not st.session_state.get("candidate_logged_in"):
        st.info("Please log in or create a candidate account to apply.")
        if st.button("Continue to Candidate Login", type="primary", use_container_width=True):
            st.session_state.view = "candidate_auth"
            st.rerun()
    else:
        selected_index = st.session_state.get("apply_job_index")
        if selected_index not in jobs.index:
            st.warning("Please select a job from the home page before applying.")
            if st.button("Back to jobs"):
                st.session_state.view = "home"
                st.rerun()
        else:
            selected_job = jobs.loc[selected_index]
            apply_title_col = next((c for c in jobs.columns if str(c).strip().lower() in {"job title", "title", "job_title"}), None)
            apply_title = str(selected_job.get(apply_title_col, "Selected job")) if apply_title_col else "Selected job"
            st.markdown("## Apply for this job")
            st.markdown(f"### {html.escape(apply_title)}")
            st.caption("Upload your resume as a PDF to submit your application.")
            with st.form("submit_job_application"):
                application_resume = st.file_uploader("Upload resume (PDF)", type=["pdf"], key="application_resume_pdf")
                submit_application = st.form_submit_button("Submit application", type="primary", use_container_width=True)
            if submit_application:
                if application_resume is None:
                    st.error("Please upload your resume PDF first.")
                else:
                    try:
                        uploaded_text = extract_pdf_text(application_resume)
                        if not uploaded_text:
                            st.error("No readable text found in this PDF. Please upload a text-based PDF.")
                        else:
                            st.session_state.application_resume_name = application_resume.name
                            st.session_state.application_resume_text = uploaded_text
                            st.session_state.application_submitted = True
                            title_col = next((c for c in jobs.columns if str(c).strip().lower() in {"job title", "title", "job_title"}), None)
                            company_col = next((c for c in jobs.columns if str(c).strip().lower() in {"company", "company name", "employer"}), None)
                            job_id_col = next((c for c in jobs.columns if str(c).strip().lower() in {"job id", "job_id", "id"}), None)
                            job_record_id = str(selected_job.get(job_id_col, selected_index)) if job_id_col else str(selected_index)
                            applications = st.session_state.setdefault("candidate_applications", {})
                            candidate_email = st.session_state.get("candidate_email", "guest").strip().lower()
                            candidate_list = applications.setdefault(candidate_email, [])
                            if not any(app.get("job_id") == job_record_id for app in candidate_list):
                                candidate_list.insert(0, {"job_id": job_record_id, "title": apply_title, "company": str(selected_job.get(company_col, "Company not specified")) if company_col else "Company not specified", "applied_on": __import__("datetime").datetime.now().strftime("%d %b %Y, %I:%M %p"), "status": "Application submitted", "resume": application_resume.name})
                                st.success("✓ Resume uploaded successfully! Your application has been submitted.")
                            else:
                                st.info("You have already applied to this job from this account. It is listed in Applied Jobs.")
                            st.info("This prototype confirms the application in the current session. Persistent storage and company-side application tracking will be added in a later step.")
                    except Exception as error:
                        st.error(f"Could not read this PDF: {error}")
            if st.session_state.get("application_submitted"):
                st.caption("Resume: " + st.session_state.get("application_resume_name", "Uploaded PDF"))
            if st.button("← Back to jobs"):
                st.session_state.view = "home"
                st.rerun()

elif view == "candidate_dashboard":
    if not st.session_state.get("candidate_logged_in"):
        st.warning("Please log in to view your profile.")
        if st.button("Candidate Login / Signup", type="primary"):
            st.session_state.view = "candidate_auth"; st.rerun()
    else:
        email = st.session_state.get("candidate_email", "").strip().lower()
        applications = st.session_state.get("candidate_applications", {}).get(email, [])
        header_col, logout_col = st.columns([5, 1])
        with header_col:
            st.markdown("## 👋 My Profile")
        with logout_col:
            if st.button("Log out", key="candidate_dashboard_logout", use_container_width=True):
                for key in ["candidate_logged_in", "candidate_name", "candidate_email", "candidate_api_token", "resume_text", "resume_filename", "match_results"]:
                    st.session_state.pop(key, None)
                st.session_state.view = "home"
                st.rerun()

        token = st.session_state.get("candidate_api_token")
        profile, profile_error = api_request("GET", "/profiles/me", token=token)
        if profile_error:
            st.error("Profile load nahi ho paya: " + profile_error)
            profile = {
                "full_name": st.session_state.get("candidate_name", ""),
                "headline": "", "skills": "", "timezone": "Asia/Kolkata",
                "availability": "Available", "portfolio_url": "", "resume_filename": "",
                "completion_percent": 0,
            }

        st.caption("Welcome back, " + st.session_state.get("candidate_name", "Candidate") + ". Your profile details are saved to the backend.")
        st.metric("Profile completion", str(profile.get("completion_percent", 0)) + "%")
        st.progress(max(0, min(100, int(profile.get("completion_percent", 0)))) / 100)

        st.markdown("### Edit profile")
        with st.form("candidate_profile_edit"):
            profile_name = st.text_input("Full name", value=profile.get("full_name", "") or "")
            profile_headline = st.text_input("Professional headline", value=profile.get("headline", "") or "", placeholder="e.g. AIML Fresher | Python | Machine Learning")
            profile_skills = st.text_area("Skills (comma-separated)", value=profile.get("skills", "") or "", placeholder="Python, SQL, Machine Learning, Power BI")
            profile_timezone = st.text_input("Timezone", value=profile.get("timezone", "Asia/Kolkata") or "Asia/Kolkata")
            availability_options = ["Available", "Open to opportunities", "Part-time", "Not available"]
            current_availability = profile.get("availability", "Available") or "Available"
            availability_index = availability_options.index(current_availability) if current_availability in availability_options else 0
            profile_availability = st.selectbox("Availability", availability_options, index=availability_index)
            profile_portfolio = st.text_input("Portfolio URL", value=profile.get("portfolio_url", "") or "", placeholder="https://...")
            save_profile = st.form_submit_button("Save profile", type="primary", use_container_width=True)

        if save_profile:
            if not profile_name.strip():
                st.error("Full name is required.")
            else:
                updated_profile, save_error = api_request(
                    "PUT", "/profiles/me", token=token,
                    json={
                        "full_name": profile_name.strip(),
                        "headline": profile_headline.strip(),
                        "skills": profile_skills.strip(),
                        "timezone": profile_timezone.strip() or "Asia/Kolkata",
                        "availability": profile_availability,
                        "portfolio_url": profile_portfolio.strip(),
                        "resume_filename": profile.get("resume_filename", "") or "",
                    },
                )
                if save_error:
                    st.error("Profile save nahi hua: " + save_error)
                else:
                    st.session_state.candidate_name = updated_profile.get("full_name", profile_name.strip())
                    st.session_state.profile_saved_message = "Profile database mein successfully save ho gaya."
                    st.rerun()

        if st.session_state.pop("profile_saved_message", None):
            st.success("Profile database mein successfully save ho gaya.")

        if profile.get("resume_filename"):
            st.caption("Saved resume filename: " + html.escape(profile.get("resume_filename", "")))
        st.divider()
        a, b, c = st.columns(3)
        a.metric("Total Jobs Applied", len(applications))
        b.metric("In Progress", sum(1 for app in applications if app.get("status") not in {"Rejected", "Selected", "Offer received"}))
        c.metric("Selected / Offers", sum(1 for app in applications if app.get("status") in {"Selected", "Offer received"}))
        st.markdown("### Recent Applications")
        if not applications:
            st.info("You have not applied to any jobs yet. Browse jobs and select Apply now to get started.")
            if st.button("Find jobs", type="primary"):
                st.session_state.view = "home"; st.rerun()
        else:
            for app in applications[:5]:
                with st.container(border=True):
                    left, right = st.columns([3, 1])
                    with left:
                        st.markdown("#### " + html.escape(app.get("title", "Job")))
                        st.caption(html.escape(app.get("company", "Company not specified")) + " · Applied " + html.escape(app.get("applied_on", "")))
                    with right:
                        st.caption("APPLICATION STATUS")
                        st.markdown("**" + html.escape(app.get("status", "Application submitted")) + "**")
            if st.button("View all applied jobs", type="primary"):
                st.session_state.view = "applied_jobs"; st.rerun()
        st.info("Note: profile details save to the backend database. Application history is still session-based and will be connected separately.")
 
elif view == "applied_jobs":
    if not st.session_state.get("candidate_logged_in"):
        st.warning("Please log in to view your applied jobs.")
        if st.button("Candidate Login / Signup", type="primary"):
            st.session_state.view = "candidate_auth"; st.rerun()
    else:
        email = st.session_state.get("candidate_email", "").strip().lower()
        applications = st.session_state.get("candidate_applications", {}).get(email, [])
        st.markdown("## ✓ Applied Jobs")
        st.caption("Your application history and current status")
        st.metric("Total applications", len(applications))
        if not applications:
            st.info("No applications yet. When you apply to a job, it will appear here.")
        else:
            filter_status = st.selectbox("Filter by status", ["All statuses"] + sorted({app.get("status", "Application submitted") for app in applications}))
            visible = applications if filter_status == "All statuses" else [app for app in applications if app.get("status") == filter_status]
            for app in visible:
                with st.container(border=True):
                    st.markdown("### " + html.escape(app.get("title", "Job")))
                    st.write("**Company:** " + html.escape(app.get("company", "Company not specified")))
                    st.write("**Applied on:** " + html.escape(app.get("applied_on", "Not available")))
                    st.write("**Status:** " + html.escape(app.get("status", "Application submitted")))
                    st.caption("Resume: " + html.escape(app.get("resume", "Uploaded PDF")))
        if st.button("← Back to My Profile"):
            st.session_state.view = "candidate_dashboard"; st.rerun()

elif view == "candidate":
    if not st.session_state.get("candidate_logged_in"):
        st.warning("Please log in or create a candidate account first.")
        if st.button("Go to Candidate Login"):
            st.session_state.view = "candidate_auth"; st.rerun()
    else:
        st.markdown(f"## Resume workspace")
        st.caption(f"Welcome, {html.escape(st.session_state.get('candidate_name','Candidate'))}. Upload your resume to see matching jobs.")
        resume_file = st.file_uploader("Upload your resume (PDF)", type=["pdf"], key="candidate_resume")
        if resume_file is not None and st.button("Analyze resume & find matching jobs", type="primary", use_container_width=True):
            try:
                resume_text = extract_pdf_text(resume_file)
                if not resume_text:
                    st.error("No readable text was found. Please upload a text-based PDF.")
                else:
                    st.session_state.resume_text = resume_text
                    st.session_state.resume_filename = resume_file.name
                    results = []
                    if jobs.empty:
                        st.warning("No jobs are available yet. Please check again after the company posts jobs.")
                    else:
                        def find_col(names):
                            return next((c for c in jobs.columns if c.strip().lower() in names), None)
                        title_col = find_col({"job title","title","job_title"})
                        desc_col = find_col({"description","job description","job_description"})
                        skills_col = find_col({"required skills","required_skills","skills"})
                        dept_col = find_col({"department"})
                        mode_col = find_col({"work mode","work_mode"})
                        low_col = find_col({"minimum budget","min budget","minimum_budget"})
                        high_col = find_col({"maximum budget","max budget","maximum_budget"})
                        for _, job in jobs.iterrows():
                            title = str(job.get(title_col, "Open role")) if title_col else "Open role"
                            description = str(job.get(desc_col, "")) if desc_col else ""
                            required = str(job.get(skills_col, "")) if skills_col else ""
                            score, lexical, matched, missing = get_match_score(f"{title}. {description}. Required skills: {required}", resume_text)
                            results.append({"title":title,"description":description,"department":str(job.get(dept_col,"Not specified")) if dept_col else "Not specified","mode":str(job.get(mode_col,"Not specified")) if mode_col else "Not specified","low":str(job.get(low_col,"")) if low_col else "","high":str(job.get(high_col,"")) if high_col else "","score":score,"lexical":lexical,"matched":matched,"missing":missing})
                        results.sort(key=lambda item:item["score"], reverse=True)
                        st.session_state.match_results = results
                        st.success(f"Resume analyzed. Found {len(results)} job match(es).")
            except Exception as error:
                st.error(f"Could not read this resume: {error}")
        if st.session_state.get("resume_text"):
            st.markdown("### Resume analysis")
            st.caption("File: " + st.session_state.get("resume_filename","Resume"))
            found = get_skills(st.session_state.resume_text)
            st.metric("Recognized skills", len(found))
            st.write(", ".join(found) if found else "No recognized skills from the current skill catalog were detected.")
            results = st.session_state.get("match_results", [])
            if results:
                st.markdown("### Your job matches")
                st.caption("Scores are AI-assisted estimates based on text similarity and recognized skill coverage, not a hiring decision.")
                for item in results:
                    with st.container(border=True):
                        a,b = st.columns([3,1])
                        with a:
                            st.markdown("#### " + item["title"])
                            st.caption(item["department"] + " · " + item["mode"])
                            st.write(item["description"] or "Job description not provided.")
                            if item["matched"]: st.write("**Matching skills:** " + ", ".join(item["matched"]))
                            if item["missing"]: st.write("**Skills to build:** " + ", ".join(item["missing"]))
                        with b:
                            st.metric("Match score", f"{item['score']}%")
                            st.caption(f"Text similarity: {item['lexical']}%")
                            if item["low"] or item["high"]: st.caption(f"Budget: ₹{item['low'] or '—'} – ₹{item['high'] or '—'}")
        if st.button("← Back to home"):
            st.session_state.view = "home"; st.rerun()

elif view == "employee":
    st.markdown("## Company employee login")
    st.caption("Use the employee ID and password assigned by the company. Successful login opens the existing company dashboard.")
    with st.form("employee_login"):
        employee_id = st.text_input("Employee ID")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login to company dashboard", type="primary", use_container_width=True)
    if submit:
        try:
            valid_id = str(st.secrets["employee_login"]["username"])
            valid_password = str(st.secrets["employee_login"]["password"])
        except Exception:
            valid_id, valid_password = "", ""
        if not valid_id or not valid_password:
            st.error("Employee credentials are not configured. Add employee_login.username and employee_login.password in Streamlit Cloud → App settings → Secrets.")
        elif employee_id.strip() == valid_id and password == valid_password:
            st.session_state.employee_authenticated = True
            st.switch_page("pages/4_Employee_Dashboard.py")
        else:
            st.error("Incorrect employee ID or password.")
    st.info("Candidate accounts cannot open the company dashboard.")
    if st.button("← Back to home"):
        st.session_state.view = "home"; st.rerun()

st.divider()
st.caption("Instant Employee AI · Candidate portal and company workspace")
