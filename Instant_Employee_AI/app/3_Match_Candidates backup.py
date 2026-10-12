from pypdf import PdfReader
import sys
import html
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st
from pypdf import PdfReader

# -----------------------------------
# Project Paths
# -----------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
JOBS_FILE = DATA_DIR / "jobs.csv"
SHORTLIST_FILE = DATA_DIR / "shortlist.csv"

DATA_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(PROJECT_ROOT))

from src.matching_engine import match_candidates


# -----------------------------------
# Page Configuration
# -----------------------------------

st.set_page_config(
    page_title="Find Talent | Instant Employee",
    page_icon="👥",
    layout="wide"
)


# -----------------------------------
# CSS Styling
# -----------------------------------

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #f8fbff, #edf4ff);
    color: #14284d;
}

.main .block-container {
    max-width: 1500px;
    padding: 1.5rem 2rem 3rem;
}

/* Hero banner */
.match-hero {
    background: linear-gradient(110deg, #e0efff, #f0edff, #d7e8ff);
    border: 1px solid #d2e4ff;
    border-radius: 22px;
    padding: 30px;
    margin-bottom: 28px;
    box-shadow: 0 8px 25px rgba(37, 99, 235, 0.08);
}

.match-hero h1 {
    color: #102c60;
    font-size: 38px;
    margin: 0 0 10px 0;
}

.match-hero p {
    color: #405b86;
    font-size: 17px;
    line-height: 1.6;
    margin: 0;
}

.section-title {
    color: #102c60;
    font-size: 25px;
    font-weight: 750;
    margin: 18px 0 5px 0;
}

.section-subtitle {
    color: #52698c;
    font-size: 15px;
    margin-bottom: 18px;
}

/* Feature chips */
.feature-chip {
    display: inline-block;
    background: #e5efff;
    color: #1d4ed8;
    border: 1px solid #c9ddff;
    padding: 8px 12px;
    border-radius: 22px;
    font-size: 13px;
    font-weight: 650;
    margin: 4px 5px 4px 0;
}

/* Tip panel */
.tip-panel {
    background: linear-gradient(120deg, #e4f0ff, #f2f4ff);
    border: 1px solid #d0e2ff;
    padding: 20px;
    border-radius: 16px;
    color: #234477;
    margin-top: 12px;
}

.tip-panel strong {
    color: #17365f;
}

/* Metric cards */
div[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #dce8fa;
    border-radius: 14px;
    padding: 16px;
    box-shadow: 0 4px 14px rgba(30, 64, 175, 0.05);
}

div[data-testid="stMetric"] label,
div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #16366a !important;
    opacity: 1 !important;
}

div[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-size: 27px !important;
}

/* Upload area */
div[data-testid="stFileUploader"] {
    background: #f0f7ff !important;
    border: 1px dashed #5595ff !important;
    border-radius: 16px !important;
    padding: 12px !important;
}

div[data-testid="stFileUploader"] section {
    background: transparent !important;
}

div[data-testid="stFileUploader"] button {
    background: #1769ee !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 9px !important;
    font-weight: 700 !important;
}

/* Selected PDF filename */
div[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] {
    background-color: #ffffff !important;
    border: 1px solid #b8d0f5 !important;
    border-radius: 10px !important;
    padding: 10px !important;
    margin-top: 8px !important;
}

div[data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] *,
div[data-testid="stFileUploader"] [data-testid="stFileUploaderFileName"] {
    color: #17365f !important;
    opacity: 1 !important;
    font-weight: 600 !important;
}

div[data-testid="stFileUploader"] small,
div[data-testid="stFileUploader"] section span {
    color: #405b86 !important;
}

/* Data table container */
div[data-testid="stDataFrame"] {
    background-color: #ffffff !important;
    border: 1px solid #b8cff0 !important;
    border-radius: 12px !important;
    overflow: hidden !important;
}

div[data-testid="stDataFrame"] iframe {
    background-color: #ffffff !important;
}

/* Alert and information boxes */
div[data-testid="stAlert"] {
    background-color: #e7f0ff !important;
    border: 1px solid #b8d0f5 !important;
    border-radius: 10px !important;
}

div[data-testid="stAlert"] p,
div[data-testid="stAlert"] span {
    color: #17365f !important;
    opacity: 1 !important;
}

/* General buttons */
div.stButton > button {
    background-color: #e0f2e8;
    color: #14532d !important;
    border: 1px solid #86c9a0;
    border-radius: 10px;
    font-weight: 700;
    min-height: 42px;
    opacity: 1 !important;
}

div.stButton > button:hover {
    background-color: #166534 !important;
    color: #ffffff !important;
    border-color: #166534 !important;
}

/* Find Best Candidates button */
div.stButton > button[kind="primary"] {
    background: linear-gradient(90deg, #7048e8, #087cf5) !important;
    color: #ffffff !important;
    border: none !important;
    min-height: 48px;
}

div.stButton > button[kind="primary"]:hover {
    background: linear-gradient(90deg, #6032dc, #075fca) !important;
    color: #ffffff !important;
}

/* CSV download button */
div[data-testid="stDownloadButton"] button {
    background-color: #1d4ed8 !important;
    color: #ffffff !important;
    border: 1px solid #1d4ed8 !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    opacity: 1 !important;
}

div[data-testid="stDownloadButton"] button:hover {
    background-color: #153eaa !important;
    color: #ffffff !important;
    border-color: #153eaa !important;
}

/* Expanders */
div[data-testid="stExpander"] {
    background-color: #ffffff !important;
    border: 1px solid #c7d9f5 !important;
    border-radius: 12px !important;
}

div[data-testid="stExpander"] summary,
div[data-testid="stExpander"] summary span,
div[data-testid="stExpander"] summary p {
    color: #17365f !important;
    font-weight: 600 !important;
}

/* Regular page text */
.stMarkdown p,
.stMarkdown label {
    color: #243b60;
}

div[data-testid="stPageLink"] a {
    color: #173b78 !important;
    font-weight: 700 !important;
}

hr {
    border-color: #dce7f8;
}
</style>
""", unsafe_allow_html=True)


# -----------------------------------
# Constants
# -----------------------------------

SHORTLIST_COLUMNS = [
    "Job ID",
    "Candidate Name",
    "Match Score",
    "Shortlisted On"
]


# -----------------------------------
# Helper Functions
# -----------------------------------

def find_column(columns, possible_names):
    for column in columns:
        if column.strip().lower() in possible_names:
            return column
    return None


def load_jobs():
    if not JOBS_FILE.exists():
        return pd.DataFrame()

    try:
        jobs = pd.read_csv(JOBS_FILE).fillna("")
        jobs.columns = jobs.columns.str.strip()
        return jobs
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def load_shortlist():
    if not SHORTLIST_FILE.exists():
        return pd.DataFrame(columns=SHORTLIST_COLUMNS)

    try:
        data = pd.read_csv(SHORTLIST_FILE).fillna("")
        data.columns = data.columns.str.strip()

        for column in SHORTLIST_COLUMNS:
            if column not in data.columns:
                data[column] = ""

        return data[SHORTLIST_COLUMNS]
    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame(columns=SHORTLIST_COLUMNS)


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


def percentage(value):
    score = number(value)
    if 0 <= score <= 1:
        return score * 100
    return score


def save_shortlist(job_id, candidate_name, score):
    current = load_shortlist()

    duplicate = (
        current["Job ID"].astype(str).str.strip().eq(str(job_id).strip())
        & current["Candidate Name"]
        .astype(str).str.strip().str.casefold()
        .eq(str(candidate_name).strip().casefold())
    )

    if duplicate.any():
        return False

    new_row = {
        "Job ID": str(job_id),
        "Candidate Name": str(candidate_name),
        "Match Score": round(float(score), 2),
        "Shortlisted On": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    updated = pd.concat(
        [current, pd.DataFrame([new_row])],
        ignore_index=True
    )

    updated.to_csv(SHORTLIST_FILE, index=False)
    return True


# -----------------------------------
# Header
# -----------------------------------

st.markdown("""
<div class="match-hero">
    <h1>👥 Find Talent</h1>
    <p>
        Discover suitable candidates by comparing resumes
        with your posted job requirements.
        Find stronger matches and simplify recruitment.
    </p>
</div>
""", unsafe_allow_html=True)


# -----------------------------------
# Load Jobs
# -----------------------------------

jobs = load_jobs()

if jobs.empty:
    st.warning("No posted jobs found. Please create a job first.")
    st.page_link(
        "pages/2_Job_Posting.py",
        label="💼 Open Job Posting",
        use_container_width=True
    )
    st.stop()

title_col = find_column(
    jobs.columns, {"job title", "title", "job_title"}
)
description_col = find_column(
    jobs.columns, {"description", "job description", "job_description"}
)
skills_col = find_column(
    jobs.columns, {"required skills", "required_skills", "skills"}
)
job_id_col = find_column(
    jobs.columns, {"job id", "job_id", "id"}
)
department_col = find_column(jobs.columns, {"department"})
work_mode_col = find_column(jobs.columns, {"work mode", "work_mode"})
min_budget_col = find_column(
    jobs.columns, {"minimum budget", "min budget", "minimum_budget"}
)
max_budget_col = find_column(
    jobs.columns, {"maximum budget", "max budget", "maximum_budget"}
)

if not title_col or not description_col or not skills_col:
    st.error(
        "jobs.csv must contain Job Title, Description "
        "and Required Skills columns."
    )
    st.stop()


# -----------------------------------
# Step 1: Select Job
# -----------------------------------

st.markdown(
    '<div class="section-title">🔵 1. Select a Posted Job</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="section-subtitle">'
    'Choose a job from your posted vacancies to find matching candidates.'
    '</div>',
    unsafe_allow_html=True
)


def job_label(index):
    row = jobs.iloc[index]
    return f"{row[title_col]} | {row[skills_col]}"


with st.container(border=True):
    select_col, dept_col, mode_col, budget_col = st.columns(
        [2.3, 1, 1, 1]
    )

    with select_col:
        st.markdown("**💼 Choose Job**")
        selected_index = st.selectbox(
            "Choose job",
            options=list(range(len(jobs))),
            format_func=job_label,
            label_visibility="collapsed",
            key="selected_job_index"
        )

    selected_job = jobs.iloc[selected_index]

    if job_id_col:
        selected_job_id = str(selected_job[job_id_col]).strip()
    else:
        selected_job_id = str(selected_job[title_col]).strip()

    with dept_col:
        st.markdown("**🏢 Department**")
        st.info(
            str(selected_job[department_col])
            if department_col else "Not specified"
        )

    with mode_col:
        st.markdown("**⚙️ Work Mode**")
        st.success(
            str(selected_job[work_mode_col])
            if work_mode_col else "Not specified"
        )

    with budget_col:
        st.markdown("**💰 Monthly Budget**")

        minimum = (
            selected_job[min_budget_col]
            if min_budget_col else "N/A"
        )
        maximum = (
            selected_job[max_budget_col]
            if max_budget_col else "N/A"
        )

        st.markdown(
            f"""
            <div style="
                background:#e7f0ff;
                color:#17365f;
                border:1px solid #b8d0f5;
                border-radius:10px;
                padding:10px;
                font-weight:700;
            ">
                ₹{html.escape(str(minimum))} – ₹{html.escape(str(maximum))}
            </div>
            """,
            unsafe_allow_html=True
        )


with st.expander("View Job Description and Requirements"):
    st.write("**Job Description**")
    st.write(selected_job[description_col])
    st.write("**Required Skills**")
    st.write(selected_job[skills_col])


# -----------------------------------
# Step 2: Upload Resumes
# -----------------------------------

st.markdown(
    '<div class="section-title">🔵 2. Upload Candidate Resumes</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="section-subtitle">'
    'Upload one or more candidate PDF resumes. Scanned PDFs may need OCR.'
    '</div>',
    unsafe_allow_html=True
)

uploaded_files = st.file_uploader(
    "Choose PDF resumes",
    type=["pdf"],
    accept_multiple_files=True,
    key="candidate_resume_upload"
)

if uploaded_files:
    st.markdown("### 📄 Selected Resume Files")

    for file in uploaded_files:
        st.markdown(
            f"""
            <div style="
                background:#ffffff;
                border:1px solid #b8d0f5;
                border-radius:10px;
                padding:12px 16px;
                margin:6px 0;
                color:#17365f;
                font-weight:600;
                overflow-wrap:anywhere;
            ">
                📄 {html.escape(file.name)}
                <span style="color:#64748b;font-weight:400;">
                    &nbsp;({file.size / 1024:.1f} KB)
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )

st.markdown("""
<div>
    <span class="feature-chip">🛡️ PDF Format Only</span>
    <span class="feature-chip">📄 Multiple Files Supported</span>
    <span class="feature-chip">🔎 Resume Text Extraction</span>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="tip-panel">
    <strong>💡 Pro Tip</strong><br>
    Upload resumes that are relevant to the selected job.
    Clear, text-based PDFs generally produce better text extraction.
</div>
""", unsafe_allow_html=True)


# -----------------------------------
# Step 3: Run Matching
# -----------------------------------

st.write("")

if st.button(
    "🚀 Find Best Candidates  →",
    type="primary",
    use_container_width=True
):
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
                        f"{file.name}: No readable text found."
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
                "No readable resumes found. Please check the uploaded PDFs."
            )

        else:
            job_description = (
                f"{selected_job[title_col]}\n"
                f"{selected_job[description_col]}\n"
                f"Required Skills: {selected_job[skills_col]}"
            )

            try:
                with st.spinner("Analyzing resumes and matching skills..."):
                    results = match_candidates(
                        job_description,
                        resumes
                    )

                normalized = []

                for item in results or []:
                    candidate = dict(item)
                    candidate.setdefault("name", "Unknown")

                    similarity = percentage(
                        candidate.get("similarity", 0)
                    )
                    coverage = percentage(
                        candidate.get("skill_coverage", 0)
                    )

                    if candidate.get("final_score") is None:
                        final_score = (similarity + coverage) / 2
                    else:
                        final_score = percentage(
                            candidate.get("final_score")
                        )

                    candidate["similarity"] = similarity
                    candidate["skill_coverage"] = coverage
                    candidate["final_score"] = final_score

                    normalized.append(candidate)

                normalized.sort(
                    key=lambda item: number(item.get("final_score")),
                    reverse=True
                )

                st.session_state["candidate_results"] = normalized
                st.session_state["candidate_results_job_id"] = (
                    selected_job_id
                )

                if normalized:
                    st.success(
                        f"Matching completed for {len(normalized)} candidate(s)."
                    )
                else:
                    st.warning("No matching results were returned.")

            except Exception as exc:
                st.error(f"Matching failed: {exc}")
                st.info(
                    "Check src/matching_engine.py if the matching function "
                    "returns a different result format."
                )


# -----------------------------------
# Step 4: Results
# -----------------------------------

results = st.session_state.get("candidate_results", [])
results_job_id = st.session_state.get("candidate_results_job_id")

if results and results_job_id == selected_job_id:
    st.divider()

    st.markdown(
        '<div class="section-title">🏆 3. Candidate Ranking</div>',
        unsafe_allow_html=True
    )

    top_candidate = results[0]

    col1, col2, col3 = st.columns(3)

    col1.metric("Candidates Analyzed", len(results))
    col2.metric("Top Candidate", top_candidate.get("name", "Unknown"))
    col3.metric(
        "Top Match Score",
        f"{number(top_candidate.get('final_score')):.2f}%"
    )

    report_rows = []

    for rank, candidate in enumerate(results, start=1):
        report_rows.append({
            "Rank": rank,
            "Candidate": candidate.get("name", "Unknown"),
            "Text Similarity (%)": number(candidate.get("similarity")),
            "Skill Coverage (%)": number(candidate.get("skill_coverage")),
            "Final Match Score (%)": number(candidate.get("final_score")),
            "Matched Skills": (
                as_text_list(candidate.get("matched_skills")) or "None"
            ),
            "Missing Skills": (
                as_text_list(candidate.get("missing_skills")) or "None"
            )
        })

    report_df = pd.DataFrame(report_rows)

    st.dataframe(
        report_df,
        use_container_width=True,
        hide_index=True
    )

    # Shortlist
    st.markdown(
        '<div class="section-title">⭐ 4. Shortlist Candidates</div>',
        unsafe_allow_html=True
    )

    saved = load_shortlist()

    for rank, candidate in enumerate(results, start=1):
        candidate_name = str(
            candidate.get("name", "Unknown")
        ).strip()

        score = number(candidate.get("final_score"))

        duplicate = (
            saved["Job ID"].astype(str).str.strip().eq(
                str(selected_job_id).strip()
            )
            & saved["Candidate Name"]
            .astype(str).str.strip().str.casefold()
            .eq(candidate_name.casefold())
        ).any()

        left, middle, right = st.columns([3, 1, 1.5])

        left.write(f"**{rank}. {candidate_name}**")
        middle.write(f"**{score:.2f}%** match")

        if duplicate:
            right.button(
                "✓ Shortlisted",
                key=f"done_{selected_index}_{rank}",
                disabled=True
            )

        elif right.button(
            "＋ Shortlist",
            key=f"shortlist_{selected_index}_{rank}"
        ):
            try:
                if save_shortlist(
                    selected_job_id,
                    candidate_name,
                    score
                ):
                    st.success(
                        f"{candidate_name} added to shortlist."
                    )
                else:
                    st.info("This candidate is already shortlisted.")

                st.cache_data.clear()
                st.rerun()

            except Exception as exc:
                st.error(f"Could not save shortlist: {exc}")

    # Candidate details
    st.markdown(
        '<div class="section-title">📊 5. Candidate Details</div>',
        unsafe_allow_html=True
    )

    for candidate in results:
        with st.expander(
            str(candidate.get("name", "Unknown Candidate"))
        ):
            a, b, c = st.columns(3)

            a.metric(
                "Text Similarity",
                f"{number(candidate.get('similarity')):.2f}%"
            )
            b.metric(
                "Skill Coverage",
                f"{number(candidate.get('skill_coverage')):.2f}%"
            )
            c.metric(
                "Final Score",
                f"{number(candidate.get('final_score')):.2f}%"
            )

            st.write(
                "**Matched Skills:**",
                as_text_list(candidate.get("matched_skills")) or "None"
            )

            st.write(
                "**Missing Skills:**",
                as_text_list(candidate.get("missing_skills")) or "None"
            )

    # Ranking chart
    st.markdown(
        '<div class="section-title">📈 6. Candidate Ranking Chart</div>',
        unsafe_allow_html=True
    )

    st.bar_chart(
        report_df.set_index("Candidate")[["Final Match Score (%)"]]
    )

    # CSV download
    st.markdown(
        '<div class="section-title">⬇️ 7. Download Matching Report</div>',
        unsafe_allow_html=True
    )

    st.download_button(
        "⬇️ Download Candidate Report (CSV)",
        data=report_df.to_csv(index=False).encode("utf-8"),
        file_name="job_candidate_matching_report.csv",
        mime="text/csv"
    )

    st.caption(
        "Match scores are preliminary screening indicators. "
        "Review job-related qualifications before making hiring decisions."
    )

elif results and results_job_id != selected_job_id:
    st.info(
        "Select the job used for the last analysis or run matching again."
    )
