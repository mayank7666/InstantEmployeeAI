
import html
import textwrap
from pathlib import Path

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Instant Employee | Company Dashboard",
    page_icon="💼",
    layout="wide",
)

# -----------------------------------
# Paths
# -----------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

JOBS_FILE = DATA_DIR / "jobs.csv"
SHORTLIST_FILE = DATA_DIR / "shortlist.csv"

SHORTLIST_COLUMNS = [
    "Job ID",
    "Candidate Name",
    "Match Score",
    "Shortlisted On",
]


# -----------------------------------
# Load Data
# -----------------------------------
def load_jobs():
    if not JOBS_FILE.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(JOBS_FILE)
        df.columns = df.columns.astype(str).str.strip()
        return df.fillna("")
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


def find_column(df, possible_names):
    for column in df.columns:
        if str(column).strip().lower() in possible_names:
            return column
    return None


def safe_text(value, default="Not specified"):
    value = str(value).strip()

    if not value or value.lower() in {"nan", "none"}:
        value = default

    return html.escape(value)


# Load the latest CSV data on each rerun
jobs_df = load_jobs()
shortlist_df = load_shortlist()

title_col = find_column(
    jobs_df, {"job title", "title", "job_title"}
)
department_col = find_column(
    jobs_df, {"department"}
)
description_col = find_column(
    jobs_df,
    {"description", "job description", "job_description"},
)
skills_col = find_column(
    jobs_df,
    {"required skills", "required_skills", "skills"},
)
status_col = find_column(
    jobs_df, {"status", "job status", "job_status"}
)
work_mode_col = find_column(
    jobs_df, {"work mode", "work_mode"}
)
minimum_budget_col = find_column(
    jobs_df,
    {"minimum budget", "min budget", "minimum_budget"},
)
maximum_budget_col = find_column(
    jobs_df,
    {"maximum budget", "max budget", "maximum_budget"},
)


# -----------------------------------
# Styling
# -----------------------------------
st.markdown(
    """
    <style>
    .stApp {
        background: #f4f7fc;
        color: #172b4d;
    }

    .main .block-container {
        max-width: 1500px;
        padding-top: 1.8rem;
        padding-bottom: 2rem;
    }

    /* Hide Streamlit default page navigation */
    [data-testid="stSidebarNav"] {
        display: none !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0b1930, #152b4c);
    }

    /* Welcome banner */
    .dashboard-hero {
        background: linear-gradient(
            110deg, #dceaff, #f1f6ff, #e1edff
        );
        border: 1px solid #d4e3ff;
        border-radius: 20px;
        padding: 34px 36px;
        margin-bottom: 30px;
        box-shadow: 0 8px 24px rgba(34, 83, 150, 0.08);
        overflow: hidden;
    }

    .hero-kicker {
        color: #1765d1;
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 1.5px;
        margin-bottom: 12px;
    }

    .dashboard-hero h1 {
        font-size: clamp(27px, 3vw, 40px);
        line-height: 1.2;
        color: #10274a;
        margin: 0 0 14px;
        font-weight: 800;
    }

    .dashboard-hero h1 span {
        color: #1263df;
    }

    .dashboard-hero p {
        color: #526987;
        font-size: 16px;
        line-height: 1.7;
        margin: 0;
        max-width: 800px;
    }

    .hero-decoration {
        float: right;
        font-size: 76px;
        margin: 8px 15px 0 20px;
    }

    /* Metric cards */
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e1e9f5;
        border-radius: 16px;
        padding: 21px;
        min-height: 125px;
        box-shadow: 0 5px 18px rgba(28, 55, 90, 0.05);
    }

    div[data-testid="stMetric"] label {
        color: #586d8d !important;
        opacity: 1 !important;
    }

    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #14294b !important;
        font-size: 31px;
        font-weight: 750;
    }

    /* Recent job cards */
    .job-card {
        background: #ffffff;
        border: 1px solid #dce7f5;
        border-radius: 15px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 4px 12px rgba(28, 55, 90, 0.04);
        overflow-wrap: anywhere;
    }

    .job-card h3 {
        color: #162c4f;
        font-size: 19px;
        margin: 0 0 10px;
    }

    .job-card p {
        color: #425e82;
        line-height: 1.6;
        margin: 7px 0;
        font-size: 14px;
    }

    .status-badge {
        display: inline-block;
        color: #087d4c;
        background: #d8f9e9;
        padding: 5px 12px;
        border-radius: 18px;
        font-size: 12px;
        font-weight: 700;
    }

    /* Recruitment information cards */
    .insight-card {
        background: linear-gradient(120deg, #d5e6ff, #c7ddff);
        border: 1px solid #a4c6f7;
        border-radius: 14px;
        padding: 18px;
        margin-bottom: 12px;
        color: #123b70 !important;
        line-height: 1.7;
        font-size: 14px;
    }

    .insight-card strong {
        display: block;
        color: #0b2f63 !important;
        font-size: 16px;
        margin-bottom: 4px;
    }

    /* Sidebar navigation buttons */
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

    /* Main action links: dark text, light blue background */
    [data-testid="stMain"] div[data-testid="stPageLink"] a {
        background: #dce8f8 !important;
        color: #123b70 !important;
        border: 1px solid #91b5e5 !important;
        border-radius: 12px !important;
        padding: 12px 16px !important;
        font-weight: 750 !important;
        opacity: 1 !important;
        text-decoration: none !important;
    }

    [data-testid="stMain"] div[data-testid="stPageLink"] a * {
        color: #123b70 !important;
        -webkit-text-fill-color: #123b70 !important;
        opacity: 1 !important;
    }

    [data-testid="stMain"] div[data-testid="stPageLink"] a:hover {
        background: #c3d8f5 !important;
        border-color: #648fce !important;
    }

    footer {
        visibility: hidden;
    }

    @media (max-width: 800px) {
        .dashboard-hero {
            padding: 24px;
        }

        .hero-decoration {
            font-size: 42px;
            margin-right: 0;
        }

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
# Welcome Banner
# -----------------------------------
st.markdown(
    """
    <div class="dashboard-hero">
        <div class="hero-decoration">🧑🏻‍💻</div>
        <div class="hero-kicker">WELCOME BACK</div>
        <h1>Welcome to <span>Instant Employee</span></h1>
        <p>
            Manage job postings, review candidate profiles, and coordinate
            recruitment activities from one place.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------
# Company Overview
# -----------------------------------
st.header("Company Overview")
st.caption("Key metrics and recruitment status at a glance.")

total_jobs = len(jobs_df)

if status_col and not jobs_df.empty:
    active_jobs = int(
        jobs_df[status_col]
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["active", "open", "published"])
        .sum()
    )
else:
    active_jobs = total_jobs

if "Candidate Name" in shortlist_df.columns:
    names = (
        shortlist_df["Candidate Name"]
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .str.casefold()
    )
    shortlisted_talents = names.nunique()
else:
    shortlisted_talents = 0

c1, c2, c3, c4 = st.columns(4, gap="medium")

c1.metric("💼 Total Jobs", total_jobs)
c2.metric("💚 Active Jobs", active_jobs)
c3.metric("👥 Shortlisted Talents", int(shortlisted_talents))
c4.metric(
    "📋 Recruitment Status",
    "Active" if total_jobs else "Pending",
)


# -----------------------------------
# Recent Jobs and Recruitment Activities
# -----------------------------------
st.write()

left_col, right_col = st.columns([1.45, 1], gap="large")

with left_col:
    st.subheader("📋 Recent Jobs")

    if jobs_df.empty:
        st.info(
            "No job postings are available yet. "
            "Open Job Posting to add a position."
        )
        st.caption(f"Jobs CSV path: {JOBS_FILE}")

    elif not title_col:
        st.warning(
            "The Job Title column was not found in data/jobs.csv."
        )
        st.write("Columns found:", ", ".join(map(str, jobs_df.columns)))

    else:
        recent_jobs = jobs_df.tail(5).iloc[::-1]

        for _, job in recent_jobs.iterrows():
            job_title = safe_text(
                job[title_col], "Untitled Position"
            )

            department = (
                safe_text(job[department_col])
                if department_col else "Not specified"
            )

            skills = (
                safe_text(job[skills_col])
                if skills_col else "Not specified"
            )

            description = (
                safe_text(
                    job[description_col],
                    "Description not available",
                )
                if description_col
                else "Description not available"
            )

            status = (
                safe_text(job[status_col], "Active")
                if status_col else "Active"
            )

            work_mode = (
                safe_text(job[work_mode_col])
                if work_mode_col else "Not specified"
            )

            minimum_budget = (
                str(job[minimum_budget_col]).strip()
                if minimum_budget_col else ""
            )

            maximum_budget = (
                str(job[maximum_budget_col]).strip()
                if maximum_budget_col else ""
            )

            if minimum_budget or maximum_budget:
                budget_text = (
                    f"{safe_text(minimum_budget, 'Not specified')} - "
                    f"{safe_text(maximum_budget, 'Not specified')}"
                )
            else:
                budget_text = "Not specified"

            card_html = textwrap.dedent(
                f"""
                <div class="job-card">
                    <h3>{job_title}</h3>
                    <p><strong>Department:</strong> {department}</p>
                    <p><strong>Required Skills:</strong> {skills}</p>
                    <p><strong>Work Mode:</strong> {work_mode}</p>
                    <p><strong>Monthly Budget:</strong> ₹{budget_text}</p>
                    <p>{description}</p>
                    <span class="status-badge">{status}</span>
                </div>
                """
            )

            st.markdown(card_html, unsafe_allow_html=True)


with right_col:
    st.subheader("📁 Recruitment Activities")

    st.markdown(
        """
        <div class="insight-card">
            <strong>💼 Job Posting</strong>
            Create and maintain job vacancies, define department,
            required skills, work mode, and budget.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.page_link(
        "pages/2_Job_Posting.py",
        label="📋 Open Job Posting",
        use_container_width=True,
    )

    st.markdown(
        """
        <div class="insight-card">
            <strong>🔎 Candidate Management</strong>
            Review candidate profiles against posted job requirements
            and examine matching results.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.page_link(
        "pages/3_Match_Candidates.py",
        label="🔎 Open Candidate Matching",
        use_container_width=True,
    )

    st.write("")
    st.subheader("⭐ Recent Shortlists")

    if shortlist_df.empty:
        st.caption("No candidates have been shortlisted yet.")

    else:
        for _, row in shortlist_df.tail(5).iloc[::-1].iterrows():
            candidate_name = safe_text(
                row.get("Candidate Name", "Unknown")
            )
            match_score = safe_text(
                row.get("Match Score", "N/A")
            )
            shortlisted_on = safe_text(
                row.get("Shortlisted On", "Date not recorded")
            )

            st.write(f"**{candidate_name}**")
            st.caption(
                f"Match score: {match_score}% · {shortlisted_on}"
            )

    st.caption(
        "Matching scores support recruitment review. "
        "Final hiring decisions should be made by the recruitment team."
    )


# -----------------------------------
# Footer
# -----------------------------------
st.divider()
st.caption("Instant Employee | Company Dashboard")
