from pathlib import Path
import os
import html
import re
import sys
import time
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
API_BASE_URL = os.getenv("INSTANT_EMPLOYEE_API_BASE_URL", "https://instant-employee-api.onrender.com").rstrip("/")


def api_request(method, path, *, token=None, **kwargs):
    """Call the deployed FastAPI backend, retry transient gateway errors, and return (data, error)."""
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Free hosting can briefly return a gateway error while the API wakes up.
    response = None
    for attempt in range(3):
        try:
            response = requests.request(
                method,
                f"{API_BASE_URL}{path}",
                headers=headers,
                timeout=(10, 60),
                **kwargs,
            )
            if response.status_code not in (502, 503, 504) or attempt == 2:
                break
        except requests.RequestException:
            if attempt == 2:
                return None, (
                    "The backend is not responding yet. The service may need time to wake up. "
                    "Please wait 30 seconds and try again."
                )
        time.sleep(2 * (attempt + 1))

    try:
        payload = response.json()
    except (ValueError, AttributeError):
        payload = {}

    if response is None:
        return None, "Backend temporarily unavailable. Please try again."

    if not response.ok:
        detail = payload.get("detail") if isinstance(payload, dict) else None
        if response.status_code in (502, 503, 504):
            return None, (
                f"The backend service is currently unavailable (HTTP {response.status_code}). "
                "The Render API may be restarting or deploying. "
                "Please try again in a little while."
            )
        return None, str(detail or f"API request failed (HTTP {response.status_code})")

    return payload, None


def get_candidate_applications(token):
    """Combine database-job applications and legacy CSV-job applications for the candidate."""
    database_rows, database_error = api_request("GET", "/applications/me", token=token)
    external_rows, external_error = api_request("GET", "/applications/external/me", token=token)
    combined = []
    if isinstance(database_rows, list):
        combined.extend(database_rows)
    if isinstance(external_rows, list):
        combined.extend(external_rows)
    combined.sort(key=lambda row: str(row.get("applied_at", "")), reverse=True)
    errors = [error for error in (database_error, external_error) if error]
    return combined, "; ".join(errors) if errors else None


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

# Load the saved candidate photo for the header avatar when logged in.
header_profile_picture = (st.session_state.get("candidate_profile_picture") or "").strip()
_header_token = st.session_state.get("candidate_api_token")
if _header_token:
    try:
        _header_profile, _header_profile_error = api_request(
            "GET", "/profiles/me", token=_header_token
        )
        if not _header_profile_error and isinstance(_header_profile, dict):
            # Support the direct profile response and common wrapped response shapes.
            _header_profile_data = _header_profile.get("profile") or _header_profile.get("data") or _header_profile
            if isinstance(_header_profile_data, dict):
                header_profile_picture = (
                    _header_profile_data.get("picture_data")
                    or _header_profile_data.get("profile_picture")
                    or _header_profile_data.get("photo_data")
                    or header_profile_picture
                    or ""
                ).strip()
                if header_profile_picture:
                    st.session_state.candidate_profile_picture = header_profile_picture
    except Exception:
        header_profile_picture = ""

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
:root{--bg:#f5f8ff;--surface:#ffffff;--surface2:#edf3ff;--line:#dce5f2;--ink:#17233b;--muted:#52637e;--blue:#1764ff;--cyan:#087fc5}
html,body,[class*="css"]{font-family:Inter,system-ui,sans-serif}
.stApp{background:linear-gradient(135deg,#f8faff,#edf4ff);color:var(--ink)}
[data-testid="stAppViewContainer"],[data-testid="stHeader"]{background:transparent}
.main .block-container{max-width:1240px;padding-top:1rem;padding-bottom:3rem}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#ffffff,#edf3ff);border-right:1px solid var(--line)}
[data-testid="stSidebar"] *{color:var(--ink)!important}
/* Cleaner candidate/company navigation in the sidebar */
[data-testid="stSidebar"] [data-testid="stButton"]{margin:5px 0}
[data-testid="stSidebar"] [data-testid="stButton"] button{
    background:linear-gradient(135deg,#ffffff,#f5f8ff)!important;
    border:1px solid #d7e2f4!important;
    border-radius:12px!important;
    color:#243653!important;
    font-weight:600!important;
    min-height:46px!important;
    box-shadow:0 2px 6px #203d7008!important;
    transition:background .15s ease,border-color .15s ease,transform .15s ease!important;
}
[data-testid="stSidebar"] [data-testid="stButton"] button:hover{
    background:#e8f0ff!important;
    border-color:#b9cefa!important;
    color:#174b9b!important;
    transform:translateY(-1px);
}
[data-testid="stSidebar"] [data-testid="stButton"] button:focus{
    box-shadow:0 0 0 2px #d8e6ff!important;
}
[data-testid="stSidebar"] hr{
    margin:22px 0!important;
    border-color:#dce5f2!important;
}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"]{
    color:#61728d!important;
    font-size:12px!important;
    font-weight:700!important;
    letter-spacing:.7px!important;
}

[data-testid="stSidebarNav"]{display:none}
.stMarkdown,.stText,[data-testid="stCaptionContainer"],label,p,li{color:var(--muted)}
h1,h2,h3,h4,h5,h6,[data-testid="stMarkdownContainer"] strong{color:var(--ink)!important}
.hero{padding:42px;border-radius:24px;border:1px solid #dce5f2;background:linear-gradient(115deg,#ffffff,#eaf1ff);margin:12px 0 24px;box-shadow:0 12px 35px #203d7010}
.kicker{font-size:12px;letter-spacing:1.6px;text-transform:uppercase;font-weight:800;color:#087fc5}
.hero h1{font-size:clamp(36px,5vw,58px);line-height:1.04;letter-spacing:-2px;margin:13px 0;color:#17233b}
.hero h1 span{color:#1764ff}
.hero p{font-size:16px;line-height:1.75;color:#52637e;max-width:690px}
.panel,.step,.jobcard{background:#fff;border:1px solid var(--line);border-radius:16px;padding:20px;margin:10px 0;box-shadow:0 5px 20px #203d7008}
.step{min-height:125px;background:#f2f6ff}
.stepnum{font-size:12px;color:#1764ff;font-weight:900;letter-spacing:1px}
.smallmuted{color:#52637e;font-size:13px}
/* Candidate login/signup split-panel design (CSS only; no generated screenshot used) */
.candidate-auth-hero{padding:30px 34px;margin:8px 0 16px;background:linear-gradient(115deg,#ffffff,#eaf2ff)}
.candidate-auth-hero h1{font-size:clamp(32px,4vw,46px);letter-spacing:-1.2px}
.candidate-auth-hero p{max-width:780px;margin-bottom:0}
[data-testid="stTabs"] [data-baseweb="tab-list"]{gap:8px;border-bottom:1px solid #dce6f5}
[data-testid="stTabs"] button[data-baseweb="tab"]{padding:10px 16px;color:#61728d;font-weight:650}
[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"]{color:#1764ff;border-bottom:2px solid #1764ff}
.candidate-auth-heading{display:flex;align-items:center;gap:15px;margin:4px 0 20px}
.candidate-auth-heading h3{margin:0 0 5px;color:#172e55;font-size:24px}
.candidate-auth-heading p{margin:0;color:#647792;font-size:14px;line-height:1.55}
.candidate-auth-icon{display:flex;align-items:center;justify-content:center;width:60px;height:60px;border-radius:17px;background:linear-gradient(140deg,#d6e5ff,#edf3ff);color:#1764ff;font-size:29px;font-weight:800;flex-shrink:0}
.candidate-signup-icon{background:linear-gradient(140deg,#e4ddff,#f3efff);color:#7047d7}
[data-testid="stForm"]{background:linear-gradient(145deg,#ffffff,#f9fbff)!important;border:1px solid #dce6f5!important;border-radius:20px!important;padding:22px!important;box-shadow:0 12px 32px #25466d0c!important}
[data-testid="stForm"] label{font-weight:600!important;color:#34445e!important}
[data-testid="stForm"] input{border-radius:11px!important;min-height:44px!important}
/* Stable form submit buttons: keep label and blue background visible in every state */
[data-testid="stForm"] button,
[data-testid="stFormSubmitButton"],
[data-testid="stFormSubmitButton"] button {
    background:#1764ff!important;
    background-color:#1764ff!important;
    background-image:none!important;
    border:1px solid #1764ff!important;
    border-radius:11px!important;
    color:#ffffff!important;
    -webkit-text-fill-color:#ffffff!important;
    font-weight:700!important;
    min-height:46px!important;
    box-shadow:0 5px 13px #1764ff22!important;
    opacity:1!important;
    visibility:visible!important;
    animation:none!important;
    transition:none!important;
    filter:none!important;
}
[data-testid="stForm"] button *,
[data-testid="stFormSubmitButton"] * {
    color:#ffffff!important;
    -webkit-text-fill-color:#ffffff!important;
    opacity:1!important;
    visibility:visible!important;
    animation:none!important;
    transition:none!important;
}
[data-testid="stForm"] button,
[data-testid="stFormSubmitButton"] button {
    font-size:15px!important;
    line-height:1.4!important;
    text-indent:0!important;
    letter-spacing:normal!important;
    white-space:nowrap!important;
}

[data-testid="stForm"] button:hover,
[data-testid="stForm"] button:focus,
[data-testid="stForm"] button:active,
[data-testid="stFormSubmitButton"]:hover,
[data-testid="stFormSubmitButton"]:focus {
    background:#1764ff!important;
    background-color:#1764ff!important;
    background-image:none!important;
    color:#ffffff!important;
    -webkit-text-fill-color:#ffffff!important;
    animation:none!important;
    transition:none!important;
    filter:none!important;
}
.candidate-auth-note{margin-top:12px;padding:13px 15px;background:#eaf2ff;border:1px solid #d9e7ff;border-radius:12px;color:#536d91;font-size:13px;line-height:1.55}
.candidate-auth-feature{height:100%;min-height:420px;padding:30px;border:1px solid #d6e5fa;border-radius:22px;background:radial-gradient(circle at 90% 5%,#d8e9ff 0,transparent 35%),linear-gradient(145deg,#edf5ff,#f9fbff 75%);box-shadow:0 12px 32px #25466d0a}
.candidate-auth-feature .kicker{font-size:11px;letter-spacing:1.3px;color:#2863c7;font-weight:800}
.candidate-auth-feature h2{font-size:clamp(25px,3vw,34px);letter-spacing:-.7px;line-height:1.2;margin:13px 0;color:#142d59}
.candidate-auth-feature h2 span{color:#1764ff}
.candidate-auth-feature>p{font-size:14px;line-height:1.7;color:#607492;margin:0 0 26px}
.candidate-feature-row{display:flex;align-items:center;gap:13px;margin:21px 0}
.candidate-feature-icon{display:flex;align-items:center;justify-content:center;width:48px;height:48px;border-radius:14px;font-size:23px;font-weight:800;flex-shrink:0}
.cfi-blue{background:#dceaff;color:#2863d9}
.cfi-green{background:#d8f7eb;color:#0d9a70}
.cfi-amber{background:#fff0d2;color:#c47b05}
.candidate-feature-row b{display:block;color:#1c3155;font-size:15px;margin-bottom:4px}
.candidate-feature-row small{display:block;color:#647792;font-size:13px;line-height:1.5}
.candidate-feature-foot{border-top:1px solid #d5e4f7;margin-top:26px;padding-top:17px;color:#456caa;font-size:13px;font-weight:650}
@media(max-width:900px){.candidate-auth-feature{min-height:0;padding:22px}.candidate-auth-feature h2{font-size:25px}.candidate-auth-heading h3{font-size:20px}}

div[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:0 4px 15px #203d7008}
div[data-testid="stMetric"] label,div[data-testid="stMetricValue"],div[data-testid="stMetricDelta"]{color:var(--ink)!important}
.stButton>button,[data-testid="stFormSubmitButton"] button{border-radius:10px!important;font-weight:750!important;min-height:43px;background:#fff!important;color:#17233b!important;border:1px solid #cbd7e8!important}
.stButton>button:hover,[data-testid="stFormSubmitButton"] button:hover{border-color:#1764ff!important;color:#1764ff!important}
.stButton>button[kind="primary"],[data-testid="stFormSubmitButton"] button[kind="primary"]{background:#1764ff!important;border-color:#1764ff!important;color:#fff!important}
input,textarea,[data-baseweb="input"],[data-baseweb="textarea"]{background:#fff!important;color:#17233b!important;border-color:#cbd7e8!important}
[data-baseweb="input"] input{color:#17233b!important;-webkit-text-fill-color:#17233b!important}
[data-baseweb="select"]>div{background:#fff!important;color:#17233b!important;border-color:#cbd7e8!important}
[data-testid="stFileUploader"] section{background:#fff!important;border:1px dashed #b9c9df!important}
[data-testid="stFileUploader"] *{color:#34445e!important}
[data-baseweb="tab-list"]{gap:8px;background:#f0f5ff;border-bottom:1px solid var(--line)}
[data-baseweb="tab"]{color:#52637e!important}
[data-baseweb="tab"][aria-selected="true"]{color:#1764ff!important;border-bottom-color:#1764ff!important}
[data-testid="stAlert"]{background:#edf4ff!important;color:#17233b!important;border:1px solid #cbdcf5!important}
[data-testid="stAlert"] p{color:#34445e!important}
hr{border-color:var(--line)!important}
/* Attractive candidate login and create-account forms */
[data-testid="stTabs"] [data-baseweb="tab-list"]{
    background:#eaf1ff!important;border:1px solid #d8e4f7!important;
    border-radius:14px!important;padding:5px!important;gap:6px!important;
}
[data-testid="stTabs"] button[data-baseweb="tab"]{
    border-radius:10px!important;padding:10px 18px!important;
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
[data-testid="stForm"] input{
    border-radius:10px!important;min-height:42px!important;
}
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

a{color:#075fc7!important}
/* Softer, more polished Apply Now buttons on job cards */
[class*="st-key-apply_job_card_"] button[kind="primary"]{
    background:#e4edff!important;
    border-color:#c9d9ff!important;
    color:#2456a6!important;
    box-shadow:0 2px 7px #2456a610!important;
}
[class*="st-key-apply_job_card_"] button[kind="primary"]:hover{
    background:#d5e3ff!important;
    border-color:#a9c4ff!important;
    color:#17458f!important;
}
/* Softer Company Login call-to-action */
[class*="st-key-company_login_cta"] button[kind="primary"]{
    background:#e4edff!important;
    border-color:#c9d9ff!important;
    color:#2456a6!important;
    box-shadow:0 2px 7px #2456a610!important;
}
[class*="st-key-company_login_cta"] button[kind="primary"]:hover{
    background:#d5e3ff!important;
    border-color:#a9c4ff!important;
    color:#17458f!important;
}
@media(max-width:700px){.hero{padding:24px}.hero h1{letter-spacing:-1px}}

/* Final, high-specificity override for candidate login submit button */
div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > button,
div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > button[kind="primary"],
div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > button:hover,
div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > button:focus,
div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > button:active {
    background: #1764ff !important;
    background-color: #1764ff !important;
    background-image: none !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    opacity: 1 !important;
    visibility: visible !important;
    text-indent: 0 !important;
    font-size: 15px !important;
    letter-spacing: normal !important;
    animation: none !important;
    transition: none !important;
    filter: none !important;
}
div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > button span,
div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > button p,
div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > button div {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    opacity: 1 !important;
    visibility: visible !important;
    animation: none !important;
    transition: none !important;
}

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




/* Hide Streamlit's sidebar completely; use the public navigation instead. */
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
[data-testid="stAppViewContainer"]{margin-left:0!important}

/* Candidate portal footer inspired by the provided Naukri reference */
.candidate-site-footer{
    margin-top:56px;padding:42px 0 24px;border-top:1px solid #e2e8f3;
    background:#fff;color:#111827;width:100%;
}
.candidate-footer-grid{
    display:grid;grid-template-columns:1.45fr 1fr 1.15fr 1fr;gap:34px;
    max-width:1180px;margin:0 auto;padding:0 22px;
}
.candidate-footer-brand{display:flex;align-items:center;gap:10px;color:#2458ed;font-size:28px;font-weight:850;letter-spacing:-.8px;margin-bottom:46px}
.candidate-footer-mark{display:inline-flex;align-items:center;justify-content:center;width:48px;height:48px;border-radius:50%;background:#315df5;color:#fff;font-size:28px}
.candidate-footer-title{font-size:16px;font-weight:750;color:#18243a;margin-bottom:14px}
.candidate-footer-links{display:flex;flex-direction:column;gap:15px}
.candidate-footer-links a{color:#283349!important;text-decoration:none!important;font-size:14px;line-height:1.4}
.candidate-footer-links a:hover{color:#2458ed!important}
.candidate-footer-social{display:flex;flex-wrap:wrap;gap:13px;margin-top:17px}
.candidate-footer-social a{display:inline-flex;align-items:center;justify-content:center;width:23px;height:23px;background:#8497bb;color:#fff!important;border-radius:3px;text-decoration:none!important;font-size:14px;font-weight:800}
.candidate-footer-bottom{max-width:1180px;margin:38px auto 0;padding:17px 22px 0;border-top:1px solid #e2e8f3;color:#718096;font-size:12px}
@media(max-width:760px){
 .candidate-footer-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:28px 20px;padding:0 12px}
 .candidate-footer-brand{font-size:22px;margin-bottom:20px}
 .candidate-footer-mark{width:38px;height:38px}
 .candidate-footer-bottom{margin-top:25px;padding-left:12px;padding-right:12px}
}

/* Naukri-inspired top navigation for candidate portal */
.stApp .st-key-candidate_top_nav{
    background:#fff!important;border:0!important;border-bottom:1px solid #edf0f6!important;border-radius:0!important;
    padding:8px 12px!important;margin:-10px -12px 22px!important;
    box-shadow:0 2px 12px rgba(27,45,84,.035)!important;overflow:visible!important;
}
.stApp .st-key-candidate_top_nav [data-testid="stHorizontalBlock"]{
    display:flex!important;flex-flow:row nowrap!important;align-items:center!important;justify-content:center!important;gap:clamp(3px,.35vw,7px)!important;
    width:100%!important;max-width:1415px!important;margin:0 auto!important;overflow:visible!important;
}
.stApp .st-key-candidate_top_nav [data-testid="column"]{min-width:0!important;flex-shrink:1!important;padding:0!important}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(1){flex:1.75 1 0!important}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(2){flex:.72 1 0!important}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(3){flex:.92 1 0!important}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(4){flex:1.02 1 0!important}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(5){flex:1.95 1 0!important;max-width:285px!important}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(6){flex:0 0 2px!important;max-width:2px!important}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(7){flex:0 0 40px!important;max-width:40px!important}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(8){flex:0 0 150px!important;max-width:150px!important}
.candidate-nav-brand{display:flex;align-items:center;gap:7px;white-space:nowrap;color:#2458ed;font-size:22px;font-weight:850;letter-spacing:-.7px;min-height:42px}
.candidate-nav-mark{display:inline-flex;align-items:center;justify-content:center;width:31px;height:31px;border-radius:50%;background:#2f5df5;color:#fff;font-size:19px;flex-shrink:0}
.candidate-nav-blue{color:#2458ed}.candidate-nav-orange{color:#f05a28;margin-left:3px}
.stApp .st-key-candidate_top_nav [data-testid="stButton"]{width:100%!important}
.stApp .st-key-candidate_top_nav [data-testid="stButton"] button{
    width:100%!important;min-width:0!important;min-height:40px!important;border-radius:22px!important;background:transparent!important;
    border:1px solid transparent!important;color:#35415e!important;font-weight:500!important;
    padding:0 4px!important;white-space:nowrap!important;box-shadow:none!important;font-size:clamp(11px,.85vw,14px)!important
}
/* Notification bell and profile pill: match the supplied reference */
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(7) [data-testid="stButton"] button{
    position:relative!important;display:flex!important;align-items:center!important;justify-content:center!important;
    width:44px!important;min-width:44px!important;height:48px!important;min-height:48px!important;
    border:0!important;border-radius:50%!important;background:transparent!important;
    color:transparent!important;font-size:0!important;padding:0!important;box-shadow:none!important;
}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(7) [data-testid="stButton"] button::before{
    content:"";display:block!important;width:29px!important;height:32px!important;flex:0 0 29px!important;
    background-repeat:no-repeat!important;background-position:center!important;background-size:contain!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='30' height='34' viewBox='0 0 30 34' fill='none'%3E%3Cpath d='M15 4.5c-5.1 0-8.1 3.9-8.1 9.1v4.1c0 1.9-.7 3.3-2 4.7L3 24.5c-.8 1-.2 2.1 1 2.1h22c1.2 0 1.8-1.1 1-2.1l-1.9-2.1c-1.3-1.4-2-2.8-2-4.7v-4.1c0-5.2-3-9.1-8.1-9.1Z' stroke='%23717FA6' stroke-width='1.45' stroke-linejoin='round'/%3E%3Cpath d='M11.5 29c.6 1.8 1.8 2.7 3.5 2.7s2.9-.9 3.5-2.7' stroke='%23717FA6' stroke-width='1.45' stroke-linecap='round'/%3E%3Cpath d='M13 3.2c.2-1 1-1.7 2-1.7s1.8.7 2 1.7' stroke='%23717FA6' stroke-width='1.45' stroke-linecap='round'/%3E%3C/svg%3E")!important;
}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(7) [data-testid="stButton"] button::after{
    content:"4";position:absolute;right:0;top:0;width:19px;height:19px;border-radius:50%;
    display:flex;align-items:center;justify-content:center;background:#f04452;color:#fff;
    font:700 11px/1 Arial,sans-serif;border:2px solid #fff;box-sizing:border-box;
}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(8) [data-testid="stButton"] button,
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(8) [data-testid="stButton"] button:hover,
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(8) [data-testid="stButton"] button:focus,
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(8) [data-testid="stButton"] button:active{
    position:relative!important;display:flex!important;align-items:center!important;justify-content:space-between!important;
    width:150px!important;min-width:150px!important;height:53px!important;min-height:53px!important;
    padding:0 10px!important;border:1px solid #d8e2ff!important;border-radius:29px!important;
    background-color:#f2f6ff!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'%3E%3Cdefs%3E%3CclipPath id='c'%3E%3Ccircle cx='16' cy='16' r='15'/%3E%3C/clipPath%3E%3C/defs%3E%3Cg clip-path='url(%23c)'%3E%3Crect width='32' height='32' fill='%23e9d6c7'/%3E%3Cpath d='M1 32c1-8 6-12 15-12s14 4 15 12' fill='%234a6a8d'/%3E%3Ccircle cx='16' cy='12' r='6' fill='%23f1c9ad'/%3E%3Cpath d='M9 12c0-7 3-10 8-9 5 1 7 5 6 10l-2-4c-4 1-7-1-9-3l-3 6Z' fill='%234a342e'/%3E%3C/g%3E%3Ccircle cx='16' cy='16' r='15' fill='none' stroke='%23e2e6ef'/%3E%3C/svg%3E")!important;
    background-repeat:no-repeat!important;background-position:right 10px center!important;background-size:32px 32px!important;
    color:#8b9abc!important;font-size:21px!important;gap:8px!important;
    box-shadow:none!important;white-space:nowrap!important;overflow:visible!important;
}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(8) [data-testid="stButton"] button span,
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(8) [data-testid="stButton"] button p{
    display:inline-flex!important;align-items:center!important;justify-content:center!important;
}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(8) [data-testid="stButton"] button::before{
    content:"";position:absolute;left:58px;top:17px;width:18px;height:18px;
    background-repeat:no-repeat;background-position:center;background-size:contain;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 20 20' fill='none'%3E%3Cpath d='M3 5h14M3 10h14M3 15h14' stroke='%238b9abc' stroke-width='1.7' stroke-linecap='round'/%3E%3C/svg%3E")!important;
}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(8) [data-testid="stButton"] button{
    font-size:0!important;
}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(8) [data-testid="stButton"] button::after{content:none!important;display:none!important;}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(8) [data-testid="stButton"] button::after{z-index:3;}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(8) [data-testid="stButton"] button .profile-avatar-circle{
    width:30px;height:30px;border-radius:50%;overflow:hidden;display:inline-flex;align-items:center;justify-content:center;
}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(8) [data-testid="stButton"] button::after{
    content:"2";position:absolute;right:-1px;top:0;width:19px;height:19px;border-radius:50%;
    display:flex;align-items:center;justify-content:center;background:#f04452;color:#fff;
    font:700 11px/1 Arial,sans-serif;border:2px solid #fff;box-sizing:border-box;
}
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(8) [data-testid="stButton"] button:hover{
    border-color:#e2e6ef!important;background:#fff!important;color:#7180a6!important;
}.stApp .st-key-candidate_top_nav [data-testid="stButton"] button:hover{
    background:#f3f6ff!important;border-color:#dce5ff!important;color:#2458ed!important
}
.stApp .st-key-candidate_top_nav [data-testid="stTextInput"]{min-width:0!important}
.stApp .st-key-candidate_top_nav [data-testid="stTextInput"] input{
    box-sizing:border-box!important;width:100%!important;min-width:0!important;min-height:42px!important;
    border-radius:24px!important;border:1px solid #e0e6f0!important;padding:0 16px!important;
    background:#fff!important;color:#33415e!important;box-shadow:0 3px 12px #182b4b0a!important;outline:none!important;
}
.stApp .st-key-candidate_top_nav [data-testid="stTextInput"] input::placeholder{color:#7b879e!important;opacity:1!important}
.stApp .st-key-candidate_top_nav [data-testid="stTextInput"] [data-baseweb="base-input"]{border:0!important;box-shadow:none!important;background:transparent!important}
@media(max-width:900px){
 .stApp .st-key-candidate_top_nav{padding:8px 5px!important;margin:0 0 16px!important}
 .candidate-nav-brand{font-size:14px;gap:4px}.candidate-nav-mark{width:26px;height:26px}
 .stApp .st-key-candidate_top_nav [data-testid="stButton"] button{font-size:10px!important;padding:0 2px!important}
}

/* Reference-style recommendation and employer discovery cards */
.market-section-heading{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:22px 0 12px}
.market-section-heading h3{margin:0;font-size:21px;font-weight:750;color:#17233b}
.market-section-heading span{color:#245cff;font-weight:650;font-size:14px}
.recommended-job-card{position:relative;min-height:174px;padding:14px;border:1px solid #e0e6f0;border-radius:18px;background:#fff;box-shadow:0 4px 14px #203d7008}
.recommended-job-logo{width:42px;height:42px;display:flex;align-items:center;justify-content:center;border:1px solid #e2e8f2;border-radius:9px;background:#f8faff;color:#7854f7;font-size:22px;font-weight:750}
.recommended-job-age{position:absolute;right:13px;top:15px;font-size:11px;color:#8090aa}
.recommended-job-title{margin-top:12px;font-size:15px;font-weight:750;color:#17233b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.recommended-job-company{margin-top:3px;font-size:12px;color:#586783;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.recommended-job-mode{margin-top:9px;font-size:12px;color:#7586a2}
.company-job-card{display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:7px;min-height:155px;padding:15px 10px;background:#fff;border:1px solid #e0e6f0;border-radius:18px;box-shadow:0 4px 14px #203d7008}
.company-logo-placeholder{display:flex;align-items:center;justify-content:center;width:46px;height:46px;border:1px solid #e2e8f2;border-radius:12px;background:#fff;color:#2454f5;font-size:19px;font-weight:850}
.company-job-name{max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:15px;font-weight:750;color:#17233b}
.company-job-count{font-size:12px;color:#71809a}



/* Compact, stable four-column employer grid: isolate it from global responsive column wrapping. */
.stApp .st-key-company_showcase_grid{width:100%;min-width:0}
.stApp .st-key-company_showcase_grid [data-testid="stHorizontalBlock"]{
    display:flex!important;flex-wrap:nowrap!important;align-items:stretch!important;gap:14px!important;
}
.stApp .st-key-company_showcase_grid [data-testid="column"]{
    flex:1 1 0!important;width:0!important;min-width:0!important;max-width:25%!important;
}
.stApp .st-key-company_showcase_grid .company-job-card{
    width:100%;box-sizing:border-box;min-height:190px!important;height:190px!important;
    padding:17px 8px 14px!important;gap:8px!important;overflow:hidden;
}
.stApp .st-key-company_showcase_grid .company-logo-wrap{height:58px!important;flex-shrink:0}
.stApp .st-key-company_showcase_grid .company-job-name{display:block;line-height:1.35!important;min-height:20px;overflow:visible;text-overflow:clip}
.stApp .st-key-company_showcase_grid .company-job-count{line-height:1.35!important;white-space:nowrap}
.stApp .st-key-company_showcase_grid .company-demo-note{line-height:1.3!important;min-height:12px}
.stApp .company-logo-wrap{
    width:64px;height:58px;display:flex;align-items:center;justify-content:center;
    flex:0 0 auto;background:#fff;border:1px solid #e1e8f3;border-radius:14px;
    overflow:hidden;box-shadow:0 4px 12px rgba(25,55,110,.07)
}
.stApp .brand-mark{display:flex;align-items:center;justify-content:center;width:100%;height:100%;padding:5px;box-sizing:border-box;font-weight:850;line-height:1;white-space:nowrap}
.stApp .brand-tcs{font-size:19px;letter-spacing:-.8px;color:#3156a6}
.stApp .brand-infosys{font-size:15px;letter-spacing:-.8px;color:#007cc3}
.stApp .brand-wipro{font-size:18px;letter-spacing:-1px;color:#3b62c4}
.stApp .brand-hcl{font-size:15px;letter-spacing:-.7px;color:#2763e9}
.stApp .brand-generic{font-size:19px;color:#2454f5}
.stApp .st-key-company_showcase_grid .company-job-name{font-size:14px!important}
.stApp .st-key-company_showcase_grid [data-testid="stButton"] button{min-height:40px!important;margin-top:2px!important}
@media(max-width:700px){
    .stApp .st-key-company_showcase_grid [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important;gap:10px!important}
    .stApp .st-key-company_showcase_grid [data-testid="column"]{flex:1 1 calc(50% - 10px)!important;width:auto!important;max-width:calc(50% - 5px)!important}
    .stApp .st-key-company_showcase_grid .company-job-card{height:176px!important;min-height:176px!important}
}

/* Attractive employer showcase with polished cards and hover states */
.market-section-heading{margin:24px 0 14px!important}
.market-section-heading h3{font-size:23px!important;letter-spacing:-.45px}
.stApp .company-job-card{
 position:relative;overflow:hidden;min-height:184px!important;padding:17px 10px 14px!important;
 gap:8px!important;border-radius:20px!important;border:1px solid #dce6f7!important;
 background:linear-gradient(155deg,#ffffff 0%,#f8fbff 68%,#edf4ff 100%)!important;
 box-shadow:0 7px 22px rgba(31,70,140,.07)!important;
 transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease!important
}
.stApp .company-job-card:before{content:"";position:absolute;left:0;right:0;top:0;height:4px;background:linear-gradient(90deg,#2563eb,#60a5fa,#a78bfa)}
.stApp .company-logo-placeholder{
 width:54px!important;height:54px!important;border-radius:16px!important;
 border:1px solid #dbe7ff!important;background:linear-gradient(145deg,#fff,#eaf1ff)!important;
 color:#255be8!important;font-size:21px!important;font-weight:850!important;
 box-shadow:0 5px 12px rgba(37,99,235,.08)!important
}
.stApp .company-job-name{font-size:15px!important;font-weight:800!important;letter-spacing:-.2px;color:#172b4d!important}
.stApp .company-job-rating{font-size:11px!important;font-weight:650;color:#64748b!important}
.stApp .company-job-rating:first-letter{color:#f59e0b}
.stApp .company-job-rating span{padding:0 5px;color:#c3cedd}
.stApp .company-job-count{font-size:11px!important;font-weight:650;color:#557095!important;background:#edf4ff;border:1px solid #dce8ff;border-radius:20px;padding:5px 9px}
.stApp .company-demo-note{font-size:9px;letter-spacing:.8px;text-transform:uppercase;color:#8b98ad}
.stApp [data-testid="stButton"] button:has(+ .company-job-card){border-radius:11px!important}
.stApp .company-job-card:hover{transform:translateY(-2px);box-shadow:0 12px 26px rgba(31,70,140,.12)!important;border-color:#b9d0ff!important}
@media(max-width:800px){.stApp .company-job-card{min-height:160px!important;padding:13px 6px!important;border-radius:15px!important}.stApp .company-job-name{font-size:12px!important}.stApp .company-logo-placeholder{width:43px!important;height:43px!important}}

/* Company discovery cards matching the compact marketplace reference */
.company-job-card{display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:7px;min-height:150px;padding:16px 12px;background:#fff;border:1px solid #dce5f2;border-radius:18px;box-shadow:0 4px 16px #1b315008}
.company-logo-placeholder{display:flex;align-items:center;justify-content:center;width:46px;height:46px;border:1px solid #e1e8f3;border-radius:13px;background:#f8faff;color:#2454f5;font-size:22px;font-weight:900}
.company-job-name{max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:16px;font-weight:750;color:#17233b}
.company-job-count{font-size:12px;color:#71809a}

/* Three-column job marketplace cards, compact by design */
.stApp .job-tile{padding:14px!important;margin:0 0 8px!important;border-radius:15px!important;background:#fff!important;border:1px solid #dce6f5!important;min-height:285px!important;display:flex;flex-direction:column}
.stApp .job-tile .job-tile-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:12px}
.stApp .job-tile .job-tile-logo{width:34px;height:34px;display:flex;align-items:center;justify-content:center;border:1px solid #e1e9f6;border-radius:10px;background:#f7faff;color:#2454f5;font-size:17px;font-weight:900}
.stApp .job-tile .job-mode-pill{font-size:10px;padding:4px 8px}
.stApp .job-tile .job-tile-department{font-size:9px;letter-spacing:1px;text-transform:uppercase;font-weight:800;color:#087cc0;margin-bottom:5px}
.stApp .job-tile .job-tile-title{font-size:17px!important;line-height:1.25!important;color:#17233b!important;margin:0 0 8px!important;min-height:42px}
.stApp .job-tile .job-tile-description{font-size:12px!important;line-height:1.45!important;color:#52637e!important;margin:0 0 12px!important;min-height:52px}
.stApp .job-tile .job-tile-skills{font-size:11px;line-height:1.4;color:#52637e;border-top:1px solid #edf1f7;padding-top:9px;min-height:55px}
.stApp .job-tile .job-tile-skills b{color:#344a69}
.stApp .job-tile .job-tile-budget{margin-top:auto;padding-top:9px;font-size:12px;font-weight:750;color:#263f65}
@media(max-width:850px){.stApp .job-tile{min-height:0!important}.stApp .job-tile .job-tile-title,.stApp .job-tile .job-tile-description,.stApp .job-tile .job-tile-skills{min-height:0!important}}

/* Marketplace-style compact job tiles */
.stApp .jobcard-compact{padding:12px 15px!important;margin:6px 0 4px!important;border-radius:12px!important;min-height:0!important}
.stApp .jobcard-compact .jobcard-top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.stApp .jobcard-compact .kicker{font-size:9px!important;letter-spacing:1.1px!important;margin-bottom:2px}
.stApp .jobcard-compact h3{font-size:17px!important;line-height:1.2!important;margin:3px 0!important}
.stApp .jobcard-compact .job-description{font-size:12px!important;line-height:1.35!important;margin:5px 0 7px!important}
.stApp .jobcard-compact .job-meta{display:flex;flex-wrap:wrap;gap:5px 18px;font-size:11px;line-height:1.35;color:#526987}
.stApp .jobcard-compact .job-meta b{color:#344a69}
.stApp .jobcard-compact .job-mode-pill{white-space:nowrap;border:1px solid #c9d9ff;border-radius:20px;padding:4px 9px;background:#e4edff;color:#2456a6;font-size:10px;font-weight:700}

/* Compact public job cards: strong height reduction so more jobs fit per screen */
.stApp .jobcard{
    padding:10px 14px!important;
    margin:5px 0 4px!important;
    border-radius:12px!important;
    box-shadow:0 2px 8px #203d7006!important;
}
.stApp .jobcard h3{
    font-size:17px!important;
    line-height:1.2!important;
    margin:2px 0 3px!important;
}
.stApp .jobcard p{
    font-size:12px!important;
    line-height:1.3!important;
    margin:3px 0!important;
}
.stApp .jobcard .kicker{font-size:9px!important;letter-spacing:1px!important}
.stApp .jobcard span[style*="border-radius:20px"]{padding:3px 8px!important;font-size:10px!important}
.stApp .jobcard b{font-weight:700!important}


/* Final screenshot polish: keep primary button text readable over blue fills */
.stApp [data-testid="stButton"] button[kind="primary"],
.stApp [data-testid="stFormSubmitButton"] button[kind="primary"],
.stApp button[kind="primary"]{
    background:#1764ff!important;
    background-color:#1764ff!important;
    border:1px solid #1764ff!important;
    color:#ffffff!important;
    -webkit-text-fill-color:#ffffff!important;
    font-weight:750!important;
    opacity:1!important;
}
.stApp [data-testid="stButton"] button[kind="primary"] *,
.stApp [data-testid="stFormSubmitButton"] button[kind="primary"] *,
.stApp button[kind="primary"] *{
    color:#ffffff!important;
    -webkit-text-fill-color:#ffffff!important;
    opacity:1!important;
}
.stApp [data-testid="stButton"] button[kind="primary"]:hover{
    background:#104fd0!important;
    border-color:#104fd0!important;
    color:#ffffff!important;
}
.landing-hero{box-shadow:0 12px 30px #203d700b}
.role-card{display:flex;flex-direction:column;min-height:230px}
.role-card p{min-height:62px}

/* Blueprint-inspired public landing page */
.landing-nav{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:8px 2px 18px;border-bottom:1px solid #dce6f5;margin-bottom:20px}
.landing-brand{font-size:22px;font-weight:900;letter-spacing:-.6px;color:#14294b}
.landing-brand span{color:#1764ff}
.landing-nav-note{font-size:12px;font-weight:750;letter-spacing:1px;color:#526987}
.landing-hero{display:grid;grid-template-columns:1.25fr .75fr;gap:24px;align-items:center;padding:34px;border:1px solid #d6e4fa;border-radius:24px;background:radial-gradient(circle at 95% 5%,#d7e6ff 0,transparent 34%),linear-gradient(120deg,#fff,#eaf2ff);box-shadow:0 14px 35px #203d7010;margin-bottom:20px}
.landing-hero .eyebrow{font-size:11px;font-weight:850;letter-spacing:1.5px;color:#1764ff}
.landing-hero h1{font-size:clamp(32px,4vw,53px);letter-spacing:-1.7px;line-height:1.07;color:#14294b;margin:13px 0}
.landing-hero h1 span{color:#1764ff}
.landing-hero p{font-size:15px;line-height:1.75;color:#526987;max-width:620px}
.landing-visual{min-height:235px;border-radius:20px;padding:20px;background:linear-gradient(145deg,#d9e8ff,#f8fbff);border:1px solid #d2e2fa;display:flex;flex-direction:column;justify-content:center;gap:12px}
.landing-visual-card{background:#ffffffdc;border:1px solid #d5e4f7;border-radius:13px;padding:12px 14px;color:#243d63;font-weight:700;box-shadow:0 4px 12px #203d7008}
.landing-visual-card small{display:block;font-size:11px;color:#647792;font-weight:500;margin-top:3px}
.landing-trust{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 0}
.landing-trust span{padding:7px 10px;border:1px solid #d6e4fa;border-radius:30px;background:#ffffffb8;font-size:11px;font-weight:700;color:#31527e}
.role-card{height:100%;padding:22px;border:1px solid #d7e4f7;border-radius:18px;background:linear-gradient(145deg,#fff,#f4f8ff);box-shadow:0 6px 20px #203d7008}
.role-card.talent{background:linear-gradient(145deg,#fff,#f5f0ff);border-color:#e1d7fb}
.role-icon{font-size:30px;margin-bottom:8px}
.role-card h3{margin:0 0 7px;color:#172e55;font-size:19px}
.role-card p{font-size:13px;line-height:1.6;color:#5d708b;min-height:62px}
.feature-card{padding:16px;border:1px solid #dce6f5;border-radius:14px;background:#fff;height:100%}
.feature-card b{display:block;color:#243d63;margin:7px 0}
.feature-card small{color:#647792;line-height:1.5}
.section-kicker{font-size:11px;font-weight:850;letter-spacing:1.2px;color:#2863c7}
@media(max-width:800px){.landing-hero{grid-template-columns:1fr;padding:22px}.landing-visual{min-height:0}.landing-hero h1{font-size:34px}.landing-nav-note{display:none}}


/* Premium candidate login refresh — visual-only; auth flow unchanged */
.stApp .stAppViewContainer .main{background:linear-gradient(135deg,#f4f7ff 0%,#edf3ff 52%,#f8faff 100%)!important}
.stApp .stAppViewContainer .main .block-container{max-width:1320px!important;padding-top:28px!important;padding-bottom:48px!important}
.stApp .stAppViewContainer .main .block-container:has(.naukri-login-benefits){position:relative}
.stApp .st-key-auth_landing_nav{
 margin:0 -12px 30px!important;padding:12px 0!important;min-height:76px!important;
 background:rgba(255,255,255,.88)!important;border:1px solid #e1e9fb!important;
 border-radius:18px!important;box-shadow:0 8px 28px rgba(35,72,145,.07)!important;
}
.stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"]{padding:0 18px!important}
.auth-brand{font-size:23px!important;font-weight:850!important;letter-spacing:-.7px!important;color:#142b55!important}
.auth-brand-mark{border-radius:10px!important;box-shadow:0 5px 14px rgba(37,91,230,.25)!important}
.naukri-login-benefits{
 min-height:420px!important;padding:42px 38px 36px!important;
 background:radial-gradient(circle at 100% 0%,rgba(203,220,255,.75),transparent 35%),linear-gradient(145deg,#fff 0%,#f5f8ff 100%)!important;
 border:1px solid #dce7fc!important;border-radius:24px!important;
 box-shadow:0 18px 48px rgba(32,70,140,.10)!important;color:#10294d!important;
}
.naukri-login-benefits h3{font-size:clamp(23px,2.2vw,30px)!important;font-weight:800!important;letter-spacing:-.8px!important;line-height:1.2!important;margin:0 0 26px!important;color:#142b55!important}
.naukri-login-benefits .benefit-row{display:flex;align-items:center;gap:12px;margin:0 0 18px!important;font-size:15px!important;line-height:1.55!important;color:#405574!important}
.naukri-login-benefits .benefit-row span{display:inline-grid;place-items:center;width:25px;height:25px;flex:0 0 25px;border-radius:50%;background:#e1edff;color:#2160ee!important;font-size:15px!important;font-weight:800!important}
.naukri-login-benefits .benefit-illustration{position:static!important;max-width:none!important;margin-top:28px;padding:15px 16px;border:1px solid #dce7ff;border-radius:14px;background:linear-gradient(110deg,#edf4ff,#fff);color:#33527f!important;font-size:13px!important;line-height:1.5}
.stApp [data-testid="stForm"]{
 border:1px solid #dce6fb!important;border-radius:24px!important;padding:30px 32px!important;
 background:rgba(255,255,255,.94)!important;box-shadow:0 18px 48px rgba(32,70,140,.11)!important;
}
.stApp .candidate-auth-heading{display:flex!important;align-items:center!important;gap:15px!important;margin:0 0 22px!important}
.stApp .candidate-auth-heading h3{font-size:27px!important;font-weight:800!important;letter-spacing:-.7px!important;color:#142b55!important}
.stApp .candidate-auth-icon{width:58px!important;height:58px!important;border-radius:18px!important;box-shadow:0 8px 18px rgba(49,103,228,.12)!important}
.stApp [data-testid="stForm"] label{font-size:13px!important;font-weight:700!important;color:#334765!important}
.stApp [data-testid="stForm"] input{border-radius:12px!important;min-height:48px!important;border:1px solid #d4deef!important;background:#fbfcff!important}
.stApp [data-testid="stForm"] input:focus{border-color:#3b72f6!important;box-shadow:0 0 0 3px rgba(59,114,246,.12)!important}
.stApp [data-testid="stForm"] button,.stApp [data-testid="stFormSubmitButton"] button{
 min-height:49px!important;border-radius:12px!important;font-weight:750!important;
 background:linear-gradient(100deg,#2158ed,#397bff)!important;border:1px solid #2b66f4!important;
 box-shadow:0 8px 18px rgba(37,96,235,.22)!important;transition:transform .18s ease,box-shadow .18s ease!important;
}
.stApp [data-testid="stForm"] button:hover,.stApp [data-testid="stFormSubmitButton"] button:hover{transform:translateY(-1px)!important;box-shadow:0 11px 22px rgba(37,96,235,.28)!important}
.stApp .candidate-auth-note{margin-top:16px!important;padding:15px 17px!important;border-radius:14px!important;background:linear-gradient(110deg,#eaf2ff,#f6f9ff)!important;border:1px solid #d7e5ff!important;color:#4c6388!important}
.stApp .st-key-auth_benefits_register button{border:1px solid #c9d8f8!important;color:#245be8!important;background:#fff!important;border-radius:11px!important;font-weight:750!important;padding:10px 17px!important;transition:all .18s ease!important}
.stApp .st-key-auth_benefits_register button:hover{background:#edf3ff!important;border-color:#8eafff!important}
@media(max-width:900px){
 .stApp .stAppViewContainer .main .block-container{padding:18px 16px 32px!important}
 .stApp .st-key-auth_landing_nav{border-radius:14px!important;margin-bottom:22px!important}
 .naukri-login-benefits{min-height:0!important;padding:28px 24px!important;border-radius:20px!important}
 .stApp [data-testid="stForm"]{padding:24px 22px!important;border-radius:20px!important}
}

/* Attractive job search field in candidate navigation */
.stApp .st-key-auth_landing_nav .st-key-auth_header_search{
 position:relative!important;margin:0!important;padding:0!important;
}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"]{margin:0!important}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"]>div{
 min-height:48px!important;border:1px solid #d6e2f7!important;border-radius:14px!important;
 background:linear-gradient(135deg,#fff,#f7faff)!important;
 box-shadow:0 5px 15px rgba(35,82,170,.07)!important;
 transition:border-color .18s ease,box-shadow .18s ease!important;
}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"]>div:focus-within{
 border-color:#6c95ff!important;box-shadow:0 0 0 4px rgba(58,108,245,.12),0 8px 20px rgba(35,82,170,.10)!important;
}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search input{
 min-height:46px!important;border:0!important;box-shadow:none!important;background:transparent!important;
 padding:0 14px 0 40px!important;color:#172b4d!important;font-size:13px!important;
}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search input::placeholder{color:#8797b1!important;opacity:1!important}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"]>div:before{
 content:"⌕";position:absolute;z-index:2;left:13px;top:7px;color:#4776e8;font-size:25px;line-height:30px;font-weight:700;pointer-events:none;
}
@media(max-width:900px){
 .stApp .st-key-auth_landing_nav .st-key-auth_header_search input{padding-left:34px!important;font-size:11px!important}
 .stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"]>div:before{left:9px}
}

/* Match the user's reference search field: bold dark rim, white pill, no icon */
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"]>div{
 min-height:52px!important;padding:3px!important;border:4px solid #292b35!important;
 border-radius:17px!important;background:#292b35!important;box-shadow:none!important;
 transition:border-color .18s ease!important;
}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"]>div:before{content:none!important;display:none!important}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search input{
 min-height:42px!important;height:42px!important;padding:0 18px!important;
 border:0!important;border-radius:13px!important;background:#fff!important;
 box-shadow:none!important;color:#26344f!important;font-size:14px!important;
}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search input::placeholder{color:#71809c!important;opacity:1!important}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"]>div:focus-within{
 border-color:#3b66ee!important;box-shadow:0 0 0 2px rgba(59,102,238,.12)!important;
}

/* Align search input with the same rounded outline style as Services nav button */
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"]>div{
 min-height:54px!important;height:54px!important;padding:0!important;
 border:1px solid #cbd8ef!important;border-radius:14px!important;
 background:#fff!important;box-shadow:none!important;overflow:hidden!important;
 transition:border-color .18s ease,box-shadow .18s ease!important;
}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"]>div:before{content:none!important;display:none!important}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search input{
 min-height:52px!important;height:52px!important;padding:0 18px!important;
 border:0!important;border-radius:13px!important;background:transparent!important;
 box-shadow:none!important;color:#26344f!important;font-size:14px!important;
}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"]>div:focus-within{
 border-color:#8daaf1!important;box-shadow:0 0 0 2px rgba(59,102,238,.08)!important;
}

/* Final fix: search box must match the white Services button */
.stApp .st-key-auth_landing_nav .st-key-auth_header_search,
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"],
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"]>div{
 background:transparent!important;
}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"]>div{
 min-height:54px!important;height:54px!important;padding:0!important;
 border:1px solid #cbd8ef!important;border-radius:14px!important;
 background:#ffffff!important;box-shadow:none!important;overflow:hidden!important;
}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search input,
.stApp .st-key-auth_landing_nav .st-key-auth_header_search input:focus,
.stApp .st-key-auth_landing_nav .st-key-auth_header_search input:hover{
 min-height:52px!important;height:52px!important;padding:0 18px!important;
 border:0!important;border-radius:13px!important;
 background:#ffffff!important;background-color:#ffffff!important;
 color:#26344f!important;-webkit-text-fill-color:#26344f!important;
 box-shadow:none!important;outline:none!important;font-size:14px!important;
}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search input::placeholder{
 color:#71809c!important;-webkit-text-fill-color:#71809c!important;opacity:1!important;
}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"]>div:focus-within{
 border-color:#cbd8ef!important;box-shadow:0 0 0 2px rgba(59,102,238,.06)!important;
}

/* Ensure Streamlit BaseWeb input wrappers stay white, not dark */
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-baseweb="input"],
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-baseweb="base-input"],
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"] input{
 background:#fff!important;background-color:#fff!important;
 color:#26344f!important;-webkit-text-fill-color:#26344f!important;
 border:0!important;box-shadow:none!important;
}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-baseweb="input"]{
 border-radius:13px!important;min-height:52px!important;
}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"]>div{
 padding:0!important;background:#fff!important;border:1px solid #cbd8ef!important;
 border-radius:14px!important;overflow:hidden!important;box-shadow:none!important;
}
.stApp .st-key-auth_landing_nav .st-key-auth_header_search input{
 padding:0 18px!important;height:52px!important;min-height:52px!important;
 border-radius:13px!important;background:#fff!important;background-color:#fff!important;
}

/* =========================================================
   Responsive layout pass: desktop, tablet and mobile
   Visual-only CSS; keep Streamlit pages and backend behavior intact.
   ========================================================= */
html,body,[data-testid="stAppViewContainer"],[data-testid="stMain"],.stApp{
 width:100%!important;max-width:100%!important;overflow-x:hidden!important;
}
.stApp .stAppViewContainer .main .block-container,
[data-testid="stMainBlockContainer"]{
 width:100%!important;max-width:1440px!important;
 padding-left:clamp(12px,2.8vw,40px)!important;
 padding-right:clamp(12px,2.8vw,40px)!important;
 box-sizing:border-box!important;
}
[data-testid="stHorizontalBlock"]{min-width:0!important;max-width:100%!important}
[data-testid="column"]{min-width:0!important;box-sizing:border-box!important}
[data-testid="stMarkdownContainer"],[data-testid="stMarkdownContainer"] *{overflow-wrap:anywhere}
img,svg,video,canvas{max-width:100%;height:auto}
[data-testid="stDataFrame"],[data-testid="stTable"],[data-testid="stDataEditor"]{max-width:100%!important;overflow-x:auto!important}
input,textarea,select,button{max-width:100%}
.stApp .st-key-auth_landing_nav{max-width:100%!important;box-sizing:border-box!important}
.stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"]{max-width:100%!important;box-sizing:border-box!important}
@media (max-width: 1100px){
 .stApp .stAppViewContainer .main .block-container,[data-testid="stMainBlockContainer"]{
  padding-left:20px!important;padding-right:20px!important;
 }
 .naukri-login-benefits{padding:30px 26px!important}
 .stApp [data-testid="stForm"]{padding:26px!important}
}
@media (max-width: 760px){
 .stApp .stAppViewContainer .main .block-container,[data-testid="stMainBlockContainer"]{
  padding:16px 12px 28px!important;
 }
 /* Header wraps instead of pushing the viewport wider than the phone */
 .stApp .st-key-auth_landing_nav{margin:0 0 20px!important;padding:10px!important;border-radius:14px!important}
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"]{
  width:100%!important;max-width:100%!important;padding:0!important;
  display:flex!important;flex-flow:row wrap!important;gap:8px!important;justify-content:flex-start!important;
 }
 .stApp .st-key-auth_landing_nav [data-testid="column"]{
  flex:1 1 calc(33.333% - 8px)!important;width:auto!important;max-width:none!important;min-width:0!important;
 }
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(1){
  flex:1 1 100%!important;width:100%!important;order:0!important;
 }
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(5){
  flex:1 1 100%!important;width:100%!important;max-width:100%!important;order:1!important;
 }
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(2){order:2!important}
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(3){order:3!important}
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(4){order:4!important}
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(6){order:5!important}
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(7){order:6!important}
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(8){flex:1 1 100%!important;width:100%!important;order:7!important}
 .stApp .st-key-auth_landing_nav [data-testid="stButton"] button{width:100%!important;min-height:42px!important;padding:7px 8px!important;font-size:12px!important;white-space:normal!important}
 .stApp .st-key-auth_landing_nav .st-key-auth_header_search [data-testid="stTextInput"]>div{width:100%!important}
 .stApp .st-key-auth_landing_nav .st-key-auth_header_search input{font-size:14px!important}
 /* Stack the login benefits and form cleanly */
 .stApp [data-testid="stHorizontalBlock"]:has(.naukri-login-benefits){flex-direction:column!important;gap:18px!important}
 .stApp [data-testid="stHorizontalBlock"]:has(.naukri-login-benefits)>[data-testid="column"]{width:100%!important;max-width:100%!important;flex:1 1 100%!important}
 .naukri-login-benefits{min-height:0!important;padding:26px 22px!important;border-radius:18px!important}
 .naukri-login-benefits .benefit-row{font-size:14px!important;margin-bottom:13px!important}
 .naukri-login-benefits .benefit-illustration{position:static!important;margin-top:18px!important}
 .stApp [data-testid="stForm"]{padding:22px 18px!important;border-radius:18px!important}
 .stApp .candidate-auth-heading h3{font-size:23px!important}
 .stApp .candidate-auth-icon{width:48px!important;height:48px!important;border-radius:14px!important;font-size:24px!important}
 /* Prevent wide dashboard grids and forms from overflowing */
 .metrics,.grid,.filters,.profilegrid,.formgrid{grid-template-columns:minmax(0,1fr)!important}
 .candidate{grid-template-columns:44px minmax(0,1fr)!important;gap:10px!important}
 .candidate .actions,.candidate .score{grid-column:2!important;justify-self:start!important}
 .jobrow{grid-template-columns:minmax(0,1fr) auto!important;gap:8px!important}
 .jobrow .count:last-child{display:none!important}
 .toolbar{flex-wrap:wrap!important}
 .toolbar>*{min-width:0!important;max-width:100%!important}
 [data-testid="stMetric"]{padding:12px!important}
 h1{font-size:clamp(26px,7vw,36px)!important;overflow-wrap:anywhere}
 h2{font-size:clamp(22px,6vw,30px)!important}
 h3{font-size:clamp(18px,5vw,24px)!important}
}
@media (max-width: 420px){
 .stApp .stAppViewContainer .main .block-container,[data-testid="stMainBlockContainer"]{padding-left:9px!important;padding-right:9px!important}
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"]{gap:6px!important}
 .stApp .st-key-auth_landing_nav [data-testid="column"]{flex-basis:calc(50% - 6px)!important}
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(1),
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(5),
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(8){flex-basis:100%!important}
 .naukri-login-benefits{padding:22px 16px!important}
 .stApp [data-testid="stForm"]{padding:18px 14px!important}
}
</style>
""", unsafe_allow_html=True)

if header_profile_picture:
    _header_photo_url = header_profile_picture
    if not _header_photo_url.startswith("data:image/"):
        _header_photo_url = "data:image/jpeg;base64," + _header_photo_url
    _header_photo_url = _header_photo_url.replace("\\", "\\\\").replace("'", "\\'")
    st.markdown(
        "<style>.stApp .st-key-candidate_nav_actions .st-key-profile_pill_shell [class*='st-key-top_nav_profile'] button::after{"
        "content:''!important;background-image:url('" + _header_photo_url + "')!important;"
        "background-size:cover!important;background-position:center!important;"
        "border-radius:50%!important;border:2px solid #fff!important;"
        "box-shadow:0 0 0 1px #dce4ff!important;}</style>",
        unsafe_allow_html=True,
    )

def load_jobs():
    """Prefer live database jobs and keep only CSV jobs not yet migrated."""
    columns = ["Job ID", "Job Title", "Department", "Description", "Required Skills",
               "Minimum Budget", "Maximum Budget", "Work Mode", "Timezone", "Posted On", "Company Name"]
    try:
        legacy = pd.read_csv(JOBS_FILE).fillna("") if JOBS_FILE.exists() else pd.DataFrame(columns=columns)
        if "Status" in legacy.columns:
            legacy = legacy[legacy["Status"].astype(str).str.lower().isin(["active", "open", "published", ""])]
    except Exception:
        legacy = pd.DataFrame(columns=columns)
    database_jobs, _ = api_request("GET", "/jobs")
    if not isinstance(database_jobs, list) or not database_jobs:
        return legacy
    database_rows = []
    database_keys = set()
    for job in database_jobs:
        title = str(job.get("title") or "").strip()
        department = str(job.get("department") or "Other").strip()
        database_keys.add((title.casefold(), department.casefold()))
        database_rows.append({
            "Job ID": str(job.get("id", "")),
            "Job Title": title,
            "Department": department,
            "Description": str(job.get("description") or ""),
            "Required Skills": str(job.get("required_skills") or ""),
            "Minimum Budget": job.get("min_budget", 0),
            "Maximum Budget": job.get("max_budget", 0),
            "Work Mode": str(job.get("work_mode") or "Remote"),
            "Timezone": str(job.get("timezone") or "Asia/Kolkata"),
            "Posted On": str(job.get("created_at") or "")[:10],
            "Company Name": str(job.get("company_name") or "Company"),
        })
    if not legacy.empty:
        title_col = next((x for x in legacy.columns if str(x).strip().lower() in {"job title", "title", "job_title"}), None)
        dept_col = next((x for x in legacy.columns if str(x).strip().lower() in {"department", "team"}), None)
        if title_col:
            keep = []
            for _, row in legacy.iterrows():
                key = (str(row.get(title_col, "")).strip().casefold(),
                       str(row.get(dept_col, "Other") if dept_col else "Other").strip().casefold())
                keep.append(key not in database_keys)
            legacy = legacy.loc[keep]
    combined = pd.concat([pd.DataFrame(database_rows, columns=columns), legacy], ignore_index=True)
    return combined.fillna("")

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
    st.session_state.view = "candidate_auth"
if st.query_params.get("view") == "employee":
    st.session_state.view = "employee"

# Sidebar navigation removed: candidate navigation is now in the top bar and footer.
view = st.session_state.view

# Persistent in-app back navigation: keep users inside Instant Employee AI.
BACK_TARGETS = {
    "home": "home",
    "all_jobs": "home",
    "job_details": "all_jobs",
    "candidate_auth": "home",
    "candidate_dashboard": "home",
    "applied_jobs": "candidate_dashboard",
    "apply_resume": "all_jobs",
    "candidate": "home",
    "employee": "home",
}
if view not in ("home", "candidate_auth"):
    with st.container(key="global_back_navigation"):
        back_col, _back_spacer = st.columns([0.16, 4.84], gap="small")
        with back_col:
            if st.button("←", key="global_page_back", help="Back to the previous section", use_container_width=True):
                st.session_state.view = BACK_TARGETS.get(st.session_state.get("view", "home"), "home")
                st.rerun()

if view == "candidate_auth":
    with st.container(key="auth_landing_nav"):
        auth_logo, auth_jobs, auth_companies, auth_services, auth_search, auth_login, auth_register, auth_employers = st.columns(
            [1.45, .45, .72, .62, 1.25, .48, .55, .85], gap="small", vertical_alignment="center", wrap=False
        )
        with auth_logo:
            st.markdown("<div class='auth-brand'><span class='auth-brand-mark'>◀</span><span><b>Instant</b> Employee</span></div>", unsafe_allow_html=True)
        with auth_jobs:
            if st.button("Jobs", key="auth_nav_jobs", use_container_width=True):
                st.session_state.view = "all_jobs"; st.rerun()
        with auth_companies:
            if st.button("Companies", key="auth_nav_companies", use_container_width=True):
                st.session_state.view = "all_jobs"; st.rerun()
        with auth_services:
            if st.button("Services", key="auth_nav_services", use_container_width=True):
                st.session_state.view = "all_jobs"; st.rerun()
        with auth_search:
            st.text_input("Search jobs", placeholder="Search jobs here", key="auth_header_search", label_visibility="collapsed")
        with auth_login:
            if st.button("Login", key="auth_nav_login", use_container_width=True):
                st.session_state.candidate_auth_mode = "login"; st.session_state.candidate_auth_mode_selector = "Login"; st.rerun()
        with auth_register:
            if st.button("Register", key="auth_nav_register", use_container_width=True):
                st.session_state.candidate_auth_mode = "register"; st.session_state.candidate_auth_mode_selector = "Register"; st.rerun()
        with auth_employers:
            if st.button("For employers  ⌄", key="auth_nav_employers", use_container_width=True):
                st.session_state.view = "employee"; st.rerun()

if view == "home":
    # Campus-style compact header; back control stays outside the header above it.
    with st.container(key="candidate_top_nav"):
        nav_logo, nav_prepare, nav_participate, nav_opportunities, nav_search, nav_profile_link = st.columns(
            [1.65, 0.68, 0.86, 0.95, 1.55, 0.58], gap="small", vertical_alignment="center", wrap=False
        )
        with nav_logo:
            st.markdown("<div class='candidate-nav-brand'><span class='candidate-nav-mark'>✦</span><span><span class='candidate-nav-blue'>Instant</span><span class='candidate-nav-orange'> Employee</span></span></div>", unsafe_allow_html=True)
        with nav_prepare:
            if st.button("Prepare", key="top_nav_prepare", use_container_width=True):
                st.session_state.view = "candidate_dashboard" if st.session_state.get("candidate_logged_in") else "candidate_auth"
                st.rerun()
        with nav_participate:
            if st.button("Participate", key="top_nav_participate", use_container_width=True):
                st.session_state.view = "candidate_dashboard" if st.session_state.get("candidate_logged_in") else "candidate_auth"
                st.rerun()
        with nav_opportunities:
            if st.button("Opportunities", key="top_nav_opportunities", use_container_width=True):
                st.session_state.view = "all_jobs"; st.rerun()
        with nav_search:
            st.text_input("Search jobs", placeholder="Search jobs here", key="campus_header_search", label_visibility="collapsed")
        with nav_profile_link:
            if st.button("My Profile", key="top_nav_my_profile", help="Open your candidate profile", use_container_width=True):
                st.session_state.view = "candidate_dashboard" if st.session_state.get("candidate_logged_in") else "candidate_auth"
                st.rerun()


    st.markdown("""
    <div class="landing-hero">
      <div>
        <div class="eyebrow">BUILD YOUR TEAM WITH VERIFIED TALENT</div>
        <h1>Build Your Global Team with <span>Verified Talent</span></h1>
        <p>Hire skilled virtual IT and tech professionals for your startup or business. Discover relevant opportunities, manage hiring in one place, and find the right fit with AI-assisted matching.</p>
        <div class="landing-trust"><span>✓ Verified talent workflows</span><span>♙ Secure & confidential</span><span>◎ Flexible hiring</span><span>✦ AI-assisted matching</span></div>
      </div>
      <div class="landing-visual">
        <div class="landing-visual-card">✦ AI Matching <small>Skills, role and experience signals</small></div>
        <div class="landing-visual-card">✓ Talent-first hiring <small>Profiles, applications and shortlist workflows</small></div>
        <div class="landing-visual-card">🌐 Global reach <small>Remote, hybrid and timezone-aware roles</small></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    role_company, role_talent = st.columns(2, gap="large")
    with role_company:
        st.markdown('<div class="role-card"><div class="role-icon">▦</div><h3>For Companies</h3><p>Post roles, review applications, discover candidates and manage your hiring workflow from one workspace.</p></div>', unsafe_allow_html=True)
        if st.button("Company Dashboard  →", key="landing_company_login", type="primary", use_container_width=True):
            st.session_state.view = "employee"
            st.rerun()
    with role_talent:
        st.markdown('<div class="role-card talent"><div class="role-icon">♙</div><h3>For Talent</h3><p>Create your profile, upload your resume, find suitable jobs and track your applications.</p></div>', unsafe_allow_html=True)
        if st.button("Find Jobs  →", key="landing_find_jobs", use_container_width=True):
            st.session_state.view = "candidate_auth" if not st.session_state.get("candidate_logged_in") else "candidate_dashboard"
            st.rerun()

    st.markdown("### Everything you need to hire and grow")
    feature_columns = st.columns(4, gap="medium")
    landing_features = [
        ("✦", "AI-assisted matching", "Find relevant jobs and candidates using skills and role details."),
        ("▤", "Simple job posting", "Create roles with requirements, budgets and work modes."),
        ("☏", "Clear workflows", "Keep profiles, applications and hiring progress organized."),
        ("♧", "Built for trust", "Separate company and talent access with authenticated workflows."),
    ]
    for feature_col, (symbol, title, description) in zip(feature_columns, landing_features):
        with feature_col:
            st.markdown(f'<div class="feature-card"><div style="font-size:23px;color:#1764ff">{symbol}</div><b>{title}</b><small>{description}</small></div>', unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # Job search controls remain visible on the home page.
    st.markdown("### Find your next role")
    search_col, dept_col, mode_col = st.columns([2, 1, 1])
    with search_col:
        st.text_input("Search jobs", placeholder="Job title, skill, or keyword", key="home_job_search")
    title_col = next((c for c in jobs.columns if str(c).strip().lower() in {"job title", "title", "job_title"}), None)
    desc_col = next((c for c in jobs.columns if str(c).strip().lower() in {"description", "job description", "job_description"}), None)
    skills_col = next((c for c in jobs.columns if str(c).strip().lower() in {"required skills", "required_skills", "skills"}), None)
    dept_col_name = next((c for c in jobs.columns if str(c).strip().lower() in {"department", "category", "job category"}), None)
    work_mode_col = next((c for c in jobs.columns if str(c).strip().lower() in {"work mode", "work_mode", "mode"}), None)
    with dept_col:
        departments = sorted({str(x).strip() for x in jobs[dept_col_name].tolist() if str(x).strip()}) if dept_col_name and not jobs.empty else []
        st.selectbox("Category", ["All categories"] + departments, index=0, key="home_category_filter")
    with mode_col:
        modes = sorted({str(x).strip() for x in jobs[work_mode_col].tolist() if str(x).strip()}) if work_mode_col and not jobs.empty else []
        st.selectbox("Work mode", ["All modes"] + modes, index=0, key="home_work_mode_filter")
    available_jobs_col, _ = st.columns([1, 2])
    with available_jobs_col:
        st.metric("Available jobs", len(jobs))

    # Company cards always remain visible on the home page.
    company_col_name = next((col for col in jobs.columns if str(col).strip().lower() in {"company name", "company", "employer"}), None)
    employer_names = []
    if company_col_name and not jobs.empty:
        employer_names = sorted({
            str(value).strip() for value in jobs[company_col_name].tolist()
            if str(value).strip() and str(value).strip().lower() not in {"company", "nan", "none"}
            and "@" not in str(value)
        })
    st.markdown('<div class="market-section-heading"><h3>Explore jobs by top companies</h3></div>', unsafe_allow_html=True)
    if employer_names:
        showcase = [{"name": name, "count": int((jobs[company_col_name].astype(str).str.strip() == name).sum()), "demo": False} for name in employer_names[:4]]
    else:
        showcase = [
            {"name": "TCS", "count": 8, "demo": True},
            {"name": "Infosys", "count": 6, "demo": True},
            {"name": "Wipro", "count": 5, "demo": True},
            {"name": "HCLTech", "count": 4, "demo": True},
        ]
    with st.container(key="company_showcase_grid"):
        company_cards = st.columns(4, gap="small")
        for company_index, company in enumerate(showcase):
            company_name = company["name"]
            with company_cards[company_index]:
                brand_marks = {
                    "TCS": '<span class="brand-mark brand-tcs">TCS</span>',
                    "Infosys": '<span class="brand-mark brand-infosys">Infosys</span>',
                    "Wipro": '<span class="brand-mark brand-wipro">wipro</span>',
                    "HCLTech": '<span class="brand-mark brand-hcl">HCLTech</span>',
                }
                logo_html = brand_marks.get(company_name, f'<span class="brand-mark brand-generic">{html.escape(company_name[:2].upper())}</span>')
                st.markdown(f"""
                <div class="company-job-card">
                  <div class="company-logo-wrap">{logo_html}</div>
                  <div class="company-job-name">{html.escape(company_name)}</div>
                  <div class="company-job-count">{company["count"]} open jobs</div>
                  {('<div class="company-demo-note">Example</div>' if company.get("demo") else '')}
                </div>
                """, unsafe_allow_html=True)
                if st.button("View jobs  →", key=f"company_jobs_{company_index}", use_container_width=True):
                    st.session_state["all_jobs_company_filter"] = company_name if not company.get("demo") else "All companies"
                    st.session_state.view = "all_jobs"
                    st.rerun()

    # Show a few recent opportunities on the home page.
    st.markdown("### Recent jobs")
    st.caption("A preview of the latest opportunities. Select View all to browse every available job.")
    if jobs.empty:
        st.info("No jobs are available right now. Please check again after companies post new roles.")
    else:
        recent_jobs = jobs.head(3)
        recent_cols = st.columns(3, gap="medium")
        for rec_index, (row_index, rec_job) in enumerate(recent_jobs.iterrows()):
            rec_title = str(rec_job.get(title_col, "Open role")) if title_col else "Open role"
            rec_company = str(rec_job.get(company_col_name, "")).strip() if company_col_name else ""
            if "@" in rec_company:
                rec_company = "Hiring team"
            rec_mode = str(rec_job.get(work_mode_col, "Remote")) if work_mode_col else "Remote"
            with recent_cols[rec_index]:
                st.markdown(f"""
                <div class="recommended-job-card">
                  <div class="recommended-job-logo">{html.escape((rec_company[:1] or rec_title[:1]).upper())}</div>
                  <div class="recommended-job-age">Recently added</div>
                  <div class="recommended-job-title">{html.escape(rec_title)}</div>
                  <div class="recommended-job-company">{html.escape(rec_company or "Instant Employee")}</div>
                  <div class="recommended-job-mode">⌖ {html.escape(rec_mode)}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("View job  →", key=f"recent_job_view_{rec_index}", use_container_width=True):
                    st.session_state.selected_job_index = row_index
                    st.session_state.view = "job_details"
                    st.rerun()
    view_all_col, _ = st.columns([1, 3])
    with view_all_col:
        if st.button("View all jobs  →", key="home_view_all_jobs", type="primary", use_container_width=True):
            st.session_state.view = "all_jobs"
            st.rerun()

    st.markdown("### How it works")
    columns = st.columns(4)
    steps = [("01", "Explore jobs", "Search roles and review job details."), ("02", "Create account", "Sign in when you are ready to apply."), ("03", "Upload resume", "Share a readable PDF resume."), ("04", "AI job matching", "Review relevant skills and match estimates.")]
    for box, (number, title, desc) in zip(columns, steps):
        with box:
            st.markdown(f"<div class='step'><div class='stepnum'>{number}</div><h4>{title}</h4><div class='smallmuted'>{desc}</div></div>", unsafe_allow_html=True)
    st.caption("Candidate accounts and the company workspace are separate.")

    # Site footer directly below the homepage content, modeled on the user's reference.
    st.markdown("""
    <footer class="candidate-site-footer">
      <div class="candidate-footer-grid">
        <div>
          <div class="candidate-footer-brand"><span class="candidate-footer-mark">✦</span><span>Instant Employee</span></div>
          <div class="candidate-footer-title">Connect with us</div>
          <div class="candidate-footer-social">
            <a href="https://www.facebook.com/" target="_blank" aria-label="Facebook">f</a>
            <a href="https://www.instagram.com/" target="_blank" aria-label="Instagram">◎</a>
            <a href="https://www.linkedin.com/" target="_blank" aria-label="LinkedIn">in</a>
            <a href="https://x.com/" target="_blank" aria-label="X">𝕏</a>
          </div>
        </div>
        <div class="candidate-footer-links">
          <a href="#about">About us</a>
          <a href="#careers">Careers</a>
          <a href="?view=employee">Employee Login</a>
          <a href="#sitemap">Sitemap</a>
          <a href="#credits">Credits</a>
        </div>
        <div class="candidate-footer-links">
          <a href="#help">Help center</a>
          <a href="#notices">Announcements / Notices</a>
          <a href="#grievances">Grievances</a>
          <a href="#report-issue">Report issue</a>
        </div>
        <div class="candidate-footer-links">
          <a href="#privacy">Privacy policy</a>
          <a href="#terms">Terms &amp; conditions</a>
          <a href="#fraud-alert">Fraud alert</a>
          <a href="#trust-safety">Trust &amp; safety</a>
        </div>
      </div>
      <div class="candidate-footer-bottom">© 2026 Instant Employee AI · AI-powered talent platform</div>
    </footer>
    """, unsafe_allow_html=True)

elif view == "all_jobs":
    st.markdown("## All available jobs")
    st.caption(f"Browse and filter all {len(jobs)} job listings currently available on Instant Employee.")
    if st.button("← Back to home", key="all_jobs_back"):
        st.session_state.view = "home"
        st.rerun()

    all_title_col = next((c for c in jobs.columns if str(c).strip().lower() in {"job title", "title", "job_title"}), None)
    all_desc_col = next((c for c in jobs.columns if str(c).strip().lower() in {"description", "job description", "job_description"}), None)
    all_skills_col = next((c for c in jobs.columns if str(c).strip().lower() in {"required skills", "required_skills", "skills"}), None)
    all_dept_col = next((c for c in jobs.columns if str(c).strip().lower() in {"department", "category", "job category"}), None)
    all_mode_col = next((c for c in jobs.columns if str(c).strip().lower() in {"work mode", "work_mode", "mode"}), None)
    all_company_col = next((c for c in jobs.columns if str(c).strip().lower() in {"company name", "company", "employer"}), None)
    all_low_col = next((c for c in jobs.columns if str(c).strip().lower() in {"minimum budget", "min budget", "minimum_budget"}), None)
    all_high_col = next((c for c in jobs.columns if str(c).strip().lower() in {"maximum budget", "max budget", "maximum_budget"}), None)

    filter_search, filter_category, filter_mode = st.columns([2, 1, 1])
    with filter_search:
        all_search = st.text_input("Search all jobs", placeholder="Job title, skill, or keyword", key="all_jobs_search")
    all_departments = sorted({str(x).strip() for x in jobs[all_dept_col].tolist() if str(x).strip()}) if all_dept_col and not jobs.empty else []
    all_modes = sorted({str(x).strip() for x in jobs[all_mode_col].tolist() if str(x).strip()}) if all_mode_col and not jobs.empty else []
    with filter_category:
        all_selected_department = st.selectbox("Category", ["All categories"] + all_departments, key="all_jobs_category")
    with filter_mode:
        all_selected_mode = st.selectbox("Work mode", ["All modes"] + all_modes, key="all_jobs_mode")

    filtered_all_jobs = jobs.copy()
    selected_company = st.session_state.get("all_jobs_company_filter", "All companies")
    if selected_company != "All companies" and all_company_col and not filtered_all_jobs.empty:
        filtered_all_jobs = filtered_all_jobs[filtered_all_jobs[all_company_col].astype(str).str.strip() == selected_company]
        st.caption(f"Showing jobs from {selected_company}.")
        if st.button("Show jobs from all companies", key="all_jobs_clear_company"):
            st.session_state["all_jobs_company_filter"] = "All companies"
            st.rerun()
    if all_search.strip() and not filtered_all_jobs.empty:
        searchable_cols = [c for c in [all_title_col, all_desc_col, all_skills_col, all_dept_col] if c]
        if searchable_cols:
            terms = [term.casefold() for term in all_search.split() if term]
            searchable_text = filtered_all_jobs[searchable_cols].astype(str).apply(lambda row: " ".join(row.values), axis=1)
            filtered_all_jobs = filtered_all_jobs[searchable_text.apply(lambda value: all(term in value.casefold() for term in terms))]
    if all_selected_department != "All categories" and all_dept_col:
        filtered_all_jobs = filtered_all_jobs[filtered_all_jobs[all_dept_col].astype(str).str.casefold() == all_selected_department.casefold()]
    if all_selected_mode != "All modes" and all_mode_col:
        filtered_all_jobs = filtered_all_jobs[filtered_all_jobs[all_mode_col].astype(str).str.casefold() == all_selected_mode.casefold()]

    st.markdown(f"### Showing {len(filtered_all_jobs)} jobs")
    if filtered_all_jobs.empty:
        st.info("No jobs match these filters. Try a different keyword or reset the filters.")
    else:
        all_job_grid = st.columns(3, gap="medium")
        for display_index, (row_index, job) in enumerate(filtered_all_jobs.iterrows()):
            with all_job_grid[display_index % 3]:
                all_title = str(job.get(all_title_col, "Open role")) if all_title_col else "Open role"
                all_department = str(job.get(all_dept_col, "Technology")) if all_dept_col else "Technology"
                all_description = str(job.get(all_desc_col, "")) if all_desc_col else ""
                all_skills = str(job.get(all_skills_col, "Skills listed in job description")) if all_skills_col else "Skills listed in job description"
                all_mode_value = str(job.get(all_mode_col, "Not specified")) if all_mode_col else "Not specified"
                all_low = str(job.get(all_low_col, "")) if all_low_col else ""
                all_high = str(job.get(all_high_col, "")) if all_high_col else ""
                all_budget = f"₹{all_low or '—'} – ₹{all_high or '—'}" if all_low or all_high else "Budget discussed"
                short_desc = all_description[:105] + ("…" if len(all_description) > 105 else "")
                short_skills = all_skills[:75] + ("…" if len(all_skills) > 75 else "")
                st.markdown(f"""
                <div class="jobcard job-tile">
                  <div class="job-tile-head"><div class="job-tile-logo">✦</div><span class="job-mode-pill">{html.escape(all_mode_value)}</span></div>
                  <div class="job-tile-department">{html.escape(all_department)}</div>
                  <h3 class="job-tile-title">{html.escape(all_title)}</h3>
                  <p class="job-tile-description">{html.escape(short_desc or "Open this role to view the complete job description.")}</p>
                  <div class="job-tile-skills"><b>Skills</b><br>{html.escape(short_skills)}</div>
                  <div class="job-tile-budget">{html.escape(all_budget)}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("View details", key=f"all_jobs_view_{row_index}", use_container_width=True):
                    st.session_state.selected_job_index = row_index
                    st.session_state.view = "job_details"
                    st.rerun()
                if st.button("Apply now", key=f"all_jobs_apply_{row_index}", type="primary", use_container_width=True):
                    st.session_state.apply_job_index = row_index
                    st.session_state.pop("application_submitted", None)
                    st.session_state.view = "apply_resume" if st.session_state.get("candidate_logged_in") else "candidate_auth"
                    st.rerun()

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
    # Keep the login/register view compact like the supplied reference page.
    auth_mode = "Register" if st.session_state.get("candidate_auth_mode") == "register" else "Login"
    if auth_mode == "Login":
        feature_col, form_col = st.columns([1.12, 0.88], gap="small")
        with feature_col:
            st.markdown(
                "<div class='naukri-login-benefits'><h3>New to Instant Employee?</h3>"
                "<div class='benefit-row'><span>✓</span>One click apply using your candidate profile.</div>"
                "<div class='benefit-row'><span>✓</span>Get relevant job recommendations.</div>"
                "<div class='benefit-row'><span>✓</span>Showcase your profile to top companies.</div>"
                "<div class='benefit-row'><span>✓</span>Track application status in one place.</div>"
                "<div class='benefit-illustration'>✦ <b>Build your career with verified opportunities</b></div></div>",
                unsafe_allow_html=True,
            )
            if st.button("Register for Free", key="auth_benefits_register", use_container_width=False):
                st.session_state.candidate_auth_mode = "register"; st.rerun()
        with form_col:
            st.markdown(
                "<div class='candidate-auth-heading'><div class='candidate-auth-icon'>♙</div><div>"
                "<h3>Login</h3></div></div>",
                unsafe_allow_html=True,
            )
            with st.form("candidate_login"):
                email = st.text_input("Email address", key="candidate_login_email", placeholder="Enter your email address")
                password = st.text_input("Password", type="password", key="candidate_login_password", placeholder="Enter your password")
                submit = st.form_submit_button("Login to Dashboard  →", type="primary", use_container_width=True)
            st.markdown("<div class='candidate-auth-note'>♢  Your candidate account keeps your profile and applications in one place.</div>", unsafe_allow_html=True)
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
                        st.session_state.view = "apply_resume" if st.session_state.get("apply_job_index") is not None else "home"
                        st.rerun()
    else:
        form_col, feature_col = st.columns([1.05, 0.95], gap="large")
        with form_col:
            st.markdown(
                "<div class='candidate-auth-heading'><div class='candidate-auth-icon candidate-signup-icon'>✦</div><div>"
                "<h3>Create your account</h3><p>Set up your candidate profile to start exploring opportunities.</p></div></div>",
                unsafe_allow_html=True,
            )
            with st.form("candidate_signup"):
                name = st.text_input("Full name", key="candidate_signup_name", placeholder="Enter your full name")
                email = st.text_input("Email address", key="candidate_signup_email", placeholder="Enter your email address")
                password = st.text_input("Create password", type="password", key="candidate_signup_password", placeholder="At least 8 characters")
                confirm = st.text_input("Confirm password", type="password", key="candidate_signup_confirm", placeholder="Re-enter your password")
                submit = st.form_submit_button("✦  Create candidate account", type="primary", use_container_width=True)
            st.markdown("<div class='candidate-auth-note'>♢  Use a strong password and keep your account details private.</div>", unsafe_allow_html=True)
        with feature_col:
            st.markdown(
                "<div class='candidate-auth-feature'><div class='kicker'>A PROFILE THAT WORKS FOR YOU</div>"
                "<h2>Showcase your <span>potential.</span></h2>"
                "<p>A simple candidate workspace designed to keep your job search organized.</p>"
                "<div class='candidate-feature-row'><span class='candidate-feature-icon cfi-blue'>♙</span><div><b>Your profile</b><small>Keep your candidate details up to date.</small></div></div>"
                "<div class='candidate-feature-row'><span class='candidate-feature-icon cfi-green'>▤</span><div><b>Your resume</b><small>Upload and manage your resume from My Profile.</small></div></div>"
                "<div class='candidate-feature-row'><span class='candidate-feature-icon cfi-amber'>✓</span><div><b>Your applications</b><small>Keep track of the roles you apply for.</small></div></div>"
                "<div class='candidate-feature-foot'>✦  One account for your job search</div></div>",
                unsafe_allow_html=True,
            )
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
            saved_profile, saved_profile_error = api_request(
                "GET", "/profiles/me", token=st.session_state.get("candidate_api_token")
            )
            saved_resume = (saved_profile or {}).get("resume_filename", "")
            if saved_profile_error:
                st.error("Could not check your saved profile resume: " + saved_profile_error)
            elif not (saved_profile or {}).get("resume_text"):
                st.warning("Upload your resume once in My Profile. After that, you can apply to jobs without uploading it again.")
                if st.button("Open My Profile to Upload Resume", type="primary", use_container_width=True):
                    st.session_state.view = "candidate_dashboard"
                    st.rerun()
            else:
                st.success("Using your saved profile resume: " + html.escape(saved_resume or "Saved PDF"))
                with st.form("submit_job_application"):
                    submit_application = st.form_submit_button("Apply with Saved Resume", type="primary", use_container_width=True)
                if submit_application:
                    title_col = next((c for c in jobs.columns if str(c).strip().lower() in {"job title", "title", "job_title"}), None)
                    company_col = next((c for c in jobs.columns if str(c).strip().lower() in {"company", "company name", "employer"}), None)
                    job_id_col = next((c for c in jobs.columns if str(c).strip().lower() in {"job id", "job_id", "id"}), None)
                    job_record_id = str(selected_job.get(job_id_col, selected_index)) if job_id_col else str(selected_index)
                    company_name = str(selected_job.get(company_col, "Company not specified")) if company_col else "Company not specified"
                    if job_record_id.isdigit():
                        application_data, application_error = api_request(
                            "POST", f"/jobs/{int(job_record_id)}/apply",
                            token=st.session_state.get("candidate_api_token"), json={}
                        )
                    else:
                        application_data, application_error = api_request(
                            "POST", "/applications/external",
                            token=st.session_state.get("candidate_api_token"),
                            json={"job_key": job_record_id, "job_title": apply_title, "company_name": company_name, "resume_filename": saved_resume},
                        )
                    if application_error:
                        if "Already applied to this job" in application_error:
                            st.info("You have already applied to this job from this account. It is listed in Applied Jobs.")
                        else:
                            st.error("The application could not be saved to the database: " + application_error)
                    else:
                        st.session_state.application_resume_name = saved_resume
                        st.session_state.application_submitted = True
                        st.success("✓ Application submitted using your saved profile resume.")
                        st.rerun()
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
        token = st.session_state.get("candidate_api_token")
        applications, applications_error = get_candidate_applications(token)
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
            st.error("The profile could not be loaded: " + profile_error)
            profile = {
                "full_name": st.session_state.get("candidate_name", ""),
                "headline": "", "skills": "", "timezone": "Asia/Kolkata",
                "availability": "Available", "portfolio_url": "", "resume_filename": "",
                "completion_percent": 0,
            }

        st.caption("Welcome back, " + st.session_state.get("candidate_name", "Candidate") + ". Your profile details are saved to the backend.")
        # Preview the newly selected photo immediately; save it with the profile form.
        profile_picture = None
        display_picture_data = profile.get("picture_data", "") or ""
        st.markdown("""
        <style>
        [class*="st-key-profile_avatar"] {position:relative; min-height:142px;}
        [class*="st-key-profile_avatar"] [data-testid="stFileUploader"] {
            position:absolute; top:76px; left:72px; width:42px; height:42px;
            margin:0; z-index:5;
        }
        [class*="st-key-profile_avatar"] [data-testid="stFileUploader"] section {
            width:42px!important; min-width:42px!important; height:42px!important;
            min-height:42px!important; padding:0!important; border:2px solid #070d18!important;
            border-radius:50%!important; background:#1764ff!important; overflow:hidden!important;
        }
        [class*="st-key-profile_avatar"] [data-testid="stFileUploader"] section > div,
        [class*="st-key-profile_avatar"] [data-testid="stFileUploader"] small,
        [class*="st-key-profile_avatar"] [data-testid="stFileUploader"] button {
            display:none!important;
        }
        [class*="st-key-profile_avatar"] [data-testid="stFileUploader"] section::after {
            content:"📷"; display:flex; align-items:center; justify-content:center;
            width:38px; height:38px; font-size:18px; position:absolute; inset:0;
        }
        [class*="st-key-profile_avatar"] [data-testid="stFileUploader"] section {cursor:pointer;}
        /* Force the profile/menu pill to stay visibly highlighted (override global button rules) */
div.st-key-candidate_top_nav div[data-testid="column"]:nth-child(8) div[data-testid="stButton"] > button,
div.st-key-candidate_top_nav div[data-testid="column"]:nth-child(8) div[data-testid="stButton"] > button:hover,
div.st-key-candidate_top_nav div[data-testid="column"]:nth-child(8) div[data-testid="stButton"] > button:focus,
div.st-key-candidate_top_nav div[data-testid="column"]:nth-child(8) div[data-testid="stButton"] > button:active {
    display:flex!important;
    align-items:center!important;
    justify-content:space-between!important;
    box-sizing:border-box!important;
    width:150px!important;
    min-width:150px!important;
    max-width:150px!important;
    height:53px!important;
    min-height:53px!important;
    padding:0 10px!important;
    border:1px solid #d8e2ff!important;
    border-radius:29px!important;
    background:#f2f6ff!important;
    box-shadow:0 0 0 1px #edf2ff inset!important;
    color:#8b9abc!important;
    overflow:visible!important;
}
div.st-key-candidate_top_nav div[data-testid="column"]:nth-child(8) div[data-testid="stButton"] > button::before {
    content:""!important;
    position:absolute!important;
    left:52px!important;
    top:17px!important;
    width:18px!important;
    height:18px!important;
    background-repeat:no-repeat!important;
    background-position:center!important;
    background-size:contain!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 20 20' fill='none'%3E%3Cpath d='M3 5h14M3 10h14M3 15h14' stroke='%238b9abc' stroke-width='1.7' stroke-linecap='round'/%3E%3C/svg%3E")!important;
}
/* Direct key-based styling: the profile pill stays highlighted without hover */
.stApp [class*="st-key-top_nav_profile"] button,
.stApp [class*="st-key-top_nav_profile"] button:hover,
.stApp [class*="st-key-top_nav_profile"] button:focus,
.stApp [class*="st-key-top_nav_profile"] button:active {
    position:relative!important;
    display:flex!important;
    align-items:center!important;
    justify-content:flex-start!important;
    box-sizing:border-box!important;
    width:150px!important;
    min-width:150px!important;
    max-width:160px!important;
    height:53px!important;
    min-height:53px!important;
    padding:0!important;
    border:1px solid #d8e2ff!important;
    border-radius:29px!important;
    background-color:#f2f6ff!important;
    background-image:none!important;
    box-shadow:0 0 0 1px #edf2ff inset!important;
    color:transparent!important;
    -webkit-text-fill-color:transparent!important;
    font-size:0!important;
    outline:none!important;
}
.stApp [class*="st-key-top_nav_profile"] button::before {
    content:""!important;
    position:absolute!important;
    left:52px!important;
    top:17px!important;
    width:18px!important;
    height:18px!important;
    background-repeat:no-repeat!important;
    background-position:center!important;
    background-size:contain!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 20 20' fill='none'%3E%3Cpath d='M3 5h14M3 10h14M3 15h14' stroke='%238b9abc' stroke-width='1.7' stroke-linecap='round'/%3E%3C/svg%3E")!important;
}
.stApp [class*="st-key-top_nav_profile"] button::after {
    content:""!important;
    position:absolute!important;
    right:10px!important;
    top:10px!important;
    width:32px!important;
    height:32px!important;
    border-radius:50%!important;
    background-repeat:no-repeat!important;
    background-position:center!important;
    background-size:32px 32px!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'%3E%3Cdefs%3E%3CclipPath id='c'%3E%3Ccircle cx='16' cy='16' r='15'/%3E%3C/clipPath%3E%3C/defs%3E%3Cg clip-path='url(%23c)'%3E%3Crect width='32' height='32' fill='%23e9d6c7'/%3E%3Cpath d='M1 32c1-8 6-12 15-12s14 4 15 12' fill='%234a6a8d'/%3E%3Ccircle cx='16' cy='12' r='6' fill='%23f1c9ad'/%3E%3Cpath d='M9 12c0-7 3-10 8-9 5 1 7 5 6 10l-2-4c-4 1-7-1-9-3l-3 6Z' fill='%234a342e'/%3E%3C/g%3E%3Ccircle cx='16' cy='16' r='15' fill='none' stroke='%23e2e6ef'/%3E%3C/svg%3E")!important;
}

/* Profile pill shell is a real Streamlit container, so its highlight is always visible */
.stApp .st-key-profile_pill_shell{
    width:160px!important;
    min-width:160px!important;
    max-width:160px!important;
    height:53px!important;
    min-height:53px!important;
    box-sizing:border-box!important;
    display:flex!important;
    align-items:center!important;
    justify-content:center!important;
    padding:0!important;
    margin:0!important;
    border:1px solid #d8e2ff!important;
    border-radius:29px!important;
    background:#f2f6ff!important;
    overflow:visible!important;
}
.stApp .st-key-profile_pill_shell [data-testid="stButton"]{
    width:100%!important;
    margin:0!important;
    padding:0!important;
}
.stApp .st-key-profile_pill_shell [data-testid="stButton"] button,
.stApp .st-key-profile_pill_shell [data-testid="stButton"] button:hover,
.stApp .st-key-profile_pill_shell [data-testid="stButton"] button:focus,
.stApp .st-key-profile_pill_shell [data-testid="stButton"] button:active{
    position:relative!important;
    width:100%!important;
    min-width:100%!important;
    height:51px!important;
    min-height:51px!important;
    padding:0!important;
    border:0!important;
    border-radius:27px!important;
    background:transparent!important;
    background-image:none!important;
    box-shadow:none!important;
    color:transparent!important;
    -webkit-text-fill-color:transparent!important;
    font-size:0!important;
    outline:none!important;
}
.stApp .st-key-profile_pill_shell [data-testid="stButton"] button::before{
    content:""!important;
    position:absolute!important;
    left:58px!important;
    top:16px!important;
    width:18px!important;
    height:18px!important;
    background-repeat:no-repeat!important;
    background-position:center!important;
    background-size:contain!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 20 20' fill='none'%3E%3Cpath d='M3 5h14M3 10h14M3 15h14' stroke='%238b9abc' stroke-width='1.7' stroke-linecap='round'/%3E%3C/svg%3E")!important;
}
.stApp .st-key-profile_pill_shell [data-testid="stButton"] button::after{
    content:""!important;
    position:absolute!important;
    right:10px!important;
    top:9px!important;
    width:32px!important;
    height:32px!important;
    border-radius:50%!important;
    background-repeat:no-repeat!important;
    background-position:center!important;
    background-size:32px 32px!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'%3E%3Cdefs%3E%3CclipPath id='c'%3E%3Ccircle cx='16' cy='16' r='15'/%3E%3C/clipPath%3E%3C/defs%3E%3Cg clip-path='url(%23c)'%3E%3Crect width='32' height='32' fill='%23e9d6c7'/%3E%3Cpath d='M1 32c1-8 6-12 15-12s14 4 15 12' fill='%234a6a8d'/%3E%3Ccircle cx='16' cy='12' r='6' fill='%23f1c9ad'/%3E%3Cpath d='M9 12c0-7 3-10 8-9 5 1 7 5 6 10l-2-4c-4 1-7-1-9-3l-3 6Z' fill='%234a342e'/%3E%3C/g%3E%3Ccircle cx='16' cy='16' r='15' fill='none' stroke='%23e2e6ef'/%3E%3C/svg%3E")!important;
}

/* Keep notification and candidate profile physically adjacent in one actions group */
.stApp .st-key-candidate_nav_actions{
    width:200px!important;min-width:200px!important;max-width:200px!important;
    margin:0!important;padding:0!important;background:transparent!important;border:0!important;
}
.stApp .st-key-candidate_nav_actions [data-testid="stHorizontalBlock"]{
    display:flex!important;flex-flow:row nowrap!important;align-items:center!important;
    justify-content:flex-start!important;gap:4px!important;width:200px!important;min-width:200px!important;max-width:200px!important;margin:0!important;
}
.stApp .st-key-candidate_nav_actions [data-testid="column"]{min-width:0!important;flex-shrink:0!important;padding:0!important}
.stApp .st-key-candidate_nav_actions [data-testid="column"]:nth-child(1){flex:0 0 42px!important;width:42px!important;max-width:42px!important}
.stApp .st-key-candidate_nav_actions [data-testid="column"]:nth-child(2){flex:0 0 150px!important;width:150px!important;max-width:150px!important}
.stApp .st-key-candidate_nav_actions [class*="st-key-top_nav_alerts"] button,
.stApp .st-key-candidate_nav_actions [class*="st-key-top_nav_alerts"] button:hover,
.stApp .st-key-candidate_nav_actions [class*="st-key-top_nav_alerts"] button:focus{
    width:42px!important;min-width:42px!important;max-width:42px!important;height:48px!important;min-height:48px!important;
    padding:0!important;border:0!important;border-radius:50%!important;background:transparent!important;
    box-shadow:none!important;color:#7180a6!important;font-size:0!important;position:relative!important;
}
.stApp .st-key-candidate_nav_actions [class*="st-key-top_nav_alerts"] button::before{
    content:""!important;position:absolute!important;inset:8px 7px!important;
    background-repeat:no-repeat!important;background-position:center!important;background-size:contain!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='30' height='34' viewBox='0 0 30 34' fill='none'%3E%3Cpath d='M15 4.5c-5.1 0-8.1 3.9-8.1 9.1v4.1c0 1.9-.7 3.3-2 4.7L3 24.5c-.8 1-.2 2.1 1 2.1h22c1.2 0 1.8-1.1 1-2.1l-1.9-2.1c-1.3-1.4-2-2.8-2-4.7v-4.1c0-5.2-3-9.1-8.1-9.1Z' stroke='%23717FA6' stroke-width='1.45' stroke-linejoin='round'/%3E%3Cpath d='M11.5 29c.6 1.8 1.8 2.7 3.5 2.7s2.9-.9 3.5-2.7' stroke='%23717FA6' stroke-width='1.45' stroke-linecap='round'/%3E%3Cpath d='M13 3.2c.2-1 1-1.7 2-1.7s1.8.7 2 1.7' stroke='%23717FA6' stroke-width='1.45' stroke-linecap='round'/%3E%3C/svg%3E")!important;
}
.stApp .st-key-candidate_nav_actions [class*="st-key-top_nav_alerts"] button::after{
    content:"4"!important;position:absolute!important;right:0!important;top:0!important;width:19px!important;height:19px!important;
    border-radius:50%!important;display:flex!important;align-items:center!important;justify-content:center!important;
    background:#f04452!important;color:#fff!important;font:700 11px/1 Arial,sans-serif!important;border:2px solid #fff!important;
}
.stApp .st-key-candidate_nav_actions .st-key-profile_pill_shell{
    width:150px!important;min-width:150px!important;max-width:150px!important;
}

/* Final header controls styling by their actual nested column positions */
.stApp .st-key-candidate_nav_actions [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child [data-testid="stButton"] button,
.stApp .st-key-candidate_nav_actions [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child [data-testid="stButton"] button:hover,
.stApp .st-key-candidate_nav_actions [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child [data-testid="stButton"] button:focus {
    position:relative!important;width:42px!important;min-width:42px!important;height:48px!important;min-height:48px!important;
    padding:0!important;border:0!important;border-radius:50%!important;background:transparent!important;
    color:transparent!important;font-size:0!important;box-shadow:none!important;
}
.stApp .st-key-candidate_nav_actions [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child [data-testid="stButton"] button::before{
    content:""!important;position:absolute!important;inset:7px!important;background-repeat:no-repeat!important;
    background-position:center!important;background-size:contain!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='30' height='34' viewBox='0 0 30 34' fill='none'%3E%3Cpath d='M15 4.5c-5.1 0-8.1 3.9-8.1 9.1v4.1c0 1.9-.7 3.3-2 4.7L3 24.5c-.8 1-.2 2.1 1 2.1h22c1.2 0 1.8-1.1 1-2.1l-1.9-2.1c-1.3-1.4-2-2.8-2-4.7v-4.1c0-5.2-3-9.1-8.1-9.1Z' stroke='%23717FA6' stroke-width='1.45' stroke-linejoin='round'/%3E%3Cpath d='M11.5 29c.6 1.8 1.8 2.7 3.5 2.7s2.9-.9 3.5-2.7' stroke='%23717FA6' stroke-width='1.45' stroke-linecap='round'/%3E%3C/svg%3E")!important;
}
.stApp .st-key-candidate_nav_actions [data-testid="stHorizontalBlock"] > [data-testid="column"]:first-child [data-testid="stButton"] button::after{
    content:"4"!important;position:absolute!important;right:-1px!important;top:0!important;width:19px!important;height:19px!important;
    border-radius:50%!important;display:flex!important;align-items:center!important;justify-content:center!important;
    background:#f04452!important;color:#fff!important;font:700 11px/1 Arial,sans-serif!important;border:2px solid #fff!important;
}
.stApp .st-key-candidate_nav_actions [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) .st-key-profile_pill_shell{
    width:108px!important;min-width:108px!important;max-width:108px!important;height:53px!important;
    border:1px solid #e2e6ef!important;border-radius:29px!important;background:#fff!important;
    box-sizing:border-box!important;padding:0!important;overflow:visible!important;
}
.stApp .st-key-candidate_nav_actions [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) .st-key-profile_pill_shell [data-testid="stButton"] button,
.stApp .st-key-candidate_nav_actions [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) .st-key-profile_pill_shell [data-testid="stButton"] button:hover,
.stApp .st-key-candidate_nav_actions [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) .st-key-profile_pill_shell [data-testid="stButton"] button:focus {
    position:relative!important;width:106px!important;min-width:106px!important;height:51px!important;min-height:51px!important;
    padding:0!important;border:0!important;border-radius:27px!important;background:#fff!important;box-shadow:none!important;
    color:transparent!important;font-size:0!important;overflow:visible!important;
}
.stApp .st-key-candidate_nav_actions [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) .st-key-profile_pill_shell [data-testid="stButton"] button::before{
    content:""!important;position:absolute!important;left:14px!important;top:16px!important;width:24px!important;height:20px!important;
    background-repeat:no-repeat!important;background-position:center!important;background-size:contain!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='20' viewBox='0 0 24 20' fill='none'%3E%3Cpath d='M2 3h20M2 10h20M2 17h20' stroke='%238b9abc' stroke-width='1.8' stroke-linecap='round'/%3E%3C/svg%3E")!important;
}
.stApp .st-key-candidate_nav_actions [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-child(2) .st-key-profile_pill_shell [data-testid="stButton"] button::after{
    content:""!important;position:absolute!important;right:8px!important;top:9px!important;width:32px!important;height:32px!important;
    border-radius:50%!important;background-repeat:no-repeat!important;background-position:center!important;background-size:32px 32px!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'%3E%3Cdefs%3E%3CclipPath id='c'%3E%3Ccircle cx='16' cy='16' r='15'/%3E%3C/clipPath%3E%3C/defs%3E%3Cg clip-path='url(%23c)'%3E%3Crect width='32' height='32' fill='%23e9d6c7'/%3E%3Cpath d='M1 32c1-8 6-12 15-12s14 4 15 12' fill='%234a6a8d'/%3E%3Ccircle cx='16' cy='12' r='6' fill='%23f1c9ad'/%3E%3Cpath d='M9 12c0-7 3-10 8-9 5 1 7 5 6 10l-2-4c-4 1-7-1-9-3l-3 6Z' fill='%234a342e'/%3E%3C/g%3E%3Ccircle cx='16' cy='16' r='15' fill='none' stroke='%23e2e6ef'/%3E%3C/svg%3E")!important;
}

/* Notification must sit outside any visible box: target the button by its Streamlit key */
.stApp .st-key-top_nav_alerts,
.stApp .st-key-top_nav_alerts [data-testid="stButton"],
.stApp .st-key-top_nav_alerts [data-testid="stButton"] > div{
    width:42px!important;min-width:42px!important;max-width:42px!important;
    margin:0!important;padding:0!important;border:0!important;background:transparent!important;
    box-shadow:none!important;overflow:visible!important;
}
.stApp .st-key-top_nav_alerts [data-testid="stButton"] button,
.stApp .st-key-top_nav_alerts [data-testid="stButton"] button:hover,
.stApp .st-key-top_nav_alerts [data-testid="stButton"] button:focus,
.stApp .st-key-top_nav_alerts [data-testid="stButton"] button:active{
    position:relative!important;display:block!important;width:42px!important;min-width:42px!important;max-width:42px!important;
    height:48px!important;min-height:48px!important;padding:0!important;margin:0!important;
    border:0!important;border-radius:0!important;background:transparent!important;background-image:none!important;
    box-shadow:none!important;color:transparent!important;-webkit-text-fill-color:transparent!important;
    font-size:0!important;outline:none!important;
}
.stApp .st-key-top_nav_alerts [data-testid="stButton"] button::before{
    content:""!important;position:absolute!important;left:6px!important;top:7px!important;width:30px!important;height:34px!important;
    background:transparent!important;background-repeat:no-repeat!important;background-position:center!important;background-size:contain!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='30' height='34' viewBox='0 0 30 34' fill='none'%3E%3Cpath d='M15 4.5c-5.1 0-8.1 3.9-8.1 9.1v4.1c0 1.9-.7 3.3-2 4.7L3 24.5c-.8 1-.2 2.1 1 2.1h22c1.2 0 1.8-1.1 1-2.1l-1.9-2.1c-1.3-1.4-2-2.8-2-4.7v-4.1c0-5.2-3-9.1-8.1-9.1Z' stroke='%23717FA6' stroke-width='1.45' stroke-linejoin='round'/%3E%3Cpath d='M11.5 29c.6 1.8 1.8 2.7 3.5 2.7s2.9-.9 3.5-2.7' stroke='%23717FA6' stroke-width='1.45' stroke-linecap='round'/%3E%3Cpath d='M13 3.2c.2-1 1-1.7 2-1.7s1.8.7 2 1.7' stroke='%23717FA6' stroke-width='1.45' stroke-linecap='round'/%3E%3C/svg%3E")!important;
}
.stApp .st-key-top_nav_alerts [data-testid="stButton"] button::after{
    content:"4"!important;position:absolute!important;right:-1px!important;top:0!important;width:19px!important;height:19px!important;
    border-radius:50%!important;display:flex!important;align-items:center!important;justify-content:center!important;
    background:#f04452!important;color:#fff!important;-webkit-text-fill-color:#fff!important;
    font:700 11px/1 Arial,sans-serif!important;border:2px solid #fff!important;box-sizing:border-box!important;
}

/* Clean final controls: blank native labels, icons and badges are drawn in CSS */
.stApp div[class*="st-key-top_nav_alerts"] button,
.stApp div[class*="st-key-top_nav_alerts"] button:hover,
.stApp div[class*="st-key-top_nav_alerts"] button:focus,
.stApp div[class*="st-key-top_nav_alerts"] button:active{
    position:relative!important;display:block!important;box-sizing:border-box!important;
    width:42px!important;min-width:42px!important;max-width:42px!important;height:48px!important;min-height:48px!important;
    padding:0!important;margin:0!important;border:0!important;border-radius:0!important;
    background:transparent!important;box-shadow:none!important;font-size:0!important;color:transparent!important;
    -webkit-text-fill-color:transparent!important;outline:none!important;
}
.stApp div[class*="st-key-top_nav_alerts"] button::before{
    content:""!important;position:absolute!important;left:6px!important;top:7px!important;width:30px!important;height:34px!important;
    background:transparent no-repeat center/contain!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='30' height='34' viewBox='0 0 30 34' fill='none'%3E%3Cpath d='M15 4.5c-5.1 0-8.1 3.9-8.1 9.1v4.1c0 1.9-.7 3.3-2 4.7L3 24.5c-.8 1-.2 2.1 1 2.1h22c1.2 0 1.8-1.1 1-2.1l-1.9-2.1c-1.3-1.4-2-2.8-2-4.7v-4.1c0-5.2-3-9.1-8.1-9.1Z' stroke='%23717FA6' stroke-width='1.45' stroke-linejoin='round'/%3E%3Cpath d='M11.5 29c.6 1.8 1.8 2.7 3.5 2.7s2.9-.9 3.5-2.7' stroke='%23717FA6' stroke-width='1.45' stroke-linecap='round'/%3E%3Cpath d='M13 3.2c.2-1 1-1.7 2-1.7s1.8.7 2 1.7' stroke='%23717FA6' stroke-width='1.45' stroke-linecap='round'/%3E%3C/svg%3E")!important;
}
.stApp div[class*="st-key-top_nav_alerts"] button::after{
    content:"4"!important;position:absolute!important;right:-1px!important;top:0!important;width:19px!important;height:19px!important;
    border-radius:50%!important;display:flex!important;align-items:center!important;justify-content:center!important;
    background:#f04452!important;color:#fff!important;-webkit-text-fill-color:#fff!important;
    font:700 11px/1 Arial,sans-serif!important;border:2px solid #fff!important;box-sizing:border-box!important;
}
.stApp div[class*="st-key-profile_pill_shell"]{
    width:108px!important;min-width:108px!important;max-width:108px!important;height:53px!important;min-height:53px!important;
    border:1px solid #e2e6ef!important;border-radius:29px!important;background:#fff!important;
    box-sizing:border-box!important;padding:0!important;margin:0!important;overflow:visible!important;
}
.stApp div[class*="st-key-profile_pill_shell"] [data-testid="stButton"] button,
.stApp div[class*="st-key-profile_pill_shell"] [data-testid="stButton"] button:hover,
.stApp div[class*="st-key-profile_pill_shell"] [data-testid="stButton"] button:focus,
.stApp div[class*="st-key-profile_pill_shell"] [data-testid="stButton"] button:active{
    position:relative!important;display:block!important;box-sizing:border-box!important;
    width:106px!important;min-width:106px!important;max-width:106px!important;height:51px!important;min-height:51px!important;
    padding:0!important;margin:0!important;border:0!important;border-radius:27px!important;background:#fff!important;
    box-shadow:none!important;font-size:0!important;color:transparent!important;-webkit-text-fill-color:transparent!important;outline:none!important;
}
.stApp div[class*="st-key-profile_pill_shell"] [data-testid="stButton"] button::before{
    content:""!important;position:absolute!important;left:14px!important;top:16px!important;width:24px!important;height:20px!important;
    background:transparent no-repeat center/contain!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='20' viewBox='0 0 24 20' fill='none'%3E%3Cpath d='M2 3h20M2 10h20M2 17h20' stroke='%238b9abc' stroke-width='1.8' stroke-linecap='round'/%3E%3C/svg%3E")!important;
}
.stApp div[class*="st-key-profile_pill_shell"] [data-testid="stButton"] button::after{
    content:"2"!important;position:absolute!important;right:8px!important;top:9px!important;width:32px!important;height:32px!important;
    border-radius:50%!important;background:#f04452!important;color:#fff!important;-webkit-text-fill-color:#fff!important;
    display:flex!important;align-items:center!important;justify-content:center!important;font:700 11px/1 Arial,sans-serif!important;
    border:2px solid #fff!important;box-sizing:border-box!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'%3E%3Cdefs%3E%3CclipPath id='c'%3E%3Ccircle cx='16' cy='16' r='15'/%3E%3C/clipPath%3E%3C/defs%3E%3Cg clip-path='url(%23c)'%3E%3Crect width='32' height='32' fill='%23e9d6c7'/%3E%3Cpath d='M1 32c1-8 6-12 15-12s14 4 15 12' fill='%234a6a8d'/%3E%3Ccircle cx='16' cy='12' r='6' fill='%23f1c9ad'/%3E%3Cpath d='M9 12c0-7 3-10 8-9 5 1 7 5 6 10l-2-4c-4 1-7-1-9-3l-3 6Z' fill='%234a342e'/%3E%3C/g%3E%3Ccircle cx='16' cy='16' r='15' fill='none' stroke='%23e2e6ef'/%3E%3C/svg%3E")!important;
    background-repeat:no-repeat!important;background-position:center!important;background-size:32px 32px!important;
}

/* Visible fallback styling for the two controls, independent of empty-button rendering */
.stApp .st-key-candidate_nav_actions [class*="st-key-top_nav_alerts"] button{
    display:flex!important;align-items:center!important;justify-content:center!important;
    width:42px!important;min-width:42px!important;height:48px!important;min-height:48px!important;
    padding:0!important;border:0!important;border-radius:0!important;background:transparent!important;
    color:#7180a6!important;font-size:0!important;box-shadow:none!important;position:relative!important;
}
.stApp .st-key-candidate_nav_actions [class*="st-key-top_nav_alerts"] button::before{
    content:"♧"!important;font-family:Arial,sans-serif!important;font-size:29px!important;line-height:1!important;
    color:#7180a6!important;position:absolute!important;left:3px!important;top:6px!important;
    width:34px!important;height:34px!important;background-image:none!important;
}
.stApp .st-key-candidate_nav_actions [class*="st-key-top_nav_alerts"] button::after{
    content:"4"!important;position:absolute!important;right:-1px!important;top:0!important;width:19px!important;height:19px!important;
    border-radius:50%!important;display:flex!important;align-items:center!important;justify-content:center!important;
    background:#f04452!important;color:#fff!important;font:700 11px/1 Arial,sans-serif!important;border:2px solid #fff!important;
}
.stApp .st-key-profile_pill_shell{
    display:flex!important;align-items:center!important;justify-content:center!important;
    width:108px!important;min-width:108px!important;max-width:108px!important;height:53px!important;
    border:1px solid #e2e6ef!important;border-radius:29px!important;background:#f2f6ff!important;
    box-sizing:border-box!important;padding:0!important;margin:0!important;overflow:visible!important;
}
.stApp .st-key-profile_pill_shell [data-testid="stButton"] button{
    position:relative!important;display:block!important;width:106px!important;min-width:106px!important;
    height:51px!important;min-height:51px!important;padding:0!important;border:0!important;
    border-radius:27px!important;background:transparent!important;box-shadow:none!important;
    color:transparent!important;font-size:0!important;overflow:visible!important;
}
.stApp .st-key-profile_pill_shell [data-testid="stButton"] button::before{
    content:"☰"!important;position:absolute!important;left:14px!important;top:12px!important;
    font-family:Arial,sans-serif!important;font-size:23px!important;line-height:25px!important;color:#8b9abc!important;
    background-image:none!important;
}
.stApp .st-key-profile_pill_shell [data-testid="stButton"] button::after{
    content:"2"!important;position:absolute!important;right:8px!important;top:9px!important;width:32px!important;height:32px!important;
    border-radius:50%!important;display:flex!important;align-items:center!important;justify-content:center!important;
    background:#f04452!important;color:#fff!important;font:700 11px/1 Arial,sans-serif!important;border:2px solid #fff!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'%3E%3Cdefs%3E%3CclipPath id='c'%3E%3Ccircle cx='16' cy='16' r='15'/%3E%3C/clipPath%3E%3C/defs%3E%3Cg clip-path='url(%23c)'%3E%3Crect width='32' height='32' fill='%23e9d6c7'/%3E%3Cpath d='M1 32c1-8 6-12 15-12s14 4 15 12' fill='%234a6a8d'/%3E%3Ccircle cx='16' cy='12' r='6' fill='%23f1c9ad'/%3E%3Cpath d='M9 12c0-7 3-10 8-9 5 1 7 5 6 10l-2-4c-4 1-7-1-9-3l-3 6Z' fill='%234a342e'/%3E%3C/g%3E%3Ccircle cx='16' cy='16' r='15' fill='none' stroke='%23e2e6ef'/%3E%3C/svg%3E")!important;
    background-repeat:no-repeat!important;background-position:center!important;background-size:32px 32px!important;
}

/* One shared Profile Navigation Container: notification + hamburger + avatar */
.stApp .st-key-profile_pill_shell{
    display:flex!important;align-items:center!important;justify-content:center!important;
    width:176px!important;min-width:176px!important;max-width:176px!important;height:53px!important;min-height:53px!important;
    box-sizing:border-box!important;padding:0 5px!important;margin:0!important;
    border:1px solid #dce4ff!important;border-radius:29px!important;background:#f2f6ff!important;overflow:visible!important;
}
.stApp .st-key-profile_pill_shell [data-testid="stHorizontalBlock"]{
    display:flex!important;flex-flow:row nowrap!important;align-items:center!important;justify-content:center!important;
    gap:4px!important;width:100%!important;margin:0!important;padding:0!important;
}
.stApp .st-key-profile_pill_shell [data-testid="column"]{min-width:0!important;padding:0!important;flex-shrink:0!important}
.stApp .st-key-profile_pill_shell [data-testid="column"]:first-child{flex:0 0 40px!important;width:40px!important;max-width:40px!important}
.stApp .st-key-profile_pill_shell [data-testid="column"]:nth-child(2){flex:0 0 118px!important;width:118px!important;max-width:118px!important}
.stApp .st-key-profile_pill_shell [data-testid="stButton"]{width:100%!important;margin:0!important;padding:0!important}
.stApp .st-key-profile_pill_shell [data-testid="stButton"] button,
.stApp .st-key-profile_pill_shell [data-testid="stButton"] button:hover,
.stApp .st-key-profile_pill_shell [data-testid="stButton"] button:focus{
    position:relative!important;display:block!important;width:100%!important;min-width:0!important;height:48px!important;min-height:48px!important;
    padding:0!important;margin:0!important;border:0!important;border-radius:24px!important;background:transparent!important;
    box-shadow:none!important;color:transparent!important;-webkit-text-fill-color:transparent!important;font-size:0!important;outline:none!important;
}
.stApp .st-key-profile_pill_shell [class*="st-key-top_nav_alerts"] button::before{
    content:"♧"!important;position:absolute!important;left:4px!important;top:6px!important;width:30px!important;height:34px!important;
    font:normal 28px/34px Arial,sans-serif!important;color:#7180a6!important;-webkit-text-fill-color:#7180a6!important;
    text-align:center!important;background:none!important;
}
.stApp .st-key-profile_pill_shell [class*="st-key-top_nav_alerts"] button::after{
    content:"4"!important;position:absolute!important;right:0!important;top:0!important;width:19px!important;height:19px!important;
    border-radius:50%!important;display:flex!important;align-items:center!important;justify-content:center!important;
    background:#f04452!important;color:#fff!important;-webkit-text-fill-color:#fff!important;font:700 11px/1 Arial,sans-serif!important;border:2px solid #f2f6ff!important;
}
.stApp .st-key-profile_pill_shell [class*="st-key-top_nav_profile"] button::before{
    content:"☰"!important;position:absolute!important;left:9px!important;top:11px!important;
    font:normal 22px/26px Arial,sans-serif!important;color:#8b9abc!important;-webkit-text-fill-color:#8b9abc!important;background:none!important;
}
.stApp .st-key-profile_pill_shell [class*="st-key-top_nav_profile"] button::after{
    content:"2"!important;position:absolute!important;right:5px!important;top:7px!important;width:32px!important;height:32px!important;
    border-radius:50%!important;display:flex!important;align-items:center!important;justify-content:center!important;
    background:#f04452!important;color:#fff!important;-webkit-text-fill-color:#fff!important;font:700 11px/1 Arial,sans-serif!important;border:2px solid #f2f6ff!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'%3E%3Cdefs%3E%3CclipPath id='c'%3E%3Ccircle cx='16' cy='16' r='15'/%3E%3C/clipPath%3E%3C/defs%3E%3Cg clip-path='url(%23c)'%3E%3Crect width='32' height='32' fill='%23e9d6c7'/%3E%3Cpath d='M1 32c1-8 6-12 15-12s14 4 15 12' fill='%234a6a8d'/%3E%3Ccircle cx='16' cy='12' r='6' fill='%23f1c9ad'/%3E%3Cpath d='M9 12c0-7 3-10 8-9 5 1 7 5 6 10l-2-4c-4 1-7-1-9-3l-3 6Z' fill='%234a342e'/%3E%3C/g%3E%3Ccircle cx='16' cy='16' r='15' fill='none' stroke='%23e2e6ef'/%3E%3C/svg%3E")!important;
    background-repeat:no-repeat!important;background-position:center!important;background-size:32px 32px!important;
}

/* FINAL OVERRIDE: one shared pill around both notification and candidate profile */
.stApp div.st-key-profile_pill_shell{
    display:flex!important;align-items:center!important;justify-content:center!important;
    box-sizing:border-box!important;width:176px!important;min-width:176px!important;max-width:176px!important;
    height:53px!important;min-height:53px!important;margin:0!important;padding:0 5px!important;
    border:1px solid #dce4ff!important;border-radius:29px!important;background:#f2f6ff!important;
    box-shadow:none!important;overflow:visible!important;
}
.stApp div.st-key-profile_pill_shell > div[data-testid="stHorizontalBlock"]{
    display:flex!important;flex-flow:row nowrap!important;align-items:center!important;justify-content:flex-start!important;
    width:164px!important;min-width:164px!important;max-width:164px!important;gap:4px!important;margin:0!important;padding:0!important;
}
.stApp div.st-key-profile_pill_shell > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]{
    min-width:0!important;flex-shrink:0!important;padding:0!important;margin:0!important;
}
.stApp div.st-key-profile_pill_shell > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child{
    flex:0 0 38px!important;width:38px!important;max-width:38px!important;
}
.stApp div.st-key-profile_pill_shell > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2){
    flex:0 0 118px!important;width:118px!important;max-width:118px!important;
}
.stApp div.st-key-profile_pill_shell [class*="st-key-top_nav_alerts"] [data-testid="stButton"],
.stApp div.st-key-profile_pill_shell [class*="st-key-top_nav_profile"] [data-testid="stButton"]{
    width:100%!important;margin:0!important;padding:0!important;
}
.stApp div.st-key-profile_pill_shell [class*="st-key-top_nav_alerts"] button,
.stApp div.st-key-profile_pill_shell [class*="st-key-top_nav_alerts"] button:hover,
.stApp div.st-key-profile_pill_shell [class*="st-key-top_nav_alerts"] button:focus{
    position:relative!important;display:block!important;width:38px!important;min-width:38px!important;height:48px!important;min-height:48px!important;
    margin:0!important;padding:0!important;border:0!important;border-radius:0!important;background:transparent!important;
    box-shadow:none!important;color:transparent!important;-webkit-text-fill-color:transparent!important;font-size:0!important;
}
.stApp div.st-key-profile_pill_shell [class*="st-key-top_nav_alerts"] button::before{
    content:""!important;position:absolute!important;left:3px!important;top:8px!important;width:29px!important;height:32px!important;
    background:transparent no-repeat center/contain!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='30' height='34' viewBox='0 0 30 34' fill='none'%3E%3Cpath d='M15 4.5c-5.1 0-8.1 3.9-8.1 9.1v4.1c0 1.9-.7 3.3-2 4.7L3 24.5c-.8 1-.2 2.1 1 2.1h22c1.2 0 1.8-1.1 1-2.1l-1.9-2.1c-1.3-1.4-2-2.8-2-4.7v-4.1c0-5.2-3-9.1-8.1-9.1Z' stroke='%23717FA6' stroke-width='1.45' stroke-linejoin='round'/%3E%3Cpath d='M11.5 29c.6 1.8 1.8 2.7 3.5 2.7s2.9-.9 3.5-2.7' stroke='%23717FA6' stroke-width='1.45' stroke-linecap='round'/%3E%3C/svg%3E")!important;
}
.stApp div.st-key-profile_pill_shell [class*="st-key-top_nav_alerts"] button::after{
    content:"4"!important;position:absolute!important;right:-1px!important;top:0!important;width:19px!important;height:19px!important;
    display:flex!important;align-items:center!important;justify-content:center!important;border-radius:50%!important;
    background:#f04452!important;color:#fff!important;-webkit-text-fill-color:#fff!important;
    font:700 11px/1 Arial,sans-serif!important;border:2px solid #f2f6ff!important;box-sizing:border-box!important;
}
.stApp div.st-key-profile_pill_shell [class*="st-key-top_nav_profile"] button,
.stApp div.st-key-profile_pill_shell [class*="st-key-top_nav_profile"] button:hover,
.stApp div.st-key-profile_pill_shell [class*="st-key-top_nav_profile"] button:focus{
    position:relative!important;display:block!important;width:118px!important;min-width:118px!important;height:48px!important;min-height:48px!important;
    margin:0!important;padding:0!important;border:0!important;border-radius:24px!important;background:transparent!important;
    box-shadow:none!important;color:transparent!important;-webkit-text-fill-color:transparent!important;font-size:0!important;
}
.stApp div.st-key-profile_pill_shell [class*="st-key-top_nav_profile"] button::before{
    content:"☰"!important;position:absolute!important;left:5px!important;top:11px!important;
    font:normal 22px/26px Arial,sans-serif!important;color:#8b9abc!important;-webkit-text-fill-color:#8b9abc!important;
}
.stApp div.st-key-profile_pill_shell [class*="st-key-top_nav_profile"] button::after{
    content:"2"!important;position:absolute!important;right:3px!important;top:7px!important;width:32px!important;height:32px!important;
    display:flex!important;align-items:center!important;justify-content:center!important;border-radius:50%!important;
    background:#f04452!important;color:#fff!important;-webkit-text-fill-color:#fff!important;
    font:700 11px/1 Arial,sans-serif!important;border:2px solid #f2f6ff!important;box-sizing:border-box!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'%3E%3Cdefs%3E%3CclipPath id='c'%3E%3Ccircle cx='16' cy='16' r='15'/%3E%3C/clipPath%3E%3C/defs%3E%3Cg clip-path='url(%23c)'%3E%3Crect width='32' height='32' fill='%23e9d6c7'/%3E%3Cpath d='M1 32c1-8 6-12 15-12s14 4 15 12' fill='%234a6a8d'/%3E%3Ccircle cx='16' cy='12' r='6' fill='%23f1c9ad'/%3E%3Cpath d='M9 12c0-7 3-10 8-9 5 1 7 5 6 10l-2-4c-4 1-7-1-9-3l-3 6Z' fill='%234a342e'/%3E%3C/g%3E%3Ccircle cx='16' cy='16' r='15' fill='none' stroke='%23e2e6ef'/%3E%3C/svg%3E")!important;
    background-repeat:no-repeat!important;background-position:center!important;background-size:32px 32px!important;
}

/* Match supplied reference: standalone notification bell beside the profile pill */
.stApp .st-key-candidate_nav_actions{
    width:170px!important;min-width:170px!important;max-width:170px!important;
    margin:0!important;padding:0!important;border:0!important;background:transparent!important;box-shadow:none!important;
}
.stApp .st-key-candidate_nav_actions [data-testid="stHorizontalBlock"]{
    display:flex!important;flex-flow:row nowrap!important;align-items:center!important;justify-content:flex-start!important;
    width:170px!important;min-width:170px!important;max-width:170px!important;gap:8px!important;margin:0!important;padding:0!important;
}
.stApp .st-key-candidate_nav_actions [data-testid="column"]{min-width:0!important;flex-shrink:0!important;padding:0!important;margin:0!important}
.stApp .st-key-candidate_nav_actions [data-testid="column"]:first-child{flex:0 0 42px!important;width:42px!important;max-width:42px!important}
.stApp .st-key-candidate_nav_actions [data-testid="column"]:nth-child(2){flex:0 0 108px!important;width:108px!important;max-width:108px!important}
.stApp .st-key-candidate_nav_actions [class*="st-key-top_nav_alerts"] button,
.stApp .st-key-candidate_nav_actions [class*="st-key-top_nav_alerts"] button:hover,
.stApp .st-key-candidate_nav_actions [class*="st-key-top_nav_alerts"] button:focus{
    position:relative!important;display:block!important;width:42px!important;min-width:42px!important;max-width:42px!important;
    height:48px!important;min-height:48px!important;padding:0!important;margin:0!important;border:0!important;border-radius:0!important;
    background:transparent!important;box-shadow:none!important;color:transparent!important;-webkit-text-fill-color:transparent!important;font-size:0!important;
}
.stApp .st-key-candidate_nav_actions [class*="st-key-top_nav_alerts"] button::before{
    content:""!important;position:absolute!important;left:5px!important;top:7px!important;width:30px!important;height:34px!important;
    background:transparent no-repeat center/contain!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='30' height='34' viewBox='0 0 30 34' fill='none'%3E%3Cpath d='M15 4.5c-5.1 0-8.1 3.9-8.1 9.1v4.1c0 1.9-.7 3.3-2 4.7L3 24.5c-.8 1-.2 2.1 1 2.1h22c1.2 0 1.8-1.1 1-2.1l-1.9-2.1c-1.3-1.4-2-2.8-2-4.7v-4.1c0-5.2-3-9.1-8.1-9.1Z' stroke='%23717FA6' stroke-width='1.45' stroke-linejoin='round'/%3E%3Cpath d='M11.5 29c.6 1.8 1.8 2.7 3.5 2.7s2.9-.9 3.5-2.7' stroke='%23717FA6' stroke-width='1.45' stroke-linecap='round'/%3E%3C/svg%3E")!important;
}
.stApp .st-key-candidate_nav_actions [class*="st-key-top_nav_alerts"] button::after{
    content:"4"!important;position:absolute!important;right:0!important;top:0!important;width:19px!important;height:19px!important;
    border-radius:50%!important;display:flex!important;align-items:center!important;justify-content:center!important;
    background:#f04452!important;color:#fff!important;-webkit-text-fill-color:#fff!important;font:700 11px/1 Arial,sans-serif!important;border:2px solid #fff!important;
}
.stApp .st-key-candidate_nav_actions .st-key-profile_pill_shell{
    display:flex!important;align-items:center!important;justify-content:center!important;
    width:108px!important;min-width:108px!important;max-width:108px!important;height:53px!important;min-height:53px!important;
    padding:0!important;margin:0!important;border:1px solid #e2e6ef!important;border-radius:29px!important;background:#fff!important;box-sizing:border-box!important;
}
.stApp .st-key-candidate_nav_actions .st-key-profile_pill_shell [data-testid="stButton"] button,
.stApp .st-key-candidate_nav_actions .st-key-profile_pill_shell [data-testid="stButton"] button:hover,
.stApp .st-key-candidate_nav_actions .st-key-profile_pill_shell [data-testid="stButton"] button:focus{
    position:relative!important;display:block!important;width:106px!important;min-width:106px!important;height:51px!important;min-height:51px!important;
    padding:0!important;margin:0!important;border:0!important;border-radius:27px!important;background:transparent!important;box-shadow:none!important;
    color:transparent!important;-webkit-text-fill-color:transparent!important;font-size:0!important;
}
.stApp .st-key-candidate_nav_actions .st-key-profile_pill_shell [data-testid="stButton"] button::before{
    content:"☰"!important;position:absolute!important;left:14px!important;top:11px!important;font:normal 22px/26px Arial,sans-serif!important;
    color:#8b9abc!important;-webkit-text-fill-color:#8b9abc!important;
}
.stApp .st-key-candidate_nav_actions .st-key-profile_pill_shell [data-testid="stButton"] button::after{
    content:"2"!important;position:absolute!important;right:5px!important;top:7px!important;width:32px!important;height:32px!important;
    border-radius:50%!important;display:flex!important;align-items:center!important;justify-content:center!important;
    background:#f04452!important;color:#fff!important;-webkit-text-fill-color:#fff!important;font:700 11px/1 Arial,sans-serif!important;border:2px solid #fff!important;
    background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'%3E%3Cdefs%3E%3CclipPath id='c'%3E%3Ccircle cx='16' cy='16' r='15'/%3E%3C/clipPath%3E%3C/defs%3E%3Cg clip-path='url(%23c)'%3E%3Crect width='32' height='32' fill='%23e9d6c7'/%3E%3Cpath d='M1 32c1-8 6-12 15-12s14 4 15 12' fill='%234a6a8d'/%3E%3Ccircle cx='16' cy='12' r='6' fill='%23f1c9ad'/%3E%3Cpath d='M9 12c0-7 3-10 8-9 5 1 7 5 6 10l-2-4c-4 1-7-1-9-3l-3 6Z' fill='%234a342e'/%3E%3C/g%3E%3Ccircle cx='16' cy='16' r='15' fill='none' stroke='%23e2e6ef'/%3E%3C/svg%3E")!important;
    background-repeat:no-repeat!important;background-position:center!important;background-size:32px 32px!important;
}

/* Header alignment fix: keep bell and compact profile pill on the same header row */
.stApp .st-key-candidate_top_nav [data-testid="column"]:nth-child(7){
    display:flex!important;align-items:center!important;justify-content:flex-end!important;
    min-width:0!important;overflow:visible!important;
}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions{
    display:flex!important;align-items:center!important;justify-content:flex-end!important;
    width:170px!important;min-width:170px!important;max-width:170px!important;
    height:53px!important;margin:0 0 0 auto!important;padding:0!important;
    border:0!important;background:transparent!important;box-shadow:none!important;overflow:visible!important;
}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions [data-testid="stHorizontalBlock"]{
    display:flex!important;flex-flow:row nowrap!important;align-items:center!important;justify-content:flex-end!important;
    gap:8px!important;width:170px!important;min-width:170px!important;max-width:170px!important;margin:0!important;padding:0!important;
}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions [data-testid="column"]{min-width:0!important;flex-shrink:0!important;padding:0!important;margin:0!important}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions [data-testid="column"]:first-child{flex:0 0 42px!important;width:42px!important;max-width:42px!important}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions [data-testid="column"]:nth-child(2){flex:0 0 108px!important;width:108px!important;max-width:108px!important}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions .st-key-profile_pill_shell{
    display:flex!important;align-items:center!important;justify-content:center!important;
    box-sizing:border-box!important;width:108px!important;min-width:108px!important;max-width:108px!important;
    height:53px!important;min-height:53px!important;margin:0!important;padding:0!important;
    border:1px solid #dce4ff!important;border-radius:29px!important;background:#f2f6ff!important;
    box-shadow:none!important;overflow:visible!important;
}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions .st-key-profile_pill_shell [data-testid="stButton"] button,
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions .st-key-profile_pill_shell [data-testid="stButton"] button:hover,
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions .st-key-profile_pill_shell [data-testid="stButton"] button:focus{
    width:106px!important;min-width:106px!important;max-width:106px!important;height:51px!important;min-height:51px!important;
    margin:0!important;padding:0!important;border:0!important;border-radius:27px!important;background:transparent!important;
    box-shadow:none!important;
}

/* Force the whole top navigation row to stay on one line and reserve space for actions */
.stApp .st-key-candidate_top_nav{
    width:100%!important;max-width:100%!important;overflow:visible!important;
}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"]{
    display:flex!important;flex-flow:row nowrap!important;align-items:center!important;
    justify-content:space-between!important;gap:clamp(4px,.45vw,8px)!important;
    width:100%!important;max-width:100%!important;overflow:visible!important;
}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]{
    min-width:0!important;flex-shrink:1!important;padding:0!important;margin:0!important;overflow:visible!important;
}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(7){
    flex:0 0 190px!important;width:190px!important;min-width:190px!important;max-width:190px!important;
    display:flex!important;align-items:center!important;justify-content:flex-end!important;
}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions{
    width:170px!important;min-width:170px!important;max-width:170px!important;
    height:53px!important;min-height:53px!important;display:block!important;flex:0 0 170px!important;
    margin:0!important;padding:0!important;overflow:visible!important;
}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions > div[data-testid="stHorizontalBlock"]{
    display:flex!important;flex-flow:row nowrap!important;align-items:center!important;justify-content:flex-start!important;
    gap:8px!important;width:170px!important;min-width:170px!important;max-width:170px!important;
    height:53px!important;margin:0!important;padding:0!important;overflow:visible!important;
}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child{
    flex:0 0 42px!important;width:42px!important;min-width:42px!important;max-width:42px!important;
}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2){
    flex:0 0 108px!important;width:108px!important;min-width:108px!important;max-width:108px!important;
}

/* Small persistent in-app back button, visible at the top of every app view */
.stApp .st-key-global_back_navigation{
    width:100%!important;margin:0 0 6px!important;padding:0!important;background:transparent!important;
}
.stApp .st-key-global_back_navigation [data-testid="stHorizontalBlock"]{
    display:flex!important;align-items:center!important;gap:8px!important;
}
.stApp .st-key-global_back_navigation [data-testid="column"]:first-child{
    flex:0 0 92px!important;width:92px!important;max-width:92px!important;min-width:92px!important;
}
.stApp .st-key-global_back_navigation [data-testid="stButton"] button{
    width:92px!important;min-width:92px!important;height:30px!important;min-height:30px!important;
    padding:3px 10px!important;border:1px solid #cbd9f4!important;border-radius:16px!important;
    background:#fff!important;color:#2458ed!important;font-size:12px!important;font-weight:650!important;
    box-shadow:0 2px 6px rgba(35,73,150,.07)!important;
}
.stApp .st-key-global_back_navigation [data-testid="stButton"] button:hover{
    background:#edf3ff!important;border-color:#9db9fb!important;color:#1745bd!important;
}

/* Render the candidate's actual saved image as an HTML image, separate from the menu button */
.stApp .st-key-candidate_top_nav .st-key-profile_pill_shell{
    display:flex!important;align-items:center!important;justify-content:center!important;
    width:108px!important;min-width:108px!important;max-width:108px!important;height:53px!important;min-height:53px!important;
    padding:0 4px!important;margin:0!important;border:1px solid #dce4ff!important;border-radius:29px!important;
    background:#f2f6ff!important;box-sizing:border-box!important;overflow:visible!important;
}
.stApp .st-key-candidate_top_nav .st-key-profile_pill_shell [data-testid="stHorizontalBlock"]{
    display:flex!important;align-items:center!important;justify-content:center!important;flex-flow:row nowrap!important;
    width:98px!important;min-width:98px!important;max-width:98px!important;gap:4px!important;margin:0!important;padding:0!important;
}
.stApp .st-key-candidate_top_nav .st-key-profile_pill_shell [data-testid="column"]{min-width:0!important;padding:0!important;flex-shrink:0!important}
.stApp .st-key-candidate_top_nav .st-key-profile_pill_shell [data-testid="column"]:first-child{flex:0 0 38px!important;width:38px!important;max-width:38px!important}
.stApp .st-key-candidate_top_nav .st-key-profile_pill_shell [data-testid="column"]:nth-child(2){flex:0 0 42px!important;width:42px!important;max-width:42px!important}
.stApp .st-key-candidate_top_nav .st-key-profile_pill_shell [class*="st-key-top_nav_profile"] button,
.stApp .st-key-candidate_top_nav .st-key-profile_pill_shell [class*="st-key-top_nav_profile"] button:hover,
.stApp .st-key-candidate_top_nav .st-key-profile_pill_shell [class*="st-key-top_nav_profile"] button:focus{
    position:relative!important;width:38px!important;min-width:38px!important;max-width:38px!important;height:42px!important;min-height:42px!important;
    padding:0!important;margin:0!important;border:0!important;border-radius:20px!important;background:transparent!important;box-shadow:none!important;
    color:transparent!important;-webkit-text-fill-color:transparent!important;font-size:0!important;
}
.stApp .st-key-candidate_top_nav .st-key-profile_pill_shell [class*="st-key-top_nav_profile"] button::before{
    content:"☰"!important;position:absolute!important;inset:0!important;display:flex!important;align-items:center!important;justify-content:center!important;
    font:normal 22px/1 Arial,sans-serif!important;color:#8b9abc!important;-webkit-text-fill-color:#8b9abc!important;background:none!important;
}
.stApp .st-key-candidate_top_nav .st-key-profile_pill_shell [class*="st-key-top_nav_profile"] button::after{content:none!important;display:none!important;background:none!important}
.stApp .st-key-candidate_top_nav .st-key-profile_pill_shell .header-candidate-avatar{
    position:relative!important;width:34px!important;height:34px!important;min-width:34px!important;min-height:34px!important;
    margin:0 auto!important;overflow:visible!important;
}
.stApp .st-key-candidate_top_nav .st-key-profile_pill_shell .header-candidate-avatar img,
.stApp .st-key-candidate_top_nav .st-key-profile_pill_shell .header-candidate-avatar-empty .avatar-fallback{
    display:flex!important;width:34px!important;height:34px!important;min-width:34px!important;min-height:34px!important;
    border-radius:50%!important;object-fit:cover!important;border:1px solid #e2e6ef!important;box-sizing:border-box!important;
}
.stApp .st-key-candidate_top_nav .st-key-profile_pill_shell .header-candidate-avatar-empty .avatar-fallback{
    align-items:center!important;justify-content:center!important;background:#e9efff!important;color:#53689b!important;font-size:18px!important;
}
.stApp .st-key-candidate_top_nav .st-key-profile_pill_shell .header-candidate-avatar span,
.stApp .st-key-candidate_top_nav .st-key-profile_pill_shell .header-candidate-avatar b{
    position:absolute!important;right:-3px!important;top:-4px!important;width:18px!important;height:18px!important;
    display:flex!important;align-items:center!important;justify-content:center!important;border-radius:50%!important;
    background:#f04452!important;color:#fff!important;font:700 10px/1 Arial,sans-serif!important;border:2px solid #f2f6ff!important;box-sizing:border-box!important;
}

/* Compact dimensions matching the supplied Naukri-style reference */
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions .st-key-profile_pill_shell{
    width:108px!important;min-width:108px!important;max-width:108px!important;
    height:50px!important;min-height:50px!important;max-height:50px!important;
    padding:0 3px!important;border-radius:26px!important;
}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions .st-key-profile_pill_shell [data-testid="stHorizontalBlock"]{
    width:98px!important;min-width:98px!important;max-width:98px!important;gap:2px!important;
}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions .st-key-profile_pill_shell [data-testid="column"]:first-child{
    flex:0 0 36px!important;width:36px!important;max-width:36px!important;
}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions .st-key-profile_pill_shell [data-testid="column"]:nth-child(2){
    flex:0 0 36px!important;width:36px!important;max-width:36px!important;
}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions .st-key-profile_pill_shell .header-candidate-avatar,
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions .st-key-profile_pill_shell .header-candidate-avatar img,
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions .st-key-profile_pill_shell .header-candidate-avatar-empty .avatar-fallback{
    width:28px!important;min-width:28px!important;max-width:28px!important;
    height:28px!important;min-height:28px!important;max-height:28px!important;
}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions .st-key-profile_pill_shell .header-candidate-avatar span,
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions .st-key-profile_pill_shell .header-candidate-avatar b{
    width:18px!important;height:18px!important;right:-3px!important;top:-4px!important;
}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions .st-key-profile_pill_shell [class*="st-key-top_nav_profile"] button{
    width:36px!important;min-width:36px!important;max-width:36px!important;height:40px!important;min-height:40px!important;
}

/* Reference-header layout: centered campus navbar with balanced spacing */
.stApp .st-key-candidate_top_nav{
    width:100%!important;box-sizing:border-box!important;
    padding:8px 0!important;margin:0 0 22px!important;
    background:#fff!important;border:0!important;border-bottom:1px solid #edf0f6!important;
    border-radius:0!important;box-shadow:none!important;overflow:visible!important;
}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"]{
    width:min(1400px, calc(100% - 40px))!important;max-width:1400px!important;
    margin:0 auto!important;padding:0!important;box-sizing:border-box!important;
    display:flex!important;flex-flow:row nowrap!important;align-items:center!important;
    justify-content:space-between!important;gap:clamp(8px,1.1vw,20px)!important;
}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]{
    min-width:0!important;flex-shrink:1!important;padding:0!important;margin:0!important;overflow:visible!important;
}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(1){flex:0 0 260px!important;width:260px!important;max-width:260px!important}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2){flex:0 0 88px!important;width:88px!important;max-width:88px!important}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(3){flex:0 0 112px!important;width:112px!important;max-width:112px!important}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(4){flex:0 0 142px!important;width:142px!important;max-width:142px!important}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(5){flex:0 0 285px!important;width:285px!important;max-width:285px!important}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(6){flex:0 0 0px!important;width:0!important;max-width:0!important}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(7){flex:0 0 175px!important;width:175px!important;max-width:175px!important;display:flex!important;justify-content:flex-end!important;align-items:center!important}
.stApp .st-key-candidate_top_nav .candidate-nav-brand{font-size:22px!important;gap:6px!important;white-space:nowrap!important}
.stApp .st-key-candidate_top_nav .candidate-nav-mark{width:29px!important;height:29px!important;font-size:18px!important}
.stApp .st-key-candidate_top_nav [data-testid="stButton"] button{
    white-space:nowrap!important;font-size:14px!important;padding:0 3px!important;
}
.stApp .st-key-candidate_top_nav [data-testid="stTextInput"] input{
    height:50px!important;min-height:50px!important;border-radius:26px!important;
    border:1px solid #e2e6f0!important;background:#fff!important;
    box-shadow:0 5px 18px rgba(30,48,82,.06)!important;padding:0 18px!important;
}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions{
    width:175px!important;min-width:175px!important;max-width:175px!important;flex:0 0 175px!important;
}
.stApp .st-key-candidate_top_nav .st-key-candidate_nav_actions > div[data-testid="stHorizontalBlock"]{
    width:175px!important;min-width:175px!important;max-width:175px!important;gap:8px!important;
    display:flex!important;flex-flow:row nowrap!important;align-items:center!important;justify-content:flex-end!important;
}
@media(max-width:1100px){
 .stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"]{width:calc(100% - 20px)!important;gap:6px!important}
 .stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(1){flex-basis:210px!important;width:210px!important}
 .stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(5){flex-basis:220px!important;width:220px!important}
}
@media(max-width:780px){
 .stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"]{width:100%!important;overflow-x:auto!important;justify-content:flex-start!important}
 .stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]{flex-shrink:0!important}
}

/* Remove notification, menu and avatar from the header as requested */
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]{
    min-width:0!important;overflow:visible!important;
}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(1){flex:1.65 1 0!important;width:auto!important;max-width:none!important}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2){flex:.68 1 0!important;width:auto!important;max-width:none!important}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(3){flex:.86 1 0!important;width:auto!important;max-width:none!important}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(4){flex:.95 1 0!important;width:auto!important;max-width:none!important}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(5){flex:1.70 1 0!important;width:auto!important;max-width:360px!important}

/* Compact My Profile shortcut in the top navigation */
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(5){flex:1.55 1 0!important;width:auto!important;max-width:360px!important}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(6){flex:.58 1 0!important;width:auto!important;max-width:100px!important}
.stApp .st-key-candidate_top_nav [class*="st-key-top_nav_my_profile"]{width:100%!important}
.stApp .st-key-candidate_top_nav [class*="st-key-top_nav_my_profile"] button{
    width:100%!important;min-width:70px!important;height:34px!important;min-height:34px!important;
    padding:0 10px!important;border:1px solid #dce5ff!important;border-radius:18px!important;
    background:#f3f6ff!important;color:#2458ed!important;font-size:12px!important;font-weight:650!important;
    white-space:nowrap!important;box-shadow:none!important;
}
.stApp .st-key-candidate_top_nav [class*="st-key-top_nav_my_profile"] button:hover{
    background:#e8efff!important;border-color:#b8cbff!important;color:#1745bd!important;
}
@media(max-width:780px){
 .stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(6){flex:0 0 82px!important;width:82px!important;max-width:82px!important}
 .stApp .st-key-candidate_top_nav [class*="st-key-top_nav_my_profile"] button{font-size:11px!important;padding:0 6px!important}
}

/* Polished My Profile button: compact, clear and consistent with the campus header */
.stApp .st-key-candidate_top_nav [class*="st-key-top_nav_my_profile"] button,
.stApp .st-key-candidate_top_nav [class*="st-key-top_nav_my_profile"] button:hover,
.stApp .st-key-candidate_top_nav [class*="st-key-top_nav_my_profile"] button:focus{
    display:flex!important;align-items:center!important;justify-content:center!important;gap:7px!important;
    width:100%!important;min-width:94px!important;height:38px!important;min-height:38px!important;
    padding:0 13px!important;border:1px solid #d7e2ff!important;border-radius:22px!important;
    background:linear-gradient(180deg,#ffffff 0%,#f2f6ff 100%)!important;
    color:#2458ed!important;-webkit-text-fill-color:#2458ed!important;
    font-family:Inter,Arial,sans-serif!important;font-size:12px!important;font-weight:700!important;
    letter-spacing:.1px!important;white-space:nowrap!important;
    box-shadow:0 3px 10px rgba(36,88,237,.09)!important;transition:all .15s ease!important;
}
.stApp .st-key-candidate_top_nav [class*="st-key-top_nav_my_profile"] button::before{
    content:"♙"!important;display:inline-flex!important;align-items:center!important;justify-content:center!important;
    color:#2458ed!important;-webkit-text-fill-color:#2458ed!important;font-size:15px!important;line-height:1!important;
}
.stApp .st-key-candidate_top_nav [class*="st-key-top_nav_my_profile"] button:hover{
    background:#eaf0ff!important;border-color:#b8cbff!important;
    box-shadow:0 5px 14px rgba(36,88,237,.15)!important;transform:translateY(-1px)!important;
}
.stApp .st-key-candidate_top_nav [class*="st-key-top_nav_my_profile"] button:focus{
    outline:2px solid #c8d7ff!important;outline-offset:2px!important;
}
@media(max-width:780px){
 .stApp .st-key-candidate_top_nav [class*="st-key-top_nav_my_profile"] button{
    min-width:88px!important;height:34px!important;min-height:34px!important;padding:0 8px!important;font-size:11px!important;
 }
}

/* Place the compact back arrow at the far-left of the home header */
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child{
    flex:0 0 38px!important;width:38px!important;min-width:38px!important;max-width:38px!important;
    display:flex!important;align-items:center!important;justify-content:flex-start!important;
}
.stApp .st-key-candidate_top_nav [class*="st-key-header_page_back"] button{
    width:30px!important;min-width:30px!important;height:30px!important;min-height:30px!important;
    padding:0!important;border:1px solid #e1e8f7!important;border-radius:10px!important;
    background:#f5f7fc!important;color:#51617f!important;font-size:18px!important;font-weight:500!important;
    box-shadow:none!important;
}
.stApp .st-key-candidate_top_nav [class*="st-key-header_page_back"] button:hover{
    background:#eaf0ff!important;border-color:#cbd9ff!important;color:#2458ed!important;
}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2){flex:1.65 1 0!important;width:auto!important;max-width:none!important}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(3){flex:.68 1 0!important;width:auto!important;max-width:none!important}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(4){flex:.86 1 0!important;width:auto!important;max-width:none!important}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(5){flex:.95 1 0!important;width:auto!important;max-width:none!important}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(6){flex:1.55 1 0!important;width:auto!important;max-width:360px!important}
.stApp .st-key-candidate_top_nav > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(7){flex:.58 1 0!important;width:auto!important;max-width:100px!important}

/* Back button sits above and outside the header, with a light unobtrusive style */
.stApp .st-key-global_back_navigation{
    width:100%!important;margin:0 0 4px!important;padding:0 0 0 10px!important;
    background:transparent!important;border:0!important;box-shadow:none!important;
}
.stApp .st-key-global_back_navigation [data-testid="stHorizontalBlock"]{
    display:flex!important;align-items:center!important;gap:0!important;width:100%!important;
}
.stApp .st-key-global_back_navigation [data-testid="column"]:first-child{
    flex:0 0 38px!important;width:38px!important;min-width:38px!important;max-width:38px!important;
}
.stApp .st-key-global_back_navigation [class*="st-key-global_page_back"] button,
.stApp .st-key-global_back_navigation [class*="st-key-global_page_back"] button:hover,
.stApp .st-key-global_back_navigation [class*="st-key-global_page_back"] button:focus{
    width:30px!important;min-width:30px!important;height:30px!important;min-height:30px!important;
    padding:0!important;border:1px solid #e8edf6!important;border-radius:9px!important;
    background:#f7f9fd!important;color:#8a98b2!important;-webkit-text-fill-color:#8a98b2!important;
    font-size:18px!important;font-weight:400!important;box-shadow:none!important;outline:none!important;
}
.stApp .st-key-global_back_navigation [class*="st-key-global_page_back"] button:hover{
    background:#eef3fc!important;border-color:#dce5f5!important;color:#61749a!important;-webkit-text-fill-color:#61749a!important;
}

/* Final back-button polish: pale colors and no blinking/pulsing animation */
.stApp .st-key-global_back_navigation [class*="st-key-global_page_back"] button,
.stApp .st-key-global_back_navigation [class*="st-key-global_page_back"] button:hover,
.stApp .st-key-global_back_navigation [class*="st-key-global_page_back"] button:focus,
.stApp .st-key-global_back_navigation [class*="st-key-global_page_back"] button:active{
    background:#fbfcff!important;
    border:1px solid #edf1f8!important;
    color:#a7b2c6!important;
    -webkit-text-fill-color:#a7b2c6!important;
    box-shadow:none!important;
    outline:none!important;
    transform:none!important;
    animation:none!important;
    transition:none!important;
}
.stApp .st-key-global_back_navigation [class*="st-key-global_page_back"] button::before,
.stApp .st-key-global_back_navigation [class*="st-key-global_page_back"] button::after{
    animation:none!important;transition:none!important;box-shadow:none!important;
}
.stApp .st-key-global_back_navigation,
.stApp .st-key-global_back_navigation *{
    animation:none!important;
    transition:none!important;
}
@media (prefers-reduced-motion: reduce){
 .stApp .st-key-global_back_navigation,
 .stApp .st-key-global_back_navigation *{animation:none!important;transition:none!important}
}

/* Naukri-inspired login landing page and top navigation */
.stApp .st-key-auth_landing_nav{
    background:#fff!important;border-bottom:1px solid #edf0f5!important;
    padding:10px 0!important;margin:-10px -12px 28px!important;box-shadow:0 2px 10px #1b2d5406!important;
}
.stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"]{
    width:min(1240px,calc(100% - 36px))!important;margin:0 auto!important;
    display:flex!important;align-items:center!important;gap:clamp(5px,.8vw,14px)!important;flex-flow:row nowrap!important;
}
.stApp .st-key-auth_landing_nav [data-testid="column"]{min-width:0!important;padding:0!important}
.auth-brand{display:flex;align-items:center;gap:9px;white-space:nowrap;color:#f04b25;font-size:23px;font-weight:800;letter-spacing:-.6px}
.auth-brand b{color:#2458ed}.auth-brand-mark{display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:50%;background:#2f5df5;color:#fff;font-size:17px}
.stApp .st-key-auth_landing_nav [data-testid="stButton"] button{min-height:38px!important;padding:0 7px!important;background:transparent!important;border:1px solid transparent!important;border-radius:20px!important;color:#293b5d!important;font-size:13px!important;white-space:nowrap!important;box-shadow:none!important}
.stApp .st-key-auth_landing_nav [class*="st-key-auth_nav_login"] button{border:1px solid #3164ff!important;color:#2458ed!important;border-radius:22px!important;padding:0 14px!important}
.stApp .st-key-auth_landing_nav [class*="st-key-auth_nav_register"] button{background:#ed3c10!important;color:#fff!important;border-color:#ed3c10!important;border-radius:22px!important;padding:0 14px!important}
.stApp .st-key-auth_landing_nav [data-testid="stTextInput"] input{height:44px!important;min-height:44px!important;border-radius:24px!important;background:#fff!important;border:1px solid #e0e6f0!important;padding:0 16px!important;box-shadow:0 4px 14px #182b4b0a!important}
.stApp .main .block-container{max-width:1240px!important;padding-top:0!important}
.stApp{background:#fafafa!important}
.stApp .st-key-global_back_navigation{display:none!important}
.stApp .st-key-auth_landing_nav + div{margin-top:0!important}
.stApp .st-key-auth_benefits_register button{border:1px solid #4c8fe8!important;color:#4c8fe8!important;background:#fff!important;border-radius:2px!important;width:210px!important}
.naukri-login-benefits{
    min-height:455px!important;box-sizing:border-box!important;padding:62px 44px 35px!important;
    background:#fff!important;border:1px solid #eef2f6!important;border-radius:2px!important;
    box-shadow:0 10px 22px rgba(30,91,140,.13)!important;color:#10294d!important;
    position:relative!important;overflow:hidden!important;
}
.naukri-login-benefits h3{font-size:21px!important;font-weight:650!important;margin:0 0 24px!important;color:#152b4d!important}
.naukri-login-benefits .benefit-row{display:flex;align-items:center;gap:13px;margin:0 0 20px;font-size:14px;color:#142a4a;white-space:normal}
.naukri-login-benefits .benefit-row span{color:#4388f6;font-size:21px;font-weight:400}
.naukri-login-benefits .benefit-illustration{position:absolute;right:20px;bottom:20px;max-width:230px;color:#8aa8c9;font-size:13px;display:flex;align-items:center;gap:8px}
.stApp .st-key-candidate_auth_mode_selector{margin:0 0 12px!important}
.stApp [data-testid="stForm"]{border-radius:2px!important;background:#fff!important;box-shadow:0 10px 22px rgba(30,91,140,.13)!important;border:1px solid #eef2f6!important;padding:32px 42px!important}
.stApp .candidate-auth-heading{margin:0 0 22px!important}
.stApp .candidate-auth-heading h3{font-size:22px!important;color:#10294d!important}
.stApp [data-testid="stForm"] input{border-radius:0!important;min-height:44px!important;border:1px solid #ddd!important}
.stApp [data-testid="stForm"] label{font-size:12px!important;color:#10294d!important}
@media(max-width:900px){
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"]{width:calc(100% - 20px)!important;gap:4px!important}
 .auth-brand{font-size:16px}.auth-brand-mark{width:28px;height:28px}
 .stApp .st-key-auth_landing_nav [data-testid="stButton"] button{font-size:10px!important;padding:0 3px!important}
 .naukri-login-benefits{padding:28px 20px!important;min-height:390px!important}
 .stApp [data-testid="stForm"]{padding:22px 20px!important}
}

/* Keep the login landing close to the reference: clean header and no extra hero/tabs */
.stApp .hero.candidate-auth-hero{display:none!important}
.stApp [data-testid="stSegmentedControl"], .stApp .st-key-candidate_auth_mode_selector{display:none!important}
.stApp .st-key-auth_landing_nav{margin-bottom:28px!important}
.stApp .st-key-candidate_auth_mode_selector{height:0!important;margin:0!important;padding:0!important;overflow:hidden!important}
.stApp .st-key-candidate_auth_mode_selector *{display:none!important}

/* Refine candidate login screen to match the supplied Naukri login reference */
.stApp .stAppViewContainer .main .block-container{
    max-width:1100px!important;padding-top:18px!important;padding-bottom:36px!important;
}
.stApp .stAppViewContainer .main{background:#fafafa!important}
.stApp .st-key-auth_landing_nav{
    margin:0 -12px 0!important;padding:8px 0!important;min-height:66px!important;
    background:#fff!important;border-bottom:1px solid #f0f1f4!important;box-shadow:none!important;
}
.stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"]{
    width:min(1210px,calc(100% - 32px))!important;max-width:1210px!important;
    gap:clamp(4px,.65vw,10px)!important;flex-flow:row nowrap!important;justify-content:space-between!important;
}
.stApp .st-key-auth_landing_nav [data-testid="column"]{flex-shrink:1!important;min-width:0!important}
.stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(1){flex:0 0 205px!important;width:205px!important}
.stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(2){flex:0 0 54px!important;width:54px!important}
.stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(3){flex:0 0 82px!important;width:82px!important}
.stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(4){flex:0 0 72px!important;width:72px!important}
.stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(5){flex:1 1 230px!important;width:230px!important;max-width:260px!important}
.stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(6){flex:0 0 78px!important;width:78px!important}
.stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(7){flex:0 0 88px!important;width:88px!important}
.stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(8){flex:0 0 128px!important;width:128px!important}
.auth-brand{font-size:26px!important;letter-spacing:-.7px!important}
.auth-brand-mark{width:40px!important;height:40px!important;font-size:19px!important}
.stApp .st-key-auth_landing_nav [data-testid="stButton"] button{font-size:14px!important;min-height:40px!important}
.stApp .st-key-auth_landing_nav [class*="st-key-auth_nav_login"] button{border-radius:24px!important;border:1px solid #3164ff!important;color:#2458ed!important}
.stApp .st-key-auth_landing_nav [class*="st-key-auth_nav_register"] button{border-radius:24px!important;background:#e9340b!important;color:#fff!important}
.stApp .st-key-auth_landing_nav [class*="st-key-auth_nav_employers"] button{font-size:13px!important}
.stApp .st-key-candidate_auth_mode_selector,.stApp [data-testid="stSegmentedControl"]{display:none!important;height:0!important;margin:0!important;padding:0!important}
.stApp .naukri-login-benefits{
    min-height:515px!important;padding:64px 44px 30px!important;border:1px solid #eef2f6!important;
    border-radius:2px!important;background:#fff!important;box-shadow:0 9px 20px rgba(33,105,153,.16)!important;
}
.stApp .naukri-login-benefits h3{font-size:21px!important;margin-bottom:24px!important}
.stApp .naukri-login-benefits .benefit-row{font-size:14px!important;line-height:1.4!important;margin-bottom:20px!important}
.stApp .naukri-login-benefits .benefit-illustration{right:12px!important;bottom:18px!important;width:220px!important;min-height:115px!important;justify-content:center!important;text-align:center!important;background:radial-gradient(ellipse at center,#e9f7ff 0%,#fff 72%)!important;border-radius:60% 40% 50% 45%!important;padding:10px!important}
.stApp .st-key-auth_benefits_register button{width:210px!important;min-height:42px!important;border-radius:2px!important;background:#fff!important;border:1px solid #4c8fe8!important;color:#4c8fe8!important}
.stApp .candidate-auth-heading{padding:0 0 2px!important;margin:0 0 16px!important}
.stApp .candidate-auth-heading .candidate-auth-icon{display:none!important}
.stApp .candidate-auth-heading h3{font-size:22px!important;font-weight:650!important;color:#10294d!important;margin:0 0 8px!important}
.stApp [data-testid="stForm"]{
    min-height:460px!important;box-sizing:border-box!important;padding:32px 42px!important;
    border:1px solid #f0f2f5!important;border-radius:2px!important;background:#fff!important;
    box-shadow:0 9px 20px rgba(33,105,153,.16)!important;
}
.stApp [data-testid="stForm"] input{
    min-height:44px!important;border:1px solid #ddd!important;border-radius:0!important;
    background:#fff!important;box-shadow:none!important;padding:0 12px!important;
}
.stApp [data-testid="stForm"] label{font-size:12px!important;font-weight:600!important;color:#10294d!important}
.stApp [data-testid="stForm"] button[kind="primaryFormSubmit"]{
    min-height:40px!important;border-radius:0!important;background:#4b91e5!important;border:0!important;color:#fff!important;
}
.stApp .candidate-auth-note{display:none!important}
@media(max-width:1050px){
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"]{width:calc(100% - 16px)!important;gap:3px!important}
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(1){flex-basis:165px!important;width:165px!important}
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]:nth-child(5){flex-basis:170px!important;width:170px!important}
 .auth-brand{font-size:20px!important}
}
@media(max-width:760px){
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"]{overflow-x:auto!important;justify-content:flex-start!important}
 .stApp .st-key-auth_landing_nav [data-testid="stHorizontalBlock"] [data-testid="column"]{flex-shrink:0!important}
 .stApp .naukri-login-benefits{min-height:340px!important;padding:28px 22px!important}
 .stApp [data-testid="stForm"]{padding:24px 20px!important;min-height:0!important}
}
</style>
        """, unsafe_allow_html=True)
        avatar_col, avatar_info_col = st.columns([1, 5], vertical_alignment="center")
        with avatar_col:
            with st.container(key="profile_avatar"):
                profile_picture = st.file_uploader(
                    "Upload/change profile photo", type=["jpg", "jpeg", "png"],
                    key="candidate_profile_picture_upload", label_visibility="collapsed",
                    help="Click the camera icon to select a JPG/PNG photo (max 2 MB).",
                )
                if profile_picture is not None:
                    import base64
                    preview_bytes = profile_picture.getvalue()
                    if len(preview_bytes) <= 2 * 1024 * 1024:
                        preview_mime = "image/png" if profile_picture.type == "image/png" else "image/jpeg"
                        display_picture_data = "data:" + preview_mime + ";base64," + base64.b64encode(preview_bytes).decode("ascii")
                if display_picture_data:
                    st.markdown(
                        "<img src='" + display_picture_data + "' "
                        "style='width:112px;height:112px;border-radius:50%;object-fit:cover;"
                        "border:3px solid #278bff;box-shadow:0 4px 18px #0005;' "
                        "alt='Profile photo' />",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        "<div style='width:112px;height:112px;border-radius:50%;"
                        "background:#14243b;border:2px dashed #278bff;display:flex;"
                        "align-items:center;justify-content:center;font-size:42px;color:#8dbdff;'>"
                        "👤</div>",
                        unsafe_allow_html=True,
                    )
        with avatar_info_col:
            st.markdown("### " + html.escape(profile.get("full_name") or "Your profile"))
            st.caption("Profile photo · Click the camera icon to change it")
        st.metric("Profile completion", str(profile.get("completion_percent", 0)) + "%")
        st.progress(max(0, min(100, int(profile.get("completion_percent", 0)))) / 100)

        with st.expander("Edit profile", expanded=False):
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
                    picture_data = profile.get("picture_data", "") or ""
                    if profile_picture is not None:
                        picture_bytes = profile_picture.getvalue()
                        if len(picture_bytes) > 2 * 1024 * 1024:
                            st.error("The profile picture must be smaller than 2 MB.")
                            st.stop()
                        import base64
                        picture_mime = "image/png" if profile_picture.type == "image/png" else "image/jpeg"
                        picture_data = "data:" + picture_mime + ";base64," + base64.b64encode(picture_bytes).decode("ascii")
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
                            "picture_data": picture_data,
                        },
                    )
                    if save_error:
                        st.error("The profile could not be saved: " + save_error)
                    else:
                        st.session_state.candidate_name = updated_profile.get("full_name", profile_name.strip())
                        st.session_state.candidate_profile_picture = (
                            updated_profile.get("picture_data") or picture_data or ""
                        )
                        st.session_state.profile_saved_message = "Profile saved to the database successfully."
                        st.rerun()


        if st.session_state.pop("profile_saved_message", None):
            st.success("Profile saved to the database successfully.")

        st.markdown("### Resume in your profile")
        st.caption("Upload your PDF once. It is stored with your profile and reused whenever you apply.")
        with st.form("candidate_profile_resume_form"):
            profile_resume_upload = st.file_uploader(
                "Upload or replace resume (PDF)", type=["pdf"], key="candidate_profile_resume_pdf"
            )
            save_resume = st.form_submit_button("Save Resume to Profile", type="primary", use_container_width=True)
        if save_resume:
            if profile_resume_upload is None:
                st.error("Choose a PDF resume first.")
            elif len(profile_resume_upload.getvalue()) > 5 * 1024 * 1024:
                st.error("Resume PDF must be 5 MB or smaller.")
            else:
                try:
                    resume_bytes = profile_resume_upload.getvalue()
                    resume_text = extract_pdf_text(profile_resume_upload)
                    if not resume_text or len(resume_text.strip()) < 20:
                        st.error("Could not extract readable text. Please use a text-based PDF resume.")
                    else:
                        import base64
                        saved, resume_error = api_request(
                            "PUT", "/profiles/me", token=token,
                            json={
                                "full_name": profile.get("full_name", ""),
                                "headline": profile.get("headline", ""),
                                "skills": profile.get("skills", ""),
                                "timezone": profile.get("timezone", "Asia/Kolkata"),
                                "availability": profile.get("availability", "Available"),
                                "portfolio_url": profile.get("portfolio_url", ""),
                                "picture_data": profile.get("picture_data", "") or "",
                                "resume_filename": profile_resume_upload.name,
                                "resume_text": resume_text[:1000000],
                                "resume_data": base64.b64encode(resume_bytes).decode("ascii"),
                            },
                        )
                        if resume_error:
                            st.error("Resume could not be saved: " + resume_error)
                        else:
                            st.success("Resume saved to your profile successfully.")
                            st.rerun()
                except Exception as error:
                    st.error("Could not read this PDF: " + str(error))

        if profile.get("resume_filename"):
            st.success("Saved resume: " + html.escape(profile.get("resume_filename", "")))
        else:
            st.info("No resume saved yet. Upload it above before applying to jobs.")
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
                        st.markdown("#### " + html.escape(app.get("job_title", "Job")))
                        st.caption(html.escape(app.get("company_name", "Company not specified")) + " · Applied " + html.escape(app.get("applied_at", "")))
                    with right:
                        st.caption("APPLICATION STATUS")
                        st.markdown("**" + html.escape(app.get("status", "Application submitted")) + "**")
            if st.button("View all applied jobs", type="primary"):
                st.session_state.view = "applied_jobs"; st.rerun()
        if applications_error:
            st.warning("Application history could not be loaded yet: " + applications_error)
 
elif view == "applied_jobs":
    if not st.session_state.get("candidate_logged_in"):
        st.warning("Please log in to view your applied jobs.")
        if st.button("Candidate Login / Signup", type="primary"):
            st.session_state.view = "candidate_auth"; st.rerun()
    else:
        token = st.session_state.get("candidate_api_token")
        applications, applications_error = get_candidate_applications(token)
        st.markdown("## ✓ Applied Jobs")
        st.caption("Your application history and current status, loaded from the database")
        if applications_error:
            st.error("Application history could not be loaded: " + applications_error)
        st.metric("Total applications", len(applications))
        if not applications:
            st.info("No applications yet. When you apply to a job, it will appear here.")
        else:
            filter_status = st.selectbox("Filter by status", ["All statuses"] + sorted({app.get("status", "Applied") for app in applications}))
            visible = applications if filter_status == "All statuses" else [app for app in applications if app.get("status") == filter_status]
            for app in visible:
                with st.container(border=True):
                    st.markdown("### " + html.escape(app.get("job_title", "Job")))
                    st.write("**Company:** " + html.escape(app.get("company_name", "Company not specified")))
                    st.write("**Applied on:** " + html.escape(app.get("applied_at", "Not available")))
                    st.write("**Status:** " + html.escape(app.get("status", "Applied")))
                    st.caption("Resume: " + html.escape(app.get("resume_filename", "Uploaded PDF")))
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
                        from src.matching_engine import match_resume_to_jobs
                        ai_jobs = []
                        for _, job in jobs.iterrows():
                            title = str(job.get(title_col, "Open role")) if title_col else "Open role"
                            description = str(job.get(desc_col, "")) if desc_col else ""
                            required = str(job.get(skills_col, "")) if skills_col else ""
                            ai_jobs.append({
                                "title": title,
                                "description": description,
                                "required_skills": required,
                                "department": str(job.get(dept_col, "Not specified")) if dept_col else "Not specified",
                                "mode": str(job.get(mode_col, "Not specified")) if mode_col else "Not specified",
                                "low": str(job.get(low_col, "")) if low_col else "",
                                "high": str(job.get(high_col, "")) if high_col else "",
                            })
                        results = match_resume_to_jobs(resume_text, ai_jobs)
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
                st.caption("Scores are AI-assisted estimates using text relevance, recognized skills, and explicit experience/education requirements when present. Review resumes before making hiring decisions.")
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
                            st.metric("AI match score", f"{item['score']}%")
                            st.caption(f"Text relevance: {item['lexical']}%")
                            st.caption(f"Required skill coverage: {item.get('skill_coverage', 0)}%")
                            st.caption(f"Experience fit: {item.get('experience_fit', 100)}%")
                            st.caption(f"Education fit: {item.get('education_fit', 100)}%")
                            if item.get("semantic") is not None:
                                st.caption(f"Semantic similarity: {item['semantic']}%")
                            if item.get("reasons"):
                                with st.expander("Why this job matched"):
                                    for reason in item["reasons"]:
                                        st.write("• " + reason)
                            if item["low"] or item["high"]: st.caption(f"Budget: ₹{item['low'] or '—'} – ₹{item['high'] or '—'}")
        if st.button("← Back to home"):
            st.session_state.view = "home"; st.rerun()

elif view == "employee":
    st.markdown("## Company workspace")
    st.caption("Company accounts can be securely accessed or created from the Company Dashboard.")
    st.info("Log in to the Company Dashboard with your company email and password. Candidate accounts cannot access the company dashboard.")
    with st.container(key="company_login_cta"):
        if st.button("Open Company Login", type="primary", use_container_width=True):
            st.switch_page("pages/4_Employee_Dashboard.py")
    if st.button("← Back to home"):
        st.session_state.view = "home"; st.rerun()

st.divider()
st.caption("Instant Employee AI · Candidate portal and company workspace")
