
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from pypdf import PdfReader


# -----------------------------------
# Project Paths
# -----------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
JOBS_FILE = DATA_DIR / "jobs.csv"
SHORTLIST_FILE = DATA_DIR / "shortlist.csv"

sys.path.insert(0, str(PROJECT_ROOT))

from src.matching_engine import match_candidates


# -----------------------------------
# Page Configuration
# -----------------------------------
st.set_page_config(
    page_title="Find Talent | Instant Employee",
    page_icon="👥",
    layout="wide",
)


# -----------------------------------
# Company authentication
# -----------------------------------
if not st.session_state.get("company_logged_in") or not st.session_state.get("company_api_token"):
    st.warning("Your company login session is missing or has expired. Open the Company Dashboard, sign in, then use Find Talent from the sidebar. Avoid refreshing this page after login.")
    if st.button("Open Company Login", type="primary", use_container_width=True):
        st.switch_page("pages/4_Employee_Dashboard.py")
    st.stop()

API_BASE_URL = "https://instant-employee-api.onrender.com"

def api_get(path):
    try:
        response = requests.get(
            f"{API_BASE_URL}{path}",
            headers={"Authorization": f"Bearer {st.session_state.company_api_token}"},
            timeout=(8, 30),
        )
        payload = response.json()
        if not response.ok:
            return None, str(payload.get("detail", f"API error {response.status_code}"))
        return payload, None
    except Exception as error:
        return None, str(error)


def api_request(method, path, token=None, params=None):
    """Send an authenticated request to the backend and return payload/error."""
    try:
        auth_token = token or st.session_state.get("company_api_token", "")
        response = requests.request(
            method,
            f"{API_BASE_URL}{path}",
            headers={"Authorization": f"Bearer {auth_token}"},
            params=params,
            timeout=(8, 30),
        )
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if not response.ok:
            detail = payload.get("detail", f"API error {response.status_code}")
            return None, str(detail)
        return payload, None
    except Exception as error:
        return None, str(error)


SHORTLIST_COLUMNS = [
    "Job ID",
    "Candidate Name",
    "Match Score",
    "Shortlisted On",
]


# -----------------------------------
# CSS Styling
# -----------------------------------
st.markdown(
    """
    <style>
    .stApp {
        background: #f4f7fc;
        color: #172b4d;
    }

    .main .block-container {
        width: 100%;
        max-width: 1500px;
        padding: 1.5rem 2rem 2rem;
    }

    /* Hide default Streamlit navigation */
    [data-testid="stSidebarNav"] {
        display: none !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0b1930, #152b4c) !important;
    }

    [data-testid="stSidebar"] > div {
        background: transparent !important;
    }

    /* Sidebar navigation links */
    [data-testid="stSidebar"] div[data-testid="stPageLink"] a {
        background: #dce9ff !important;
        color: #123b70 !important;
        border: 1px solid #b5cdf5 !important;
        border-radius: 12px !important;
        padding: 14px 16px !important;
        font-weight: 700 !important;
    }

    [data-testid="stSidebar"] div[data-testid="stPageLink"] a * {
        color: #123b70 !important;
        -webkit-text-fill-color: #123b70 !important;
        opacity: 1 !important;
    }

    /* Page headings */
    h1, h2, h3 {
        color: #14294b !important;
    }

    /* Resume uploader */
    [data-testid="stFileUploader"] {
        background: #ffffff !important;
        border: 1px solid #dce7f5 !important;
        border-radius: 14px !important;
        padding: 12px !important;
    }

    [data-testid="stFileUploader"] section {
        background: #ffffff !important;
        border-radius: 10px !important;
    }

    /* Uploaded resume file list */
    [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] {
        background: #ffffff !important;
        border: 1px solid #dce7f5 !important;
        border-radius: 8px !important;
        margin: 8px 0 !important;
    }

    /* Resume filenames and details */
    [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] p,
    [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] span,
    [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] small,
    [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] div {
        color: #123b70 !important;
        -webkit-text-fill-color: #123b70 !important;
        opacity: 1 !important;
    }

    /* Browse files button */
    [data-testid="stFileUploader"] button {
        background: #e1ebfa !important;
        color: #123b70 !important;
        border: 1px solid #b5cdf5 !important;
        border-radius: 8px !important;
    }

    [data-testid="stFileUploader"] button * {
        color: #123b70 !important;
        -webkit-text-fill-color: #123b70 !important;
    }

    /* Metrics */
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #dce7f5;
        border-radius: 14px;
        padding: 18px;
        box-shadow: 0 4px 12px rgba(28, 55, 90, 0.04);
    }

    div[data-testid="stMetric"] label {
        color: #526987 !important;
    }

    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #123b70 !important;
    }

    /* Expanders */
    [data-testid="stExpander"] {
        background: #ffffff;
        border: 1px solid #dce7f5;
        border-radius: 10px;
    }

    /* Main action buttons */
    div.stButton > button[kind="primary"] {
        background: #1765d1 !important;
        color: #ffffff !important;
        border: 1px solid #1765d1 !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        padding: 10px 18px !important;
    }

    div.stButton > button[kind="primary"] * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }

    div.stButton > button[kind="primary"]:hover {
        background: #104da8 !important;
        border-color: #104da8 !important;
    }

    /* Light, readable Shortlist button in automatic matching */
    [class*="st-key-auto_shortlist_"] button {
        background: #e4edff !important;
        color: #2456a6 !important;
        -webkit-text-fill-color: #2456a6 !important;
        border: 1px solid #c9d9ff !important;
        border-radius: 10px !important;
        font-weight: 650 !important;
        box-shadow: 0 2px 7px #2456a610 !important;
    }
    [class*="st-key-auto_shortlist_"] button * {
        color: #2456a6 !important;
        -webkit-text-fill-color: #2456a6 !important;
    }
    [class*="st-key-auto_shortlist_"] button:hover {
        background: #d5e3ff !important;
        border-color: #a9c4ff !important;
    }

    [data-testid="stDataFrame"] {
        border: 1px solid #dce7f5;
        border-radius: 10px;
        overflow: hidden;
    }

    footer {
        visibility: hidden;
    }

    @media (max-width: 800px) {
        .main .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------
# Sidebar Navigation
# -----------------------------------
with st.sidebar:
    st.markdown(
        """
        <div style="padding:12px 0 22px;">
            <div style="font-size:25px;">👥</div>
            <div style="font-size:23px;font-weight:800;color:white;">
                Instant Employee
            </div>
            <div style="font-size:12px;color:#b7c8e3;">
                Recruitment Dashboard
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    st.page_link(
        "app.py",
        label="🏠 Dashboard",
        use_container_width=True,
    )

    st.page_link(
        "pages/2_Job_Posting.py",
        label="💼 Job Posting",
        use_container_width=True,
    )

    st.page_link(
        "pages/3_Match_Candidates.py",
        label="🔎 Candidate Matching",
        use_container_width=True,
    )

    st.divider()
    st.caption("Your Company · Recruiter Panel")


# -----------------------------------
# Helper Functions
# -----------------------------------
def load_jobs():
    if not JOBS_FILE.exists():
        return pd.DataFrame()

    try:
        jobs = pd.read_csv(JOBS_FILE)
        jobs.columns = jobs.columns.astype(str).str.strip()
        return jobs.fillna("")
    except (
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        UnicodeDecodeError,
    ):
        return pd.DataFrame()


def load_shortlist():
    if not SHORTLIST_FILE.exists():
        return pd.DataFrame(columns=SHORTLIST_COLUMNS)

    try:
        df = pd.read_csv(SHORTLIST_FILE)
        df.columns = df.columns.astype(str).str.strip()

        for column in SHORTLIST_COLUMNS:
            if column not in df.columns:
                df[column] = ""

        return df[SHORTLIST_COLUMNS].fillna("")

    except (
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        UnicodeDecodeError,
    ):
        return pd.DataFrame(columns=SHORTLIST_COLUMNS)


def save_shortlist(job_id, candidate_name, score):
    current = load_shortlist()

    job_id = str(job_id).strip()
    candidate_name = str(candidate_name).strip()

    duplicate = (
        current["Job ID"].astype(str).str.strip().eq(job_id)
        & current["Candidate Name"]
        .astype(str)
        .str.strip()
        .str.casefold()
        .eq(candidate_name.casefold())
    )

    if duplicate.any():
        return False

    new_row = pd.DataFrame([{
        "Job ID": job_id,
        "Candidate Name": candidate_name,
        "Match Score": round(float(score), 2),
        "Shortlisted On": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
    }])

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    pd.concat(
        [current, new_row],
        ignore_index=True,
    ).to_csv(SHORTLIST_FILE, index=False)

    return True


def as_text_list(value):
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    try:
        return ", ".join(str(item) for item in value)
    except TypeError:
        return str(value)


def number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


# -----------------------------------
# Header
# -----------------------------------
st.title("👥 Find Talent")
st.caption(
    "Automatically rank every applicant using the resume saved in their candidate profile."
)

st.subheader("Automatic job-wise matching")
st.caption("Candidates who apply with a saved profile resume are matched automatically. No manual resume upload is needed for these applicants.")
company_jobs, jobs_error = api_get("/jobs/mine")
company_apps, apps_error = api_get("/applications/company")
company_jobs = company_jobs if isinstance(company_jobs, list) else []
company_apps = company_apps if isinstance(company_apps, list) else []
if jobs_error:
    st.warning("Could not load company jobs: " + jobs_error)
if apps_error:
    st.warning("Could not load applicants: " + apps_error)

if not company_jobs:
    st.info("No database jobs found for this company yet. Post a job first.")
else:
    job_options = {f"{job.get('title', 'Job')} · #{job.get('id')}": job for job in company_jobs}
    chosen_job_label = st.selectbox("Select a job to rank its applicants", list(job_options.keys()), key="automatic_matching_job")
    chosen_job = job_options[chosen_job_label]
    job_applicants = [row for row in company_apps if row.get("job_id") == chosen_job.get("id")]
    applicants_with_resume = [row for row in job_applicants if str(row.get("resume_text") or "").strip()]
    st.metric("Applicants for this job", len(job_applicants))
    if not job_applicants:
        st.info("No one has applied to this job yet. New applications will appear here.")
    elif not applicants_with_resume:
        st.info("Applicants are present, but none has a saved readable resume yet. Ask candidates to save a PDF in My Profile.")
    else:
        job_description = next((str(row.get("job_description") or "") for row in applicants_with_resume if row.get("job_description")), "")
        resumes = {}
        app_by_label = {}
        for row in applicants_with_resume:
            email = str(row.get("candidate_email") or "")
            name = str(row.get("candidate_name") or email or f"Candidate {row.get('candidate_id')}")
            label = f"{name} ({email})" if email else name
            resumes[label] = str(row.get("resume_text") or "")
            app_by_label[label] = row
        try:
            ranked_candidates = match_candidates(job_description, resumes)
            ranked_table = []
            for rank, candidate in enumerate(ranked_candidates, start=1):
                app_row = app_by_label.get(candidate.get("name"), {})
                ranked_table.append({
                    "Rank": rank,
                    "Candidate": candidate.get("name", "Candidate"),
                    "Match Score": f"{float(candidate.get('final_score', 0)):.1f}%",
                    "Skill Coverage": f"{float(candidate.get('skill_coverage', 0)):.1f}%",
                    "Matched Skills": ", ".join(candidate.get("matched_skills") or []),
                    "Missing Skills": ", ".join(candidate.get("missing_skills") or []),
                    "Status": app_row.get("status", "Applied"),
                    "Resume": app_row.get("resume_filename", ""),
                })
            if ranked_table:
                st.dataframe(pd.DataFrame(ranked_table), use_container_width=True, hide_index=True)
                st.markdown("### Shortlist candidates")
                st.caption("Use the action beside each candidate's name to shortlist them for this job.")
                for rank, candidate in enumerate(ranked_candidates, start=1):
                    app_row = app_by_label.get(candidate.get("name"), {})
                    candidate_name = str(candidate.get("name", "Candidate"))
                    candidate_status = str(app_row.get("status", "Applied")).strip()
                    name_col, action_col = st.columns([3, 1.4], vertical_alignment="center")
                    with name_col:
                        st.write(f"**{rank}. {candidate_name}**")
                    with action_col:
                        if candidate_status.casefold() == "shortlisted":
                            st.markdown(
                                "<span style='display:inline-block;background:#e4f6e9;color:#22643b;"
                                "border:1px solid #b8e2c4;border-radius:14px;padding:5px 11px;"
                                "font-size:12px;font-weight:700;white-space:nowrap'>✓ Shortlisted</span>",
                                unsafe_allow_html=True,
                            )
                        elif app_row.get("id") is not None:
                            if st.button("＋ Shortlist", key=f"auto_shortlist_{app_row.get('id')}"):
                                _, status_error = api_request(
                                    "PATCH",
                                    f"/applications/{app_row.get('id')}/status",
                                    token=st.session_state.get("company_api_token"),
                                    params={"new_status": "Shortlisted"},
                                )
                                if status_error:
                                    st.error("Could not shortlist candidate: " + status_error)
                                else:
                                    st.success(f"{candidate_name} was shortlisted.")
                                    st.rerun()
                        else:
                            st.caption("Status unavailable")
                st.success(f"Best match: {ranked_table[0]['Candidate']} · {ranked_table[0]['Match Score']}")
                st.caption("Ranking is recalculated from all current applicants whenever this page loads. Review resumes before making hiring decisions.")
        except Exception as error:
            st.error("Automatic candidate matching failed: " + str(error))

st.divider()
st.subheader("Legacy manual resume screening (CSV jobs)")
st.caption("Use this only for old CSV jobs or resumes that have not applied through the candidate profile workflow.")


# -----------------------------------
# Job Selection
# -----------------------------------
jobs = load_jobs()

if jobs.empty:
    st.warning(
        "No posted jobs found. Please post a job first "
        "using the Job Posting page."
    )
    st.caption(f"Jobs file location: {JOBS_FILE}")
    st.stop()


required_columns = [
    "Job Title",
    "Description",
    "Required Skills",
]

missing_columns = [
    column for column in required_columns
    if column not in jobs.columns
]

if missing_columns:
    st.error(
        "The jobs.csv file is missing required columns: "
        + ", ".join(missing_columns)
    )
    st.stop()


for column in required_columns:
    jobs[column] = jobs[column].astype(str)


st.subheader("1. Select a Posted Job")


def job_label(index):
    row = jobs.iloc[index]
    return (
        f"{row['Job Title']} | "
        f"{row['Required Skills']}"
    )


selected_index = st.selectbox(
    "Choose the job for candidate screening",
    options=list(range(len(jobs))),
    format_func=job_label,
    key="selected_job_index",
)

selected_job = jobs.iloc[selected_index]

job_id_column = next(
    (
        column for column in jobs.columns
        if column.strip().lower()
        in {"job id", "job_id", "id"}
    ),
    None,
)

selected_job_id = (
    str(selected_job[job_id_column]).strip()
    if job_id_column
    else str(selected_job["Job Title"]).strip()
)


c1, c2, c3 = st.columns(3)

c1.metric("Job Title", selected_job["Job Title"])
c2.metric(
    "Department",
    selected_job.get("Department", "N/A") or "N/A",
)
c3.metric(
    "Work Mode",
    selected_job.get("Work Mode", "N/A") or "N/A",
)


with st.expander("View Job Description and Requirements"):
    st.write("**Job Description**")
    st.write(selected_job["Description"])

    st.write("**Required Skills**")
    st.write(selected_job["Required Skills"])

    st.write(
        f"**Monthly Budget:** ₹"
        f"{selected_job.get('Minimum Budget', 'N/A')} – "
        f"₹{selected_job.get('Maximum Budget', 'N/A')}"
    )


# -----------------------------------
# Resume Upload
# -----------------------------------
st.divider()
st.subheader("2. Upload Candidate Resumes")

uploaded_files = st.file_uploader(
    "Upload one or more candidate PDF resumes",
    type=["pdf"],
    accept_multiple_files=True,
    key="candidate_resume_upload",
)

st.caption(
    "Upload resumes relevant to the selected job. "
    "Scanned PDFs may need OCR if they contain no selectable text."
)


# -----------------------------------
# Candidate Matching
# -----------------------------------
if st.button("🚀 Find Best Candidates", type="primary"):
    if not uploaded_files:
        st.error("Please upload at least one PDF resume.")

    else:
        resumes = {}
        errors = []

        for file in uploaded_files:
            try:
                reader = PdfReader(file)

                resume_text = "\n".join(
                    page.extract_text() or ""
                    for page in reader.pages
                ).strip()

                if not resume_text:
                    errors.append(
                        f"{file.name}: No readable text found. "
                        "The PDF may need OCR."
                    )
                    continue

                name = Path(file.name).stem
                original_name = name
                suffix = 2

                while name in resumes:
                    name = f"{original_name} ({suffix})"
                    suffix += 1

                resumes[name] = resume_text

            except Exception as exc:
                errors.append(f"{file.name}: {exc}")

        for error in errors:
            st.warning(error)

        if not resumes:
            st.error(
                "No readable resumes found. "
                "Please check the uploaded PDFs."
            )

        else:
            job_description = (
                f"{selected_job['Job Title']}\n"
                f"{selected_job['Description']}\n"
                f"Required Skills: "
                f"{selected_job['Required Skills']}"
            )

            try:
                with st.spinner(
                    "Matching resumes to the selected job..."
                ):
                    results = match_candidates(
                        job_description,
                        resumes,
                    )

                normalized = []

                for item in results or []:
                    candidate = dict(item)
                    candidate.setdefault("name", "Unknown")

                    similarity = number(
                        candidate.get("similarity", 0)
                    )
                    coverage = number(
                        candidate.get("skill_coverage", 0)
                    )

                    if candidate.get("final_score") is None:
                        candidate["final_score"] = round(
                            (similarity + coverage) / 2,
                            2,
                        )

                    candidate["final_score"] = number(
                        candidate.get("final_score")
                    )
                    normalized.append(candidate)

                normalized.sort(
                    key=lambda item: number(
                        item.get("final_score")
                    ),
                    reverse=True,
                )

                st.session_state["candidate_results"] = normalized
                st.session_state[
                    "candidate_results_job_id"
                ] = selected_job_id

                if normalized:
                    st.success(
                        f"Analysis completed for "
                        f"{len(normalized)} candidate(s)."
                    )
                else:
                    st.warning(
                        "No matching results were returned."
                    )

            except Exception as exc:
                st.error(f"Matching failed: {exc}")
                st.info(
                    "Check src/matching_engine.py and confirm "
                    "that match_candidates(job_description, resumes) "
                    "returns candidate names, similarity, skill_coverage, "
                    "matched_skills and missing_skills."
                )


# -----------------------------------
# Candidate Results
# -----------------------------------
results = st.session_state.get("candidate_results", [])
results_job_id = st.session_state.get(
    "candidate_results_job_id"
)

if results and results_job_id == selected_job_id:
    st.divider()
    st.subheader("3. Candidate Ranking")

    top_candidate = results[0]
    a, b, c = st.columns(3)

    a.metric("Candidates", len(results))
    b.metric(
        "Top Candidate",
        top_candidate.get("name", "Unknown"),
    )
    c.metric(
        "Top Match Score",
        f"{number(top_candidate.get('final_score')):.2f}%",
    )

    report_rows = []

    for rank, candidate in enumerate(results, start=1):
        report_rows.append({
            "Rank": rank,
            "Candidate": candidate.get("name", "Unknown"),
            "Text Similarity (%)": number(
                candidate.get("similarity")
            ),
            "Skill Coverage (%)": number(
                candidate.get("skill_coverage")
            ),
            "Final Match Score (%)": number(
                candidate.get("final_score")
            ),
            "Matched Skills": (
                as_text_list(candidate.get("matched_skills"))
                or "None"
            ),
            "Missing Skills": (
                as_text_list(candidate.get("missing_skills"))
                or "None"
            ),
        })

    report_df = pd.DataFrame(report_rows)

    st.dataframe(
        report_df,
        use_container_width=True,
        hide_index=True,
    )

    # -----------------------------------
    # Shortlist Candidates
    # -----------------------------------
    st.subheader("4. Shortlist Candidates")
    st.caption(
        "Shortlisting is saved to data/shortlist.csv "
        "and counted on the Company Dashboard."
    )

    saved = load_shortlist()

    for rank, candidate in enumerate(results, start=1):
        candidate_name = str(
            candidate.get("name", "Unknown")
        ).strip()

        score = number(candidate.get("final_score"))

        duplicate = (
            saved["Job ID"].astype(str).str.strip()
            .eq(str(selected_job_id))
            & saved["Candidate Name"]
            .astype(str)
            .str.strip()
            .str.casefold()
            .eq(candidate_name.casefold())
        ).any()

        left, middle, right = st.columns([3, 1, 1.5])

        left.write(f"**{rank}. {candidate_name}**")
        middle.write(f"**{score:.2f}%** match")

        if duplicate:
            right.button(
                "✓ Shortlisted",
                key=f"shortlisted_{selected_index}_{rank}",
                disabled=True,
            )

        elif right.button(
            "＋ Shortlist",
            key=f"shortlist_{selected_index}_{rank}",
        ):
            try:
                if save_shortlist(
                    selected_job_id,
                    candidate_name,
                    score,
                ):
                    st.success(
                        f"{candidate_name} was added to the shortlist."
                    )
                else:
                    st.info(
                        f"{candidate_name} is already shortlisted "
                        "for this job."
                    )

                st.rerun()

            except Exception as exc:
                st.error(f"Could not save shortlist: {exc}")

    # -----------------------------------
    # Candidate Details
    # -----------------------------------
    st.subheader("5. Candidate Details")

    for candidate in results:
        name = str(
            candidate.get("name", "Unknown Candidate")
        )

        with st.expander(name):
            x, y, z = st.columns(3)

            x.metric(
                "Text Similarity",
                f"{number(candidate.get('similarity')):.2f}%",
            )
            y.metric(
                "Skill Coverage",
                f"{number(candidate.get('skill_coverage')):.2f}%",
            )
            z.metric(
                "Final Match Score",
                f"{number(candidate.get('final_score')):.2f}%",
            )

            st.write(
                "**Matched Skills:**",
                as_text_list(
                    candidate.get("matched_skills")
                ) or "None",
            )

            st.write(
                "**Missing Skills:**",
                as_text_list(
                    candidate.get("missing_skills")
                ) or "None",
            )

    # -----------------------------------
    # Ranking Chart
    # -----------------------------------
    st.subheader("6. Candidate Ranking Chart")

    st.bar_chart(
        report_df[
            ["Candidate", "Final Match Score (%)"]
        ].set_index("Candidate")
    )

    # -----------------------------------
    # Download Report
    # -----------------------------------
    st.subheader("7. Download Matching Report")

    st.download_button(
        label="⬇️ Download Candidate Report (CSV)",
        data=report_df.to_csv(index=False).encode("utf-8"),
        file_name="job_candidate_matching_report.csv",
        mime="text/csv",
    )

    st.caption(
        "Matching scores are preliminary indicators. Review candidate "
        "qualifications and use consistent, job-related criteria "
        "before making employment decisions."
    )

elif results and results_job_id != selected_job_id:
    st.info(
        "Select the job used for the last analysis to view its results, "
        "or run matching again for this job."
    )
