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



/* Display company brand logos in clean white logo tiles */
.stApp .company-logo-wrap{width:66px;height:66px;display:flex;align-items:center;justify-content:center;background:#fff;border:1px solid #e1e8f3;border-radius:15px;overflow:hidden;box-shadow:0 4px 12px rgba(25,55,110,.07)}
.stApp .company-brand-logo{display:block;width:54px;height:54px;object-fit:contain;padding:5px;border-radius:10px;background:#fff}

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

</style>
""", unsafe_allow_html=True)

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
    st.session_state.view = "home"

with st.sidebar:
    st.markdown("<div style='font-size:23px;font-weight:900;padding:8px 0'>✦ Instant Employee</div><div style='color:#aab8cf;font-size:12px'>AI Talent Platform</div>", unsafe_allow_html=True)
    st.divider()
    st.caption("CANDIDATE")
    if st.button("⌂  Home", use_container_width=True):
        st.session_state.view = "home"; st.rerun()
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
    st.markdown("""
    <div class="landing-nav">
      <div class="landing-brand">✦ Instant <span>Employee</span></div>
      <div class="landing-nav-note">AI-POWERED TALENT PLATFORM</div>
    </div>
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

    # Search/filter controls stay visible; only the full job results are behind View all.
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

    # Keep the available-jobs summary visible under the search filters, outside View All.
    available_jobs_col, _ = st.columns([1, 2])
    with available_jobs_col:
        st.metric("Available jobs", len(jobs))




    # Company showcase: use real employer names when available, otherwise show clearly labeled UI examples.
    company_col_name = next((col for col in jobs.columns if str(col).strip().lower() in {"company name", "company", "employer"}), None)
    employer_names = []
    if company_col_name and not jobs.empty:
        employer_names = sorted({
            str(value).strip() for value in jobs[company_col_name].tolist()
            if str(value).strip()
            and str(value).strip().lower() not in {"company", "nan", "none"}
            and "@" not in str(value)
        })
    st.markdown("""
    <div class="market-section-heading">
      <h3>Explore jobs by top companies</h3>
      <span>View all ↓</span>
    </div>
    """, unsafe_allow_html=True)
    if employer_names:
        showcase = [{"name": name, "count": int((jobs[company_col_name].astype(str).str.strip() == name).sum()), "rating": "", "reviews": "", "demo": False} for name in employer_names[:4]]
    else:
        # UI examples only: current backend jobs expose company email, not a public company display name.
        showcase = [
            {"name": "TCS", "full_name": "Tata Consultancy Services", "domain": "tcs.com", "count": 8, "rating": "", "reviews": "", "demo": True},
            {"name": "Infosys", "full_name": "Infosys", "domain": "infosys.com", "count": 6, "rating": "", "reviews": "", "demo": True},
            {"name": "Wipro", "full_name": "Wipro", "domain": "wipro.com", "count": 5, "rating": "", "reviews": "", "demo": True},
            {"name": "HCLTech", "full_name": "HCLTech", "domain": "hcltech.com", "count": 4, "rating": "", "reviews": "", "demo": True},
        ]
    company_cards = st.columns(4, gap="small")
    for company_index, company in enumerate(showcase):
        company_name = company["name"]
        with company_cards[company_index]:
            rating_html = (f'<div class="company-job-rating">★ {company["rating"]} <span>|</span> {company["reviews"]}</div>' if company.get("rating") else f'<div class="company-job-count">{company["count"]} open jobs</div>')
            logo_domain = company.get("domain", "")
            logo_url = f"https://www.google.com/s2/favicons?domain={logo_domain}&sz=128" if logo_domain else ""
            logo_html = (
                f'<img class="company-brand-logo" src="{logo_url}" alt="{html.escape(company_name)} logo" '
                f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
                f'<div class="company-logo-placeholder" style="display:none">{html.escape(company_name[:1].upper())}</div>'
                if logo_url else f'<div class="company-logo-placeholder">{html.escape(company_name[:1].upper())}</div>'
            )
            st.markdown(f"""
            <div class="company-job-card">
              <div class="company-logo-wrap">{logo_html}</div>
              <div class="company-job-name">{html.escape(company_name)}</div>
              {rating_html}
              {('<div class="company-demo-note">Example</div>' if company.get("demo") else '')}
            </div>
            """, unsafe_allow_html=True)
            if st.button("View jobs  →", key=f"company_jobs_{company_index}", use_container_width=True):
                st.session_state["home_company_filter"] = company_name if not company.get("demo") else "All companies"
                st.session_state["home_show_all_jobs"] = True
                st.rerun()
    if st.button("View all companies & jobs  →", key="view_all_companies_jobs"):
        st.session_state["home_company_filter"] = "All companies"
        st.session_state["home_show_all_jobs"] = True
        st.rerun()


    heading_col, view_all_col = st.columns([5, 1])
    with heading_col:
        st.markdown('<div class="market-section-heading"><h3>Recommended jobs for you</h3></div>', unsafe_allow_html=True)
    with view_all_col:
        if st.button("View all ↓", key="recommended_view_all", use_container_width=True):
            st.session_state["home_show_all_jobs"] = True
            st.rerun()
    if not jobs.empty:
        recommended_source = jobs.head(3)
        recommended_cols = st.columns(3, gap="small")
        for rec_index, (_, rec_job) in enumerate(recommended_source.iterrows()):
            rec_title_col = next((col for col in jobs.columns if str(col).strip().lower() in {"job title", "title", "job_title"}), None)
            rec_company_col = next((col for col in jobs.columns if str(col).strip().lower() in {"company name", "company", "employer"}), None)
            rec_mode_col = next((col for col in jobs.columns if str(col).strip().lower() in {"work mode", "work_mode", "mode"}), None)
            rec_title = str(rec_job.get(rec_title_col, "Open role")) if rec_title_col else "Open role"
            rec_company = str(rec_job.get(rec_company_col, "")).strip() if rec_company_col else ""
            if "@" in rec_company:
                rec_company = "Hiring team"
            rec_mode = str(rec_job.get(rec_mode_col, "Remote")) if rec_mode_col else "Remote"
            with recommended_cols[rec_index]:
                st.markdown(f"""
                <div class="recommended-job-card">
                  <div class="recommended-job-logo">{html.escape((rec_company[:1] or rec_title[:1]).upper())}</div>
                  <div class="recommended-job-age">Open role</div>
                  <div class="recommended-job-title">{html.escape(rec_title)}</div>
                  <div class="recommended-job-company">{html.escape(rec_company or "Instant Employee")}</div>
                  <div class="recommended-job-mode">⌖ {html.escape(rec_mode)}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("View job  →", key=f"recommended_view_{rec_index}", use_container_width=True):
                    st.session_state.selected_job_index = rec_job.name
                    st.session_state.view = "job_details"
                    st.rerun()

    if st.session_state.get("home_show_all_jobs", False):
        filtered_jobs = jobs.copy()
        selected_company = st.session_state.get("home_company_filter", "All companies")
        if selected_company != "All companies" and company_col_name and not filtered_jobs.empty:
            filtered_jobs = filtered_jobs[
                filtered_jobs[company_col_name].astype(str).str.strip() == str(selected_company).strip()
            ]
            st.caption(f"Showing jobs from {selected_company}.")
            if st.button("← Show all jobs", key="clear_company_filter"):
                st.session_state["home_company_filter"] = "All companies"
                st.rerun()
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
    
        st.markdown("### Latest opportunities")
        st.caption("Open a job to read the full description and apply.")
    
        if filtered_jobs.empty:
            st.info(
                "No jobs match these filters yet. Try another keyword, choose All categories / All modes, "
                "or check back after new jobs are posted."
            )
        else:
            # Marketplace grid: compact job tiles, similar to the small cards in the reference.
            job_grid = st.columns(3, gap="medium")
            for display_index, (row_index, job) in enumerate(filtered_jobs.iterrows()):
                card_col = job_grid[display_index % 3]
                with card_col:
                    title = str(job.get(title_col, "Open role")) if title_col else "Open role"
                    department = str(job.get(dept_col_name, "Technology")) if dept_col_name else "Technology"
                    description = str(job.get(desc_col, "")) if desc_col else ""
                    skills = str(job.get(skills_col, "Skills listed in job description")) if skills_col else "Skills listed in job description"
                    mode = str(job.get(work_mode_col, "Not specified")) if work_mode_col else "Not specified"
                    low_col = next((c for c in jobs.columns if str(c).strip().lower() in {"minimum budget", "min budget", "minimum_budget"}), None)
                    high_col = next((c for c in jobs.columns if str(c).strip().lower() in {"maximum budget", "max budget", "maximum_budget"}), None)
                    low = str(job.get(low_col, "")) if low_col else ""
                    high = str(job.get(high_col, "")) if high_col else ""
                    budget = f"₹{low or '—'} – ₹{high or '—'}" if low or high else "Budget discussed"
                    short_description = description[:105] + ("…" if len(description) > 105 else "")
                    short_skills = skills[:75] + ("…" if len(skills) > 75 else "")
                    st.markdown(f"""
                    <div class="jobcard job-tile">
                      <div class="job-tile-head">
                        <div class="job-tile-logo">✦</div>
                        <span class="job-mode-pill">{html.escape(mode)}</span>
                      </div>
                      <div class="job-tile-department">{html.escape(department)}</div>
                      <h3 class="job-tile-title">{html.escape(title)}</h3>
                      <p class="job-tile-description">{html.escape(short_description or "Open this role to view the complete job description.")}</p>
                      <div class="job-tile-skills"><b>Skills</b><br>{html.escape(short_skills)}</div>
                      <div class="job-tile-budget">{html.escape(budget)}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("View details", key=f"view_job_{row_index}", use_container_width=True):
                        st.session_state.selected_job_index = row_index
                        st.session_state.view = "job_details"
                        st.rerun()
                    if st.button("Apply now", key=f"apply_job_card_{row_index}", type="primary", use_container_width=True):
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
    
    else:
        st.caption("Select View all to browse and filter every available job.")

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
    st.markdown(
        "<div class='hero candidate-auth-hero'><div class='kicker'>INSTANT EMPLOYEE · CAREER PORTAL</div>"
        "<h1>Candidate <span>account</span></h1>"
        "<p>Sign in to manage your profile, save your resume and discover opportunities matched to your skills.</p></div>",
        unsafe_allow_html=True,
    )
    login, signup = st.tabs(["Login", "Create account"])
    with login:
        form_col, feature_col = st.columns([1.05, 0.95], gap="large")
        with form_col:
            st.markdown(
                "<div class='candidate-auth-heading'><div class='candidate-auth-icon'>♙</div><div>"
                "<h3>Welcome back!</h3><p>Login to your candidate account to explore job opportunities and manage your profile.</p></div></div>",
                unsafe_allow_html=True,
            )
            with st.form("candidate_login"):
                email = st.text_input("Email address", key="candidate_login_email", placeholder="Enter your email address")
                password = st.text_input("Password", type="password", key="candidate_login_password", placeholder="Enter your password")
                submit = st.form_submit_button("Login to Dashboard  →", type="primary", use_container_width=True)
            st.markdown("<div class='candidate-auth-note'>♢  Your candidate account keeps your profile and applications in one place.</div>", unsafe_allow_html=True)
        with feature_col:
            st.markdown(
                "<div class='candidate-auth-feature'><div class='kicker'>YOUR NEXT MOVE STARTS HERE</div>"
                "<h2>Find your <span>next opportunity.</span></h2>"
                "<p>Create your profile, showcase your skills, and discover job opportunities that fit your experience.</p>"
                "<div class='candidate-feature-row'><span class='candidate-feature-icon cfi-blue'>⌕</span><div><b>Browse jobs</b><small>Explore roles and review job details.</small></div></div>"
                "<div class='candidate-feature-row'><span class='candidate-feature-icon cfi-green'>▤</span><div><b>Build your profile</b><small>Keep your resume and skills in one place.</small></div></div>"
                "<div class='candidate-feature-row'><span class='candidate-feature-icon cfi-amber'>✦</span><div><b>Get matched</b><small>Review AI-assisted job match estimates.</small></div></div>"
                "<div class='candidate-feature-foot'>✦  Take the next step in your career</div></div>",
                unsafe_allow_html=True,
            )
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
        </style>
        """, unsafe_allow_html=True)
        avatar_col, avatar_info_col = st.columns([1, 5], vertical_alignment="center")
        with avatar_col:
            with st.container(key="profile_avatar"):
                profile_picture = st.file_uploader(
                    "Upload/change profile photo", type=["jpg", "jpeg", "png"],
                    key="candidate_profile_picture", label_visibility="collapsed",
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
