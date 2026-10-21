from pathlib import Path
import base64
import html
import os
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
API_BASE_URL = os.getenv("INSTANT_EMPLOYEE_API_BASE_URL", "https://instant-employee-api.onrender.com").rstrip("/")


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
/* Modern split-panel login and admin setup layout */
.auth-heading{display:flex;align-items:center;gap:15px;padding:8px 0 18px}
.auth-heading h3{margin:0 0 5px;font-size:22px;color:#14294b}
.auth-heading p{margin:0;color:#64748b;font-size:14px}
.auth-icon{width:58px;height:58px;display:flex;align-items:center;justify-content:center;border-radius:17px;background:#e0edff;color:#1765d1;font-size:28px;font-weight:800;flex-shrink:0}
.auth-icon-purple{background:#eee8ff;color:#7047d7}
.auth-feature{height:100%;min-height:440px;padding:30px;border:1px solid #d5e5fb;border-radius:22px;background:radial-gradient(circle at 90% 8%,#d6eaff 0,transparent 34%),linear-gradient(145deg,#e4f0ff,#f7faff 75%);box-shadow:0 10px 30px #244a800b}
.auth-feature h2{font-size:30px;letter-spacing:-.7px;margin:12px 0;color:#132c56}
.auth-feature>p{font-size:15px;line-height:1.65;color:#607492;margin-bottom:28px}
.auth-feature .kicker{font-size:11px;letter-spacing:1.3px;color:#2863c7;font-weight:800}
.feature-row{display:flex;align-items:center;gap:14px;margin:21px 0}
.feature-icon{display:flex;width:48px;height:48px;align-items:center;justify-content:center;border-radius:14px;font-size:22px;font-weight:800;flex-shrink:0}
.icon-blue{background:#dceaff;color:#2863d9}
.icon-green{background:#d8f7eb;color:#0d9a70}
.icon-amber{background:#fff0d2;color:#c47b05}
.feature-row b{display:block;color:#1c3155;font-size:15px;margin-bottom:4px}
.feature-row small{display:block;color:#647792;font-size:13px;line-height:1.45}
.feature-foot{border-top:1px solid #d2e2f7;margin-top:28px;padding-top:18px;color:#456caa;font-size:13px;font-weight:600}
.auth-note{margin-top:12px;padding:14px 16px;background:#e2efff;border:1px solid #d3e5ff;border-radius:12px;color:#456387;font-size:13px;line-height:1.55}
.auth-security{display:flex;align-items:center;gap:14px;margin-top:20px;padding:16px 20px;border:1px solid #f4d6dd;border-radius:16px;background:linear-gradient(100deg,#fff0f2,#fff7f8)}
.security-shield{display:flex;align-items:center;justify-content:center;width:42px;height:42px;border-radius:13px;background:#ffe0e5;color:#be3449;font-size:23px;flex-shrink:0}
.auth-security b{display:block;color:#9f2538;font-size:14px;margin-bottom:4px}
.auth-security small{display:block;color:#7a5660;font-size:13px;line-height:1.5}
.security-note{margin-top:30px;padding:14px;background:#ffffffa8;border:1px solid #d9e6f5;border-radius:12px;color:#536b89;font-size:13px;line-height:1.6}
[data-testid="stForm"]{background:linear-gradient(145deg,#ffffff,#f9fbff)!important;border:1px solid #e0e9f6!important;border-radius:20px!important;padding:22px!important;box-shadow:0 12px 32px #25466d0c!important}
[data-testid="stForm"] button[kind="primary"]{background:linear-gradient(100deg,#3395ff,#0875ed)!important;border-color:#1682f6!important;color:#fff!important}
[data-testid="stForm"] button[kind="primary"] *{color:#fff!important;-webkit-text-fill-color:#fff!important}
[data-testid="stForm"] button[kind="primary"]:hover{background:linear-gradient(100deg,#2584f1,#0564d2)!important}
/* Soft light-blue login and admin setup buttons */
[data-testid="stForm"] button[kind="primary"]{
    background:linear-gradient(100deg,#e5efff,#d8e7ff)!important;
    border-color:#c6d9fb!important;
    color:#2456a6!important;
    box-shadow:0 3px 9px #2456a610!important;
}
[data-testid="stForm"] button[kind="primary"] *{
    color:#2456a6!important;-webkit-text-fill-color:#2456a6!important;
}
[data-testid="stForm"] button[kind="primary"]:hover{
    background:linear-gradient(100deg,#d6e6ff,#c9ddff)!important;
    border-color:#aec9f7!important;
}
/* Streamlit form-submit buttons may not use kind="primary"; target them directly */
[data-testid="stFormSubmitButton"] button,
button[data-testid="stFormSubmitButton"],
[data-testid="stForm"] button[type="submit"]{
    background:linear-gradient(100deg,#e5efff,#d8e7ff)!important;
    background-color:#d8e7ff!important;
    border:1px solid #c6d9fb!important;
    color:#2456a6!important;
    -webkit-text-fill-color:#2456a6!important;
    border-radius:11px!important;
    font-weight:700!important;
    box-shadow:0 3px 9px #2456a610!important;
}
[data-testid="stFormSubmitButton"] button *,
button[data-testid="stFormSubmitButton"] *,
[data-testid="stForm"] button[type="submit"] *{
    color:#2456a6!important;-webkit-text-fill-color:#2456a6!important;
}
[data-testid="stFormSubmitButton"] button:hover,
button[data-testid="stFormSubmitButton"]:hover,
[data-testid="stForm"] button[type="submit"]:hover{
    background:#cfe1ff!important;background-color:#cfe1ff!important;
    border-color:#aec9f7!important;
}
@media(max-width:900px){.auth-feature{min-height:0;padding:22px}.auth-feature h2{font-size:25px}.auth-heading h3{font-size:19px}}

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

/* Shared responsive layout: mobile phones, tablets and desktop */
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    max-width: 100%;
}
[data-testid="stMainBlockContainer"] {
    width: 100% !important;
    max-width: 1440px !important;
    padding-left: clamp(12px, 3vw, 40px) !important;
    padding-right: clamp(12px, 3vw, 40px) !important;
}
[data-testid="stHorizontalBlock"] {
    flex-wrap: wrap !important;
    align-items: stretch;
    gap: clamp(10px, 1.5vw, 22px) !important;
}
[data-testid="stHorizontalBlock"] > [data-testid="column"] {
    min-width: 0 !important;
}
[data-testid="stTable"], [data-testid="stDataFrame"], [data-testid="stDataEditor"],
[data-testid="stTable"] > div, [data-testid="stDataFrame"] > div {
    max-width: 100% !important;
}
[data-testid="stForm"], [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stMetric"], .job-hero, .matching-hero, .candidate-auth-feature {
    min-width: 0;
    overflow-wrap: anywhere;
}
img, svg, video, iframe {
    max-width: 100%;
}
@media (max-width: 900px) {
    [data-testid="stMainBlockContainer"] {
        padding-left: 18px !important;
        padding-right: 18px !important;
    }
    [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        flex: 1 1 280px !important;
        width: auto !important;
    }
    h1 { font-size: clamp(1.65rem, 5vw, 2.3rem) !important; }
    h2 { font-size: clamp(1.3rem, 4vw, 1.8rem) !important; }
}
@media (max-width: 600px) {
    [data-testid="stMainBlockContainer"] {
        padding: 12px 12px 28px !important;
    }
    [data-testid="stHorizontalBlock"] {
        flex-direction: column !important;
        gap: 12px !important;
    }
    [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        flex: 1 1 100% !important;
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
    }
    [data-testid="stForm"] {
        padding: 16px !important;
        border-radius: 15px !important;
    }
    [data-testid="stForm"] input, [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input, [data-testid="stSelectbox"] {
        max-width: 100% !important;
    }
    [data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button {
        width: 100% !important;
        white-space: normal !important;
        min-height: 42px !important;
    }
    [data-testid="stTable"], [data-testid="stDataFrame"], [data-testid="stDataEditor"] {
        overflow-x: auto !important;
    }
    .job-hero, .matching-hero, .candidate-auth-feature {
        padding: 18px !important;
        border-radius: 16px !important;
    }
    .candidate-auth-hero { padding: 20px !important; }
    .candidate-auth-feature { min-height: 0 !important; }
    [data-testid="stMetric"] { padding: 12px !important; }
}

/* Blueprint alignment: company dashboard cards, metrics and actions */
.company-blueprint-kicker{font-size:11px;letter-spacing:1.7px;text-transform:uppercase;font-weight:850;color:#2855e8}
[data-testid="stMetric"]{background:#fff!important;border:1px solid #dce6f5!important;border-radius:16px!important;padding:18px 20px!important;box-shadow:0 5px 18px #203d7008!important;min-height:112px}
[data-testid="stMetricLabel"]{color:#61728d!important;font-size:13px!important;font-weight:650!important}
[data-testid="stMetricValue"]{color:#18365f!important;font-size:34px!important;font-weight:850!important;letter-spacing:-1px!important}
.jobcard{background:#fff;border:1px solid #dce6f5;border-radius:16px;padding:20px 22px;margin:10px 0 8px;box-shadow:0 5px 18px #203d7008}
.jobcard h4{color:#172e55!important;font-size:19px!important;margin:0 0 9px!important}
.jobcard p{font-size:13px;color:#526987!important;margin:5px 0}
.pill{display:inline-block;border:1px solid #b8efd4;border-radius:30px;padding:4px 10px;background:#dff9eb;color:#087b50;font-size:11px;font-weight:800;margin-left:5px}
[data-testid="stExpander"]{border:1px solid #dce6f5!important;border-radius:12px!important;background:#fff!important}
[data-testid="stButton"] button,[data-testid="stPageLink"] a{border-radius:11px!important}
[data-testid="stPageLink"] a{border:1px solid #dce6f5!important;background:#f8faff!important}

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
    st.markdown(
        "<div class='hero'><div class='kicker'>INSTANT EMPLOYEE · RECRUITER WORKSPACE</div>"
        "<h1>Welcome to <span>Instant Employee</span></h1>"
        "<p>Sign in to manage jobs, review applications and discover the right talent with AI-powered matching.</p></div>",
        unsafe_allow_html=True,
    )
    register_first = st.query_params.get("auth") == "register"
    tab_labels = ["⚙️  Initial Admin Setup", "🏢  Company / Employee Login"] if register_first else ["🏢  Company / Employee Login", "⚙️  Initial Admin Setup"]
    first_tab, second_tab = st.tabs(tab_labels)
    if register_first:
        setup_tab, login_tab = first_tab, second_tab
    else:
        login_tab, setup_tab = first_tab, second_tab
    with login_tab:
        form_col, feature_col = st.columns([1.05, 0.95], gap="large")
        with form_col:
            st.markdown(
                "<div class='auth-heading'><div class='auth-icon'>▣</div><div><h3>Company / Employee Login</h3>"
                "<p>Access your recruitment dashboard</p></div></div>",
                unsafe_allow_html=True,
            )
            with st.form("company_login_form"):
                email = st.text_input("Company email", placeholder="Enter your company email")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                submitted = st.form_submit_button("→  Login to Dashboard", type="primary", use_container_width=True)
            st.markdown(
                "<div class='auth-note'>ⓘ  Company login gives access to job posting, candidate matching and team management.</div>",
                unsafe_allow_html=True,
            )
        with feature_col:
            st.markdown(
                "<div class='auth-feature'><div class='kicker'>YOUR TEAM, ONE WORKSPACE</div>"
                "<h2>Hire better, faster.</h2><p>Everything you need to move from job opening to the right candidate.</p>"
                "<div class='feature-row'><span class='feature-icon icon-blue'>♧</span><div><b>Post Jobs</b><small>Create and manage job openings easily.</small></div></div>"
                "<div class='feature-row'><span class='feature-icon icon-green'>♙</span><div><b>Find Talent</b><small>AI-powered candidate matching.</small></div></div>"
                "<div class='feature-row'><span class='feature-icon icon-amber'>▥</span><div><b>Track Applications</b><small>Review, shortlist and manage candidates.</small></div></div>"
                "<div class='feature-foot'>✦  Simple tools for smarter recruitment</div></div>",
                unsafe_allow_html=True,
            )
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
        setup_col, guide_col = st.columns([1.05, 0.95], gap="large")
        with setup_col:
            st.markdown(
                "<div class='auth-heading'><div class='auth-icon auth-icon-purple'>⚙</div><div><h3>Initial Admin Setup</h3>"
                "<p>Create the first company administrator</p></div></div>",
                unsafe_allow_html=True,
            )
            st.info("This is only for the first company admin. ADMIN_SETUP_KEY must be configured privately on the Render API. Employees can be created later from the dashboard.")
            with st.form("company_bootstrap_form"):
                company_name = st.text_input("Company / admin name", placeholder="Enter your name", key="bootstrap_company_name")
                admin_email = st.text_input("Admin email", placeholder="admin@company.com", key="bootstrap_admin_email")
                admin_password = st.text_input("Admin password (minimum 8 characters)", type="password", placeholder="Create a strong password", key="bootstrap_admin_password")
                confirm_password = st.text_input("Confirm admin password", type="password", placeholder="Re-enter your password", key="bootstrap_confirm_password")
                setup_key = st.text_input("Private setup key", type="password", placeholder="Enter the private setup key", key="bootstrap_setup_key", help="Must match ADMIN_SETUP_KEY configured privately in Render.")
                submitted = st.form_submit_button("✦  Set Up First Admin", type="primary", use_container_width=True)
        with guide_col:
            st.markdown(
                "<div class='auth-feature setup-feature'><div class='kicker'>SECURE COMPANY SETUP</div>"
                "<h2>Get your workspace ready.</h2><p>Set up your admin account to unlock company recruitment tools.</p>"
                "<div class='feature-row'><span class='feature-icon icon-blue'>1</span><div><b>Company details</b><small>Enter the admin name and work email.</small></div></div>"
                "<div class='feature-row'><span class='feature-icon icon-green'>2</span><div><b>Secure password</b><small>Use at least 8 characters and confirm it.</small></div></div>"
                "<div class='feature-row'><span class='feature-icon icon-amber'>3</span><div><b>Private setup key</b><small>Use the key configured by the API administrator.</small></div></div>"
                "<div class='security-note'>♢  Keep your setup key private. It is not saved in the repository.</div></div>",
                unsafe_allow_html=True,
            )
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
    st.markdown(
        "<div class='auth-security'><span class='security-shield'>♢</span><div><b>Protected company access</b>"
        "<small>Public sign-up is available only for candidate accounts. Company admin sign-up requires a private setup key.</small></div></div>",
        unsafe_allow_html=True,
    )
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

st.markdown(f"<div class='hero'><div class='kicker'>✦ COMPANY WORKSPACE · SIGNED IN AS {safe(me.get('email')).upper()}</div><h1>Your hiring <span>overview</span></h1><p>Manage your own vacancies, monitor candidate applications, and move from job posting to shortlist in one workspace.</p><div style='display:flex;gap:9px;flex-wrap:wrap;margin-top:16px'><span style='padding:7px 11px;border:1px solid #d4e2fa;border-radius:30px;background:#ffffffb8;color:#31527e;font-size:12px;font-weight:700'>✓ Secure company workspace</span><span style='padding:7px 11px;border:1px solid #d4e2fa;border-radius:30px;background:#ffffffb8;color:#31527e;font-size:12px;font-weight:700'>✦ AI-assisted matching</span></div></div>", unsafe_allow_html=True)

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
        selected_job_id = st.session_state.get("dashboard_selected_job")
        if selected_job_id is None:
            try:
                selected_job_id = int(st.query_params.get("selected_job", ""))
                st.session_state["dashboard_selected_job"] = selected_job_id
            except (TypeError, ValueError):
                selected_job_id = None
        for job in jobs[:8]:
            job_id = int(job.get("id"))
            status = "Active" if job.get("is_active") else "Closed"
            st.markdown(f"<div class='jobcard'><h4>{safe(job.get('title'))} <span class='pill'>{status}</span></h4><p><b>Department:</b> {safe(job.get('department'))} · <b>Applications:</b> {int(job.get('applications_count', 0))}</p></div>", unsafe_allow_html=True)
            action_col, status_col = st.columns(2)
            with action_col:
                if st.button("View applications", key=f"view_apps_{job_id}", use_container_width=True):
                    st.session_state["dashboard_selected_job"] = job_id
                    st.query_params["selected_job"] = str(job_id)
                    st.rerun()
            with status_col:
                action_label = "Close job" if job.get("is_active") else "Reopen job"
                if st.button(action_label, key=f"toggle_job_{job_id}", use_container_width=True):
                    _, status_error = api_request(
                        "PATCH",
                        f"/jobs/{job_id}/status",
                        token=token,
                        params={"is_active": not bool(job.get("is_active"))},
                    )
                    if status_error:
                        st.error("Job status could not be updated: " + status_error)
                    else:
                        st.success("Job status updated.")
                        st.rerun()


            if selected_job_id == job_id:
                with st.expander("⌃ Hide applications", expanded=True):
                    st.divider()
                    st.subheader("Applications for selected job")
                    selected_apps = [row for row in applications if row.get("job_id") == selected_job_id]
                    if not selected_apps:
                        st.info("There are no applications for this job yet.")
                    else:
                        applications_table = pd.DataFrame([{
                            "Application ID": row.get("id"),
                            "Candidate": row.get("candidate_name") or "Name not provided",
                            "Email": row.get("candidate_email", ""),
                            "Applied On": str(row.get("applied_at", ""))[:19].replace("T", " "),
                            "Resume File": row.get("resume_filename", ""),
                            "Status": row.get("status", "Applied"),
                        } for row in selected_apps])
                        st.dataframe(applications_table, use_container_width=True, hide_index=True)
                        st.download_button(
                            "Download Applications CSV",
                            data=applications_table.to_csv(index=False).encode("utf-8-sig"),
                            file_name=f"job_{selected_job_id}_applications.csv",
                            mime="text/csv",
                            key=f"download_applications_{selected_job_id}",
                            use_container_width=True,
                        )

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
                                application_status = str(row.get("status") or "Applied")
                                if row.get("resume_filename") and st.button("Load resume", key=f"load_resume_{row.get('id')}", use_container_width=True):
                                    resume_payload, resume_error = api_request(
                                        "GET", f"/applications/{row.get('id')}/resume", token=token
                                    )
                                    if resume_error:
                                        st.error("Resume unavailable: " + resume_error)
                                    else:
                                        st.session_state[f"resume_download_{row.get('id')}"] = resume_payload
                                if application_status != "Shortlisted" and application_status not in {"Rejected", "Selected"}:
                                    if st.button("✓ Shortlist", key=f"quick_shortlist_{row.get('id')}", use_container_width=True):
                                        _, shortlist_error = api_request(
                                            "PATCH",
                                            f"/applications/{row.get('id')}/status",
                                            token=token,
                                            params={"new_status": "Shortlisted"},
                                        )
                                        if shortlist_error:
                                            st.error("Candidate could not be shortlisted: " + shortlist_error)
                                        else:
                                            st.success(f"{candidate_label} shortlisted.")
                                            st.rerun()
                            with st.expander(f"Messages · {candidate_label}", expanded=False):
                                conversation_id = int(row.get("id"))
                                message_payload, message_error = api_request(
                                    "GET", f"/applications/{conversation_id}/messages", token=token
                                )
                                if message_error:
                                    st.error("Messages could not be loaded: " + message_error)
                                else:
                                    conversation_messages = message_payload.get("messages", [])
                                    if not conversation_messages:
                                        st.caption("No messages yet. Start the conversation about the application or interview.")
                                    for message in conversation_messages:
                                        who = "You" if message.get("is_mine") else candidate_label
                                        st.markdown(f"**{safe(who)}** · {safe(str(message.get('created_at') or '')[:16].replace('T', ' '))}")
                                        st.write(str(message.get("body", "")))
                                    with st.form(f"send_message_{conversation_id}"):
                                        message_body = st.text_area("Write a message", key=f"message_body_{conversation_id}", max_chars=5000)
                                        send_message = st.form_submit_button("Send message", type="primary")
                                    if send_message:
                                        if not message_body.strip():
                                            st.warning("Write a message before sending.")
                                        else:
                                            _, send_error = api_request(
                                                "POST", f"/applications/{conversation_id}/messages",
                                                token=token, json={"body": message_body}
                                            )
                                            if send_error:
                                                st.error("Message could not be sent: " + send_error)
                                            else:
                                                st.success("Message sent.")
                                                st.rerun()

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

                with st.expander(f"Edit details · {job.get('title', 'Job')}"):
                    with st.form(f"edit_job_form_{job_id}"):
                        edit_title = st.text_input("Job title", value=str(job.get("title") or ""), key=f"edit_title_{job_id}")
                        edit_department = st.text_input("Department", value=str(job.get("department") or "Other"), key=f"edit_department_{job_id}")
                        edit_description = st.text_area("Job description", value=str(job.get("description") or ""), key=f"edit_description_{job_id}")
                        edit_skills = st.text_input("Required skills", value=str(job.get("required_skills") or ""), key=f"edit_skills_{job_id}")
                        edit_min_budget = st.number_input("Minimum budget (INR)", min_value=0, value=max(0, int(job.get("min_budget") or 0)), step=1000, key=f"edit_min_{job_id}")
                        edit_max_budget = st.number_input("Maximum budget (INR)", min_value=0, value=max(0, int(job.get("max_budget") or 0)), step=1000, key=f"edit_max_{job_id}")
                        edit_work_mode = st.selectbox("Work mode", ["Remote", "Hybrid", "On-site"], index=["Remote", "Hybrid", "On-site"].index(job.get("work_mode")) if job.get("work_mode") in ["Remote", "Hybrid", "On-site"] else 0, key=f"edit_mode_{job_id}")
                        edit_timezone = st.text_input("Timezone", value=str(job.get("timezone") or "Asia/Kolkata"), key=f"edit_timezone_{job_id}")
                        save_job_changes = st.form_submit_button("Save job changes", type="primary", use_container_width=True)
                    if save_job_changes:
                        if len(edit_title.strip()) < 2 or len(edit_description.strip()) < 10:
                            st.error("Enter a job title and a description of at least 10 characters.")
                        elif edit_max_budget and edit_min_budget > edit_max_budget:
                            st.error("Minimum budget cannot exceed maximum budget.")
                        else:
                            update_payload = {
                                "title": edit_title.strip(),
                                "department": edit_department.strip() or "Other",
                                "description": edit_description.strip(),
                                "required_skills": edit_skills.strip(),
                                "min_budget": int(edit_min_budget),
                                "max_budget": int(edit_max_budget),
                                "work_mode": edit_work_mode,
                                "timezone": edit_timezone.strip() or "Asia/Kolkata",
                            }
                            _, edit_error = api_request("PUT", f"/jobs/{job_id}", token=token, json=update_payload)
                            if edit_error:
                                st.error("Job could not be updated: " + edit_error)
                            else:
                                st.success("Job details updated successfully.")
                                st.rerun()



with right:
    st.subheader("Quick Actions")
    st.page_link("pages/2_Job_Posting.py", label="＋  Post a Job", use_container_width=True)
    st.page_link("pages/3_Match_Candidates.py", label="⌕  AI Candidate Matching", use_container_width=True)
    st.markdown("<div class='panel'><h4>Application privacy</h4><p>Only database applications for jobs belonging to your account are shown here. Applications from other companies are not exposed.</p></div>", unsafe_allow_html=True)

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
