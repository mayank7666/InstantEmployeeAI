from pathlib import Path
import html
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Instant Employee | AI Talent Platform", page_icon="✦", layout="wide")
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
JOBS_FILE = DATA / "jobs.csv"
SHORTLIST_FILE = DATA / "shortlist.csv"

def read_csv(path):
    try:
        return pd.read_csv(path).fillna("") if path.exists() else pd.DataFrame()
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
        return pd.DataFrame()

def col(df, names):
    for name in df.columns:
        if str(name).strip().lower() in names:
            return name
    return None

def safe(value):
    return html.escape(str(value or "Not specified").strip())

jobs = read_csv(JOBS_FILE)
shortlist = read_csv(SHORTLIST_FILE)
title_col = col(jobs, {"job title", "title", "job_title"})
status_col = col(jobs, {"status", "job status", "job_status"})
skills_col = col(jobs, {"required skills", "required_skills", "skills"})
department_col = col(jobs, {"department"})
description_col = col(jobs, {"description", "job description", "job_description"})
mode_col = col(jobs, {"work mode", "work_mode"})
min_col = col(jobs, {"minimum budget", "min budget", "minimum_budget"})
max_col = col(jobs, {"maximum budget", "max budget", "maximum_budget"})
active_jobs = int(jobs[status_col].astype(str).str.lower().isin(["active", "open", "published"]).sum()) if status_col and not jobs.empty else len(jobs)
shortlisted = shortlist["Candidate Name"].astype(str).str.strip().replace("", pd.NA).dropna().str.casefold().nunique() if "Candidate Name" in shortlist.columns else 0

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root{--blue:#2454f5;--ink:#101828;--muted:#62718a;--line:#e5eaf2}
html,body,[class*="css"]{font-family:Inter,system-ui,sans-serif}
.stApp{background:#f6f8fc;color:#101828}
.main .block-container{max-width:1450px;padding-top:1rem;padding-bottom:2rem}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#101b2d,#16263e)}
[data-testid="stSidebar"] *{color:#f7f9ff}
[data-testid="stSidebarNav"]{display:none}
.hero{padding:32px 34px;border-radius:22px;border:1px solid #dfe7fb;background:linear-gradient(115deg,#f7f9ff,#eaf0ff);margin-bottom:22px}
.kicker{font-size:12px;letter-spacing:1.7px;text-transform:uppercase;font-weight:800;color:#2855e8}
.hero h1{font-size:clamp(32px,4vw,48px);line-height:1.08;letter-spacing:-1.8px;margin:12px 0;color:#101828}
.hero h1 span{color:#2454f5}.hero p{font-size:15px;line-height:1.7;color:#52637e;max-width:700px}
.hero-art{background:radial-gradient(circle at 70% 20%,#d6e1ff,transparent 40%),linear-gradient(145deg,#dce7ff,#f5f7ff);border:1px solid #dce5fa;border-radius:20px;text-align:center;padding:30px 12px;font-size:68px}
div[data-testid="stMetric"]{background:white;border:1px solid var(--line);border-radius:14px;padding:17px;box-shadow:0 4px 15px #263e7008}
div[data-testid="stMetric"] label{color:#62718a!important}div[data-testid="stMetricValue"]{color:#101828;font-weight:800}
.panel{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:14px}
.jobcard{background:#fff;border:1px solid var(--line);border-radius:12px;padding:15px;margin:10px 0}
.jobcard h4{margin:0 0 6px;color:#152541}.jobcard p{margin:4px 0;color:#62718a;font-size:13px}
.pill{display:inline-block;background:#dcfce7;color:#166534;border-radius:20px;padding:3px 9px;font-size:11px;font-weight:700}
.stButton>button,.stPageLink a{border-radius:9px!important;font-weight:700!important}
.stButton>button[kind="primary"]{background:#2454f5!important;border-color:#2454f5!important}
@media(max-width:800px){.hero{padding:22px}.hero h1{letter-spacing:-1px}}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<div style='font-size:24px;font-weight:800;padding:10px 0'>✦ Instant Employee</div><div style='color:#9caec9;font-size:12px;margin-bottom:18px'>AI Talent Platform</div>", unsafe_allow_html=True)
    st.divider()
    st.page_link("app.py", label="⌂  Dashboard", use_container_width=True)
    st.page_link("pages/2_Job_Posting.py", label="＋  Post a Job", use_container_width=True)
    st.page_link("pages/3_Match_Candidates.py", label="⌕  Find Talent", use_container_width=True)
    st.divider()
    st.caption("Company workspace")

left, right = st.columns([1.4, .75], gap="large", vertical_alignment="center")
with left:
    st.markdown("""
    <div class="hero"><div class="kicker">AI-powered talent matching</div>
    <h1>Hire Vetted Virtual IT &amp; Tech Employees <span>with AI</span></h1>
    <p>An extension of your team, not just a freelance marketplace. Find the right talent faster with AI-powered matching.</p>
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:18px"><span class="pill">Skills-first matching</span><span class="pill">Remote-ready talent</span><span class="pill">Company workspace</span></div></div>
    """, unsafe_allow_html=True)
    a,b = st.columns(2)
    with a: st.page_link("pages/2_Job_Posting.py", label="＋  I'm a Company · Post a Job", use_container_width=True)
    with b: st.page_link("pages/3_Match_Candidates.py", label="⌕  Find Talent with AI", use_container_width=True)
with right:
    st.markdown("<div class='hero-art'>👩🏻‍💻<div style='font-size:15px;font-weight:800;color:#152541;margin-top:8px'>AI Matched Candidates</div><div style='font-size:12px;color:#62718a;margin-top:4px'>Skills · Experience · Role fit</div></div>", unsafe_allow_html=True)

st.markdown("### Company Dashboard")
st.caption("Manage job postings and review recruitment activity from one place.")
m1,m2,m3,m4 = st.columns(4)
m1.metric("Active Jobs", active_jobs)
m2.metric("Shortlisted Talents", int(shortlisted))
m3.metric("Job Postings", len(jobs))
m4.metric("AI Matching", "Ready to test" if len(jobs) else "Add a job first")

main, side = st.columns([1.5,.85], gap="large")
with main:
    st.markdown("<div class='panel'><h3 style='margin:0'>Recent Jobs</h3><p style='color:#62718a;margin:4px 0 12px'>Latest jobs saved in your project data</p></div>", unsafe_allow_html=True)
    if jobs.empty or not title_col:
        st.info("No jobs found yet. Use Post a Job to create your first vacancy.")
    else:
        for _, row in jobs.tail(5).iloc[::-1].iterrows():
            title = safe(row.get(title_col, "Untitled position"))
            dept = safe(row.get(department_col, "Not specified")) if department_col else "Not specified"
            skills = safe(row.get(skills_col, "Not specified")) if skills_col else "Not specified"
            desc = safe(row.get(description_col, "Description not available")) if description_col else "Description not available"
            mode = safe(row.get(mode_col, "Not specified")) if mode_col else "Not specified"
            status = safe(row.get(status_col, "Active")) if status_col else "Active"
            budget = "Not specified"
            if min_col or max_col:
                low = safe(row.get(min_col, "Not specified")) if min_col else "Not specified"
                high = safe(row.get(max_col, "Not specified")) if max_col else "Not specified"
                budget = f"₹{low} – ₹{high}"
            st.markdown(f"<div class='jobcard'><h4>{title} <span class='pill'>{status}</span></h4><p><b>Department:</b> {dept} &nbsp;·&nbsp; <b>Work mode:</b> {mode}</p><p><b>Skills:</b> {skills}</p><p><b>Monthly budget:</b> {budget}</p><p>{desc}</p></div>", unsafe_allow_html=True)
with side:
    st.markdown("<div class='panel'><h3 style='margin-top:0'>✦ AI Matching Insights</h3><p style='color:#62718a;line-height:1.7'>Compare resumes against job requirements and review candidate match results.</p></div>", unsafe_allow_html=True)
    st.page_link("pages/3_Match_Candidates.py", label="View Candidate Matches →", use_container_width=True)
    st.markdown("<div class='panel'><h3 style='margin-top:0'>Quick Actions</h3><p style='color:#62718a'>Create a role, then find candidates whose skills align with your requirements.</p></div>", unsafe_allow_html=True)
    st.page_link("pages/2_Job_Posting.py", label="＋ Create a Job", use_container_width=True)
    if not shortlist.empty and "Candidate Name" in shortlist.columns:
        st.subheader("Recent Shortlists")
        for _, item in shortlist.tail(5).iloc[::-1].iterrows():
            st.write("**" + str(item.get("Candidate Name", "Candidate")) + "**")
            if "Match Score" in shortlist.columns: st.caption("Match score: " + str(item.get("Match Score", "N/A")) + "%")

st.divider()
st.caption("Instant Employee · AI-powered talent platform · Company dashboard")
