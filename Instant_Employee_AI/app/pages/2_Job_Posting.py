
from pathlib import Path
from datetime import date
import uuid
import requests

import pandas as pd
import streamlit as st

# =========================================
# PATHS AND PAGE CONFIGURATION
# =========================================
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
JOBS_FILE = DATA_DIR / "jobs.csv"
API_BASE_URL = "https://instant-employee-api.onrender.com"

DATA_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(
    page_title="Job Posting | Instant Employee",
    page_icon="💼",
    layout="wide"
)

JOB_COLUMNS = [
    "Job ID",
    "Job Title",
    "Department",
    "Description",
    "Required Skills",
    "Minimum Budget",
    "Maximum Budget",
    "Work Mode",
    "Timezone",
    "Posted On",
    "Company Name"
]


# =========================================
# LOAD AND SAVE JOBS
# =========================================
def load_jobs():
    if not JOBS_FILE.exists():
        return pd.DataFrame(columns=JOB_COLUMNS)

    try:
        df = pd.read_csv(JOBS_FILE).fillna("")

        for column in JOB_COLUMNS:
            if column not in df.columns:
                df[column] = ""

        return df[JOB_COLUMNS]

    except (pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame(columns=JOB_COLUMNS)


def save_jobs(df):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df[JOB_COLUMNS].to_csv(JOBS_FILE, index=False)


# =========================================
# STYLING
# =========================================
st.markdown("""
<style>
.stApp {
    background: #f3f7fd;
    color: #17365f;
}

.main .block-container {
    max-width: 1500px;
    padding-top: 1.5rem;
    padding-bottom: 2rem;
}

/* Hide default navigation */
[data-testid="stSidebarNav"] {
    display: none !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0b1930, #152b4c);
}

/* Banner */
.job-hero {
    background: linear-gradient(115deg, #dceaff, #f0edff, #d8e8ff);
    border: 1px solid #d0e1ff;
    border-radius: 20px;
    padding: 32px;
    margin-bottom: 28px;
    box-shadow: 0 7px 24px rgba(30, 75, 140, 0.07);
}

.job-hero h1 {
    color: #12315f;
    font-size: 36px;
    font-weight: 800;
    margin: 0 0 12px 0;
}

.job-hero p {
    color: #42648e;
    font-size: 16px;
    line-height: 1.7;
    margin: 0;
}

/* Form */
.form-panel {
    background: #ffffff;
    border: 1px solid #d7e5fb;
    border-radius: 18px;
    padding: 24px;
    margin-bottom: 25px;
    box-shadow: 0 5px 18px rgba(28, 55, 90, 0.04);
}

/* Headings and labels */
.stApp h1,
.stApp h2,
.stApp h3 {
    color: #17365f;
}

.stApp label,
.stApp [data-testid="stWidgetLabel"],
.stApp [data-testid="stWidgetLabel"] p {
    color: #17365f !important;
    font-weight: 600 !important;
}

/* Text fields */
.stApp input,
.stApp textarea {
    color: #17365f !important;
    -webkit-text-fill-color: #17365f !important;
    background: #ffffff !important;
    border-color: #bfd2ef !important;
}

/* Dropdown selected values */
.stApp [data-baseweb="select"] > div {
    background: #ffffff !important;
    border-color: #bfd2ef !important;
}

.stApp [data-baseweb="select"] input,
.stApp [data-baseweb="select"] div,
.stApp [data-baseweb="select"] span {
    color: #17365f !important;
    -webkit-text-fill-color: #17365f !important;
}

/* Dropdown menu */
[data-baseweb="popover"],
[data-baseweb="menu"] {
    background: #ffffff !important;
}

[data-baseweb="menu"] *,
[data-baseweb="popover"] * {
    color: #17365f !important;
    -webkit-text-fill-color: #17365f !important;
}

/* Buttons */
div.stButton > button,
div.stFormSubmitButton > button,
div.stDownloadButton > button {
    background: #1765d1 !important;
    color: #ffffff !important;
    border: 1px solid #1765d1 !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    min-height: 42px;
}

div.stButton > button:hover,
div.stFormSubmitButton > button:hover,
div.stDownloadButton > button:hover {
    background: #104da8 !important;
    border-color: #104da8 !important;
}

/* Metric boxes */
.posted-metric {
    background: #ffffff;
    border: 1px solid #bcd3f5;
    border-radius: 15px;
    padding: 18px;
    min-height: 105px;
    box-shadow: 0 4px 14px rgba(25, 65, 120, 0.07);
}

.posted-metric-title {
    color: #234c7e;
    font-size: 15px;
    font-weight: 700;
}

.posted-metric-value {
    color: #102f5c;
    font-size: 31px;
    font-weight: 800;
    margin-top: 8px;
}

/* Sidebar page links */
[data-testid="stSidebar"] div[data-testid="stPageLink"] a {
    background: #dce9ff !important;
    color: #123b70 !important;
    border: 1px solid #b5cdf5 !important;
    border-radius: 12px !important;
    padding: 12px 14px !important;
    font-weight: 700 !important;
}

[data-testid="stSidebar"] div[data-testid="stPageLink"] a * {
    color: #123b70 !important;
    -webkit-text-fill-color: #123b70 !important;
}

@media (max-width: 800px) {
    .job-hero {
        padding: 22px;
    }

    .job-hero h1 {
        font-size: 28px;
    }
}
</style>
""", unsafe_allow_html=True)


# =========================================
# SIDEBAR
# =========================================
with st.sidebar:
    st.markdown("""
    <div style="padding:12px 0 20px 0;">
        <div style="font-size:25px;">👥</div>
        <div style="font-size:22px;font-weight:800;color:white;">
            Instant Employee
        </div>
        <div style="font-size:12px;color:#b7c8e3;">
            Recruitment Dashboard
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.page_link(
        "pages/4_Employee_Dashboard.py",
        label="🏠 Company Dashboard",
        use_container_width=True
    )

    st.page_link(
        "pages/2_Job_Posting.py",
        label="💼 Job Posting",
        use_container_width=True
    )

    st.page_link(
        "pages/3_Match_Candidates.py",
        label="🔎 Candidate Matching",
        use_container_width=True
    )

    st.divider()
    st.caption("Your Company · Recruiter Panel")


# Company pages require a company-role account created through the dashboard.
if not st.session_state.get("company_logged_in") or not st.session_state.get("company_api_token"):
    st.warning("Please log in to the Company Dashboard before posting a job.")
    st.page_link("pages/4_Employee_Dashboard.py", label="← Company Login / Dashboard", use_container_width=True)
    st.stop()

def create_api_job(payload):
    try:
        response = requests.post(
            f"{API_BASE_URL}/jobs",
            headers={"Authorization": f"Bearer {st.session_state.company_api_token}"},
            json=payload,
            timeout=(8, 30),
        )
        try:
            data = response.json()
        except ValueError:
            data = {}
        if not response.ok:
            return None, str(data.get("detail", f"API request failed (HTTP {response.status_code})"))
        return data, None
    except requests.RequestException:
        return None, "The API is currently unavailable. The job was not saved to the database; please try again shortly."

# =========================================
# JOB POSTING BANNER
# =========================================
BANNER_FILE = PROJECT_ROOT / "assets" / "Modern Job Posting Banner.png"

hero_text_col, hero_image_col = st.columns([1.15, 0.85], gap="large")
with hero_text_col:
    st.markdown("""
    <div class="job-hero">
        <div style="font-size:12px;letter-spacing:1.5px;text-transform:uppercase;font-weight:800;color:#2870c7;margin-bottom:10px;">
            INSTANT EMPLOYEE · RECRUITER WORKSPACE
        </div>
        <h1>💼 Job Posting</h1>
        <p>
            Create and manage job vacancies, define required skills,
            set monthly budgets, and find the right talent for your team.
        </p>
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:18px;">
            <span style="background:#e3eeff;color:#2456a6;padding:7px 11px;border-radius:20px;font-size:12px;font-weight:700;">✦ Create roles</span>
            <span style="background:#e0f7ed;color:#137b5b;padding:7px 11px;border-radius:20px;font-size:12px;font-weight:700;">✓ Define skills</span>
            <span style="background:#fff0d7;color:#95610d;padding:7px 11px;border-radius:20px;font-size:12px;font-weight:700;">₹ Set budget</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
with hero_image_col:
    if BANNER_FILE.exists():
        st.image(str(BANNER_FILE), caption="Create the next opportunity for your team", use_container_width=True)
    else:
        st.markdown("""
        <div class="job-hero" style="height:100%;display:flex;flex-direction:column;justify-content:center;">
            <div style="font-size:56px;">💼 ✦</div>
            <h2 style="color:#12315f;">Build your team</h2>
            <p>Clear roles. The right skills. Better matches.</p>
        </div>
        """, unsafe_allow_html=True)


# =========================================
# CREATE A NEW JOB
# =========================================
st.subheader("✨ Create a New Job")
st.caption(
    "Fill in the job details below. Fields marked with * are required."
)

with st.form("job_posting_form", clear_on_submit=True):
    left_col, right_col = st.columns(2, gap="medium")

    with left_col:
        job_title = st.text_input(
            "Job Title *",
            placeholder="e.g. Machine Learning Engineer"
        )

        department = st.selectbox(
            "Department *",
            [
                "Artificial Intelligence",
                "Data Analytics",
                "Software Development",
                "Data Science",
                "Human Resources",
                "Marketing",
                "Finance",
                "Other"
            ]
        )

        minimum_budget = st.number_input(
            "Minimum Monthly Budget (INR) *",
            min_value=0,
            value=15000,
            step=1000
        )

        work_mode = st.selectbox(
            "Work Mode",
            ["Remote", "Hybrid", "On-site"]
        )

    with right_col:
        required_skills = st.text_input(
            "Required Skills *",
            placeholder="Python, SQL, Machine Learning"
        )

        maximum_budget = st.number_input(
            "Maximum Monthly Budget (INR) *",
            min_value=0,
            value=30000,
            step=1000
        )

        timezone = st.selectbox(
            "Preferred Timezone",
            [
                "IST (India)",
                "UTC",
                "EST (US Eastern)",
                "PST (US Pacific)",
                "GMT",
                "CET (Central Europe)"
            ]
        )

    description = st.text_area(
        "Job Description *",
        placeholder="Describe responsibilities and qualifications...",
        height=130
    )

    submitted = st.form_submit_button(
        "➕ Post Job",
        use_container_width=True
    )


# =========================================
# SAVE NEW JOB
# =========================================
if submitted:
    if not job_title.strip():
        st.error("Please enter the Job Title.")

    elif not required_skills.strip():
        st.error("Please enter the Required Skills.")

    elif not description.strip():
        st.error("Please enter the Job Description.")

    elif minimum_budget > maximum_budget:
        st.error("Minimum budget cannot exceed maximum budget.")

    else:
        api_payload = {
            "title": job_title.strip(),
            "department": department,
            "description": description.strip(),
            "required_skills": required_skills.strip(),
            "min_budget": int(minimum_budget),
            "max_budget": int(maximum_budget),
            "work_mode": work_mode,
            "timezone": timezone,
        }
        created_job, api_error = create_api_job(api_payload)

        if api_error:
            st.error("The job could not be saved to the database: " + api_error)
            st.info("The job was not saved to the CSV to prevent a mismatch between the public listing and the company database.")
        else:
            current_jobs = load_jobs()
            new_job = {
                "Job ID": str(created_job["id"]),
                "Job Title": job_title.strip(),
                "Department": department,
                "Description": description.strip(),
                "Required Skills": required_skills.strip(),
                "Minimum Budget": minimum_budget,
                "Maximum Budget": maximum_budget,
                "Work Mode": work_mode,
                "Timezone": timezone,
                "Posted On": date.today().isoformat(),
                "Company Name": st.session_state.get("company_email", "Company"),
            }
            updated_jobs = pd.concat(
                [current_jobs, pd.DataFrame([new_job])],
                ignore_index=True
            )
            try:
                save_jobs(updated_jobs)
                st.success(f"Job posted to the database: {job_title}")
                st.rerun()
            except OSError as error:
                st.error(f"The job was saved to the database, but the public CSV could not be updated: {error}")
                st.warning("The job will remain on the dashboard. CSV synchronization must be fixed to show it in the public job listing.")


# =========================================
# POSTED JOBS - INTERACTIVE BOXES
# =========================================
st.divider()
st.subheader("📋 Posted Jobs")
st.caption("Choose a category to explore your job vacancies.")

jobs_df = load_jobs()

if jobs_df.empty:
    st.info("No jobs posted yet. Create your first job above.")

else:
    for column in [
        "Department", "Work Mode", "Description", "Required Skills"
    ]:
        if column not in jobs_df.columns:
            jobs_df[column] = ""

    jobs_df = jobs_df.fillna("")

    total_jobs = len(jobs_df)

    departments = sorted(
        jobs_df["Department"]
        .replace("", "Not specified")
        .astype(str)
        .unique()
        .tolist()
    )

    remote_jobs = int(
        jobs_df["Work Mode"]
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("remote")
        .sum()
    )

    if "job_category_filter" not in st.session_state:
        st.session_state.job_category_filter = "Total Jobs"

    # Three clickable metric boxes
    col1, col2, col3 = st.columns(3, gap="medium")

    with col1:
        st.markdown(f"""
        <div class="posted-metric">
            <div class="posted-metric-title">💼 Total Jobs</div>
            <div class="posted-metric-value">{total_jobs}</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button(
            "Select Job Type",
            key="select_total_jobs",
            use_container_width=True
        ):
            st.session_state.job_category_filter = "Total Jobs"

    with col2:
        st.markdown(f"""
        <div class="posted-metric">
            <div class="posted-metric-title">🏢 Departments</div>
            <div class="posted-metric-value">{len(departments)}</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button(
            "Select Department",
            key="select_departments",
            use_container_width=True
        ):
            st.session_state.job_category_filter = "Departments"

    with col3:
        st.markdown(f"""
        <div class="posted-metric">
            <div class="posted-metric-title">🌐 Remote Jobs</div>
            <div class="posted-metric-value">{remote_jobs}</div>
        </div>
        """, unsafe_allow_html=True)

        if st.button(
            "Select Work Mode",
            key="select_work_mode",
            use_container_width=True
        ):
            st.session_state.job_category_filter = "Remote Jobs"

    st.write("")

    # -------------------------------------
    # Related Dropdown Options
    # -------------------------------------
    category = st.session_state.job_category_filter
    display_df = jobs_df.copy()

    if category == "Total Jobs":
        st.markdown("### 💼 Job Type Options")

        job_option = st.selectbox(
            "Choose which jobs to view",
            [
                "All Jobs",
                "Jobs with Description",
                "Jobs with Required Skills"
            ],
            key="total_jobs_dropdown"
        )

        if job_option == "Jobs with Description":
            display_df = display_df[
                display_df["Description"].astype(str).str.strip().ne("")
            ]

        elif job_option == "Jobs with Required Skills":
            display_df = display_df[
                display_df["Required Skills"].astype(str).str.strip().ne("")
            ]

    elif category == "Departments":
        st.markdown("### 🏢 Department Options")

        selected_department = st.selectbox(
            "Choose Department",
            ["All Departments"] + departments,
            key="department_dropdown"
        )

        if selected_department != "All Departments":
            display_df = display_df[
                display_df["Department"]
                .replace("", "Not specified")
                .astype(str)
                .eq(selected_department)
            ]

    elif category == "Remote Jobs":
        st.markdown("### 🌐 Work Mode Options")

        # Only these three options appear in this dropdown
        selected_mode = st.selectbox(
            "Choose Work Mode",
            ["Remote", "Hybrid", "On-site"],
            key="work_mode_dropdown"
        )

        display_df = display_df[
            display_df["Work Mode"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq(selected_mode.lower())
        ]

    # Search within the selected category
    search_text = st.text_input(
        "🔎 Search by job title, skill or department",
        placeholder="Enter a job title or skill...",
        key="interactive_job_search"
    )

    if search_text.strip():
        search_mask = display_df.astype(str).apply(
            lambda column: column.str.contains(
                search_text.strip(),
                case=False,
                na=False,
                regex=False
            )
        ).any(axis=1)

        display_df = display_df[search_mask]

    st.caption(f"Showing {len(display_df)} job(s)")

    if display_df.empty:
        st.warning("No jobs found for the selected options.")

    else:
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )

        st.download_button(
            "⬇️ Download Selected Jobs CSV",
            data=display_df.to_csv(index=False).encode("utf-8"),
            file_name="selected_jobs.csv",
            mime="text/csv",
            use_container_width=True
        )


# =========================================
# FOOTER
# =========================================
st.divider()
st.caption("Instant Employee | Job Posting")
