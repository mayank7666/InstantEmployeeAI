from pathlib import Path
import html
import re
import sys
import pandas as pd
import streamlit as st
from pypdf import PdfReader

st.set_page_config(page_title="Instant Employee | AI Talent Platform", page_icon="✦", layout="wide")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DATA = ROOT / "data"
JOBS_FILE = DATA / "jobs.csv"

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
            accept_new_options=True,
            placeholder="Select or type a category",
            key="home_category_select",
        )
    with mode_col:
        modes = sorted({str(x).strip() for x in jobs[work_mode_col].tolist() if str(x).strip()}) if work_mode_col and not jobs.empty else []
        selected_mode = st.selectbox("Work mode", ["All modes"] + modes)

    filtered_jobs = jobs.copy()
    if search_text.strip() and not filtered_jobs.empty:
        searchable_cols = [c for c in [title_col, desc_col, skills_col, dept_col_name] if c]
        if searchable_cols:
            mask = filtered_jobs[searchable_cols].astype(str).apply(lambda row: row.str.contains(search_text.strip(), case=False, regex=False).any(), axis=1)
            filtered_jobs = filtered_jobs[mask]
    if selected_department and selected_department != "All categories" and dept_col_name:
        filtered_jobs = filtered_jobs[
            filtered_jobs[dept_col_name].astype(str).str.contains(
                str(selected_department).strip(), case=False, na=False, regex=False
            )
        ]
    if selected_mode != "All modes" and work_mode_col:
        filtered_jobs = filtered_jobs[filtered_jobs[work_mode_col].astype(str) == selected_mode]

    count_a, count_b = st.columns([3, 1])
    with count_a:
        st.markdown("### Latest opportunities")
        st.caption("Open a job to read the full description and apply.")
    with count_b:
        st.metric("Available jobs", len(filtered_jobs))

    if filtered_jobs.empty:
        st.info("No jobs match these filters yet. Try another keyword or category, or check back after new jobs are posted.")
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
            if st.button("View job details  →", key=f"view_job_{row_index}", type="primary", use_container_width=False):
                st.session_state.selected_job_index = row_index
                st.session_state.view = "job_details"
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
            if st.session_state.get("candidate_logged_in"):
                st.session_state.view = "candidate"
            else:
                st.session_state.view = "candidate_auth"
            st.rerun()

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
            elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email.strip()):
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
