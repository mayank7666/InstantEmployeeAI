from pathlib import Path
import html
import re
import pandas as pd
import streamlit as st
from pypdf import PdfReader

st.set_page_config(page_title="Instant Employee | AI Talent Platform", page_icon="✦", layout="wide")
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
JOBS_FILE = DATA / "jobs.csv"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
html,body,[class*="css"]{font-family:Inter,system-ui,sans-serif}
.stApp{background:#f6f8fc;color:#101828}
.main .block-container{max-width:1240px;padding-top:1rem;padding-bottom:3rem}
[data-testid="stSidebar"]{background:#101b2d}
[data-testid="stSidebar"] *{color:#f7f9ff}
[data-testid="stSidebarNav"]{display:none}
.hero{padding:42px;border-radius:24px;border:1px solid #dfe7fb;background:radial-gradient(circle at 85% 15%,#dce6ff,transparent 30%),linear-gradient(115deg,#fff,#edf2ff);margin:12px 0 24px}
.kicker{font-size:12px;letter-spacing:1.6px;text-transform:uppercase;font-weight:800;color:#2454f5}
.hero h1{font-size:clamp(36px,5vw,58px);line-height:1.04;letter-spacing:-2px;margin:13px 0;color:#101828}
.hero h1 span{color:#2454f5}
.hero p{font-size:16px;line-height:1.75;color:#52637e;max-width:690px}
.panel{background:#fff;border:1px solid #e5eaf2;border-radius:17px;padding:22px;margin-bottom:16px}
.step{background:#fff;border:1px solid #e5eaf2;border-radius:14px;padding:18px;min-height:125px}
.stepnum{font-size:12px;color:#2454f5;font-weight:900;letter-spacing:1px}
.jobcard{background:#fff;border:1px solid #e5eaf2;border-radius:14px;padding:17px;margin:10px 0}
.smallmuted{color:#62718a;font-size:13px}
div[data-testid="stMetric"]{background:white;border:1px solid #e5eaf2;border-radius:14px;padding:16px}
.stButton>button{border-radius:10px!important;font-weight:750!important;min-height:43px}
.stButton>button[kind="primary"]{background:#2454f5!important;border-color:#2454f5!important}
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
    st.divider()
    st.caption("COMPANY ACCESS")
    if st.button("▣  Employee Login", use_container_width=True):
        st.session_state.view = "employee"; st.rerun()
    if st.session_state.get("candidate_logged_in"):
        st.caption("Signed in: " + st.session_state.get("candidate_name", "Candidate"))
        if st.button("Log out", use_container_width=True):
            for key in ["candidate_logged_in","candidate_name","candidate_email","resume_text","resume_filename","match_results"]:
                st.session_state.pop(key, None)
            st.session_state.view = "home"; st.rerun()

view = st.session_state.view

if view == "home":
    st.markdown("<div style='font-size:23px;font-weight:900'>✦ Instant Employee</div>", unsafe_allow_html=True)
    st.markdown("""<div class="hero"><div class="kicker">AI-powered career matching</div>
    <h1>Your skills deserve<br>the <span>right opportunity.</span></h1>
    <p>Discover roles that fit your skills. Create your candidate account, upload your resume, and let our AI-assisted matching engine compare your experience with available jobs.</p></div>""", unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("<div class='panel'><div class='kicker'>FOR JOB SEEKERS</div><h3>Find a role that fits you</h3><p class='smallmuted'>Create your candidate account, upload a PDF resume and review your job-match results.</p></div>", unsafe_allow_html=True)
        if st.button("Candidate Login / Sign Up  →", type="primary", use_container_width=True):
            st.session_state.view = "candidate_auth"; st.rerun()
    with right:
        st.markdown("<div class='panel'><div class='kicker'>FOR COMPANY EMPLOYEES</div><h3>Company workspace</h3><p class='smallmuted'>Authorized employees use their assigned ID and password to open the internal dashboard.</p></div>", unsafe_allow_html=True)
        if st.button("Employee Login  →", use_container_width=True):
            st.session_state.view = "employee"; st.rerun()
    st.markdown("### How it works")
    columns = st.columns(4)
    steps = [("01","Create account","Sign in as a candidate."),("02","Upload resume","Upload a readable PDF."),("03","AI analysis","Extract skills and compare job requirements."),("04","View matches","Review scores and skill gaps.")]
    for box, (number,title,desc) in zip(columns, steps):
        with box:
            st.markdown(f"<div class='step'><div class='stepnum'>{number}</div><h4>{title}</h4><div class='smallmuted'>{desc}</div></div>", unsafe_allow_html=True)
    st.caption(f"{len(jobs)} job posting(s) currently available · Candidate portal and company workspace are separate.")

elif view == "candidate_auth":
    st.markdown("## Candidate account")
    st.caption("This first prototype stores candidate accounts for the current browser session only.")
    login, signup = st.tabs(["Login", "Create account"])
    with login:
        with st.form("candidate_login"):
            email = st.text_input("Email address", key="candidate_login_email")
            password = st.text_input("Password", type="password", key="candidate_login_password")
            submit = st.form_submit_button("Login", type="primary", use_container_width=True)
        if submit:
            account = st.session_state.get("candidate_accounts", {}).get(email.strip().lower())
            if account and account["password"] == password:
                st.session_state.candidate_logged_in = True
                st.session_state.candidate_name = account["name"]
                st.session_state.candidate_email = email.strip().lower()
                st.session_state.view = "candidate"; st.rerun()
            else:
                st.error("Account not found or password is incorrect. Create an account if you are new.")
    with signup:
        with st.form("candidate_signup"):
            name = st.text_input("Full name")
            email = st.text_input("Email address", key="candidate_signup_email")
            password = st.text_input("Create password", type="password", key="candidate_signup_password")
            confirm = st.text_input("Confirm password", type="password")
            submit = st.form_submit_button("Create candidate account", type="primary", use_container_width=True)
        if submit:
            if not name.strip() or not email.strip() or not password:
                st.error("Please fill in every field.")
            elif not re.match(r"^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", email.strip()):
                st.error("Enter a valid email address.")
            elif len(password) < 6:
                st.error("Password must contain at least 6 characters.")
            elif password != confirm:
                st.error("Passwords do not match.")
            else:
                accounts = st.session_state.setdefault("candidate_accounts", {})
                key = email.strip().lower()
                if key in accounts:
                    st.error("This email already has an account. Please log in.")
                else:
                    accounts[key] = {"name": name.strip(), "password": password}
                    st.session_state.candidate_logged_in = True
                    st.session_state.candidate_name = name.strip()
                    st.session_state.candidate_email = key
                    st.session_state.view = "candidate"; st.rerun()
    if st.button("← Back to home"):
        st.session_state.view = "home"; st.rerun()

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
