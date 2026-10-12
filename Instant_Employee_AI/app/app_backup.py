
import streamlit as st
import pandas as pd
import sys
from pathlib import Path
from pypdf import PdfReader

# -------------------------------
# Project Path
# -------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.matching_engine import match_candidates


# -------------------------------
# Page Configuration
# -------------------------------

st.set_page_config(
    page_title="AI Resume Screening System",
    page_icon="📊",
    layout="wide"
)

st.title("📊 AI Resume Screening System")
st.write(
    "Upload candidate resumes and compare them with a job description "
    "using AI-based resume matching."
)


# -------------------------------
# Helper Functions
# -------------------------------

def format_skills(skills):
    """Convert skill lists into readable text."""
    if isinstance(skills, list):
        return ", ".join(str(skill) for skill in skills) if skills else "None"

    if pd.isna(skills) if not isinstance(skills, list) else False:
        return "None"

    return str(skills) if skills else "None"


def format_score(value):
    """Format a score as a percentage."""
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):.2f}%"
    except (ValueError, TypeError):
        return "N/A"


def extract_pdf_text(uploaded_file):
    """Extract text from an uploaded PDF."""
    try:
        reader = PdfReader(uploaded_file)
        pages = []

        for page in reader.pages:
            pages.append(page.extract_text() or "")

        return "\n".join(pages).strip()

    except Exception as error:
        st.warning(
            f"Could not read {uploaded_file.name}: {error}"
        )
        return ""


# -------------------------------
# Job Description
# -------------------------------

st.subheader("📝 Job Description")

job_description = st.text_area(
    "Enter the job description",
    height=180,
    placeholder=(
        "Example: We need a Machine Learning Engineer with "
        "Python, SQL, Machine Learning, NLP and Pandas skills."
    )
)


# -------------------------------
# Resume Upload
# -------------------------------

st.subheader("📄 Upload Candidate Resumes")

uploaded_files = st.file_uploader(
    "Upload one or more resumes in PDF format",
    type=["pdf"],
    accept_multiple_files=True
)


# -------------------------------
# Analyze Candidates
# -------------------------------

if st.button("🔍 Analyze Candidates", type="primary"):

    if not job_description.strip():
        st.error("Please enter a job description.")

    elif not uploaded_files:
        st.error("Please upload at least one PDF resume.")

    else:
        resumes = {}
        candidate_names = []

        with st.spinner("Analyzing resumes... Please wait."):

            for uploaded_file in uploaded_files:
                resume_text = extract_pdf_text(uploaded_file)

                if not resume_text:
                    st.warning(
                        f"No readable text found in {uploaded_file.name}."
                    )
                    continue

                # Use the PDF filename as the candidate name.
                original_name = Path(uploaded_file.name).stem
                candidate_name = original_name
                counter = 2

                # Prevent duplicate candidate names.
                while candidate_name in resumes:
                    candidate_name = f"{original_name}_{counter}"
                    counter += 1

                resumes[candidate_name] = resume_text
                candidate_names.append(candidate_name)

            if not resumes:
                st.error(
                    "No readable resume text was found. "
                    "Please upload text-based PDF resumes."
                )

            else:
                try:
                    results = match_candidates(
                        job_description,
                        resumes
                    )

                    if not results:
                        st.warning("No matching results were returned.")

                    else:
                        df = pd.DataFrame(results)

                        # Ensure expected columns exist.
                        required_columns = [
                            "name",
                            "similarity",
                            "semantic_similarity",
                            "skill_coverage",
                            "final_score",
                            "matched_skills",
                            "missing_skills"
                        ]

                        for column in required_columns:
                            if column not in df.columns:
                                df[column] = None

                        # Convert scores to numeric values.
                        score_columns = [
                            "similarity",
                            "semantic_similarity",
                            "skill_coverage",
                            "final_score"
                        ]

                        for column in score_columns:
                            df[column] = pd.to_numeric(
                                df[column],
                                errors="coerce"
                            )

                        # Convert scores to percentages if returned as
                        # fractions between 0 and 1.
                        for column in score_columns:
                            if (
                                df[column].notna().any()
                                and df[column].max() <= 1
                                and df[column].min() >= 0
                            ):
                                df[column] = df[column] * 100

                        # Prepare readable skill columns.
                        df["matched_skills"] = df[
                            "matched_skills"
                        ].apply(format_skills)

                        df["missing_skills"] = df[
                            "missing_skills"
                        ].apply(format_skills)

                        # Sort candidates by final score.
                        df = df.sort_values(
                            by="final_score",
                            ascending=False,
                            na_position="last"
                        ).reset_index(drop=True)

                        # Display-friendly column names.
                        display_df = df.rename(
                            columns={
                                "name": "Candidate",
                                "similarity": "Text Similarity (%)",
                                "semantic_similarity": "Semantic Similarity (%)",
                                "skill_coverage": "Skill Coverage (%)",
                                "final_score": "Final Match Score (%)",
                                "matched_skills": "Matched Skills",
                                "missing_skills": "Missing Skills"
                            }
                        )

                        st.success(
                            f"Analysis completed for {len(df)} candidate(s)."
                        )

                        # -------------------------------
                        # Analysis Overview
                        # -------------------------------

                        st.header("📌 Analysis Overview")

                        col1, col2, col3 = st.columns(3)

                        col1.metric(
                            "Total Candidates",
                            len(df)
                        )

                        if df["final_score"].notna().any():
                            top_index = df["final_score"].idxmax()
                            top_candidate = df.loc[top_index, "name"]
                            top_score = df.loc[top_index, "final_score"]

                            col2.metric(
                                "Top Candidate",
                                str(top_candidate)
                            )

                            col3.metric(
                                "Highest Match Score",
                                format_score(top_score)
                            )
                        else:
                            col2.metric("Top Candidate", "N/A")
                            col3.metric("Highest Match Score", "N/A")

                        # -------------------------------
                        # Candidate Ranking
                        # -------------------------------

                        st.header("🏆 Candidate Ranking")

                        ranking_columns = [
                            "Candidate",
                            "Text Similarity (%)",
                            "Semantic Similarity (%)",
                            "Skill Coverage (%)",
                            "Final Match Score (%)",
                            "Matched Skills",
                            "Missing Skills"
                        ]

                        st.dataframe(
                            display_df[ranking_columns],
                            use_container_width=True,
                            hide_index=True
                        )

                        # -------------------------------
                        # Candidate Details
                        # -------------------------------

                        st.header("👤 Candidate Details")

                        candidate_options = display_df[
                            "Candidate"
                        ].tolist()

                        selected_candidate = st.selectbox(
                            "Select a candidate",
                            candidate_options
                        )

                        selected_row = display_df[
                            display_df["Candidate"] == selected_candidate
                        ].iloc[0]

                        detail_col1, detail_col2, detail_col3 = st.columns(3)

                        detail_col1.metric(
                            "Final Match Score",
                            format_score(
                                selected_row["Final Match Score (%)"]
                            )
                        )

                        detail_col2.metric(
                            "Text Similarity",
                            format_score(
                                selected_row["Text Similarity (%)"]
                            )
                        )

                        detail_col3.metric(
                            "Skill Coverage",
                            format_score(
                                selected_row["Skill Coverage (%)"]
                            )
                        )

                        st.write("**Matched Skills**")
                        st.write(selected_row["Matched Skills"])

                        st.write("**Missing Skills**")
                        st.write(selected_row["Missing Skills"])

                        # -------------------------------
                        # Skill Gap Analysis
                        # -------------------------------

                        st.header("🎯 Skill Gap Analysis")

                        missing_skills = selected_row[
                            "Missing Skills"
                        ]

                        if missing_skills == "None":
                            st.success(
                                "No missing skills were identified "
                                "from the configured skill catalog."
                            )
                        else:
                            st.warning(
                                f"Skills to improve: {missing_skills}"
                            )

                            st.write(
                                "Candidates can focus on learning "
                                "and practicing these skills."
                            )

                        # -------------------------------
                        # Candidate Score Charts
                        # -------------------------------

                        st.header("📊 Candidate Ranking Charts")

                        # Chart 1: Final Match Score
                        st.subheader("🏆 Final Match Score")

                        final_chart = display_df[
                            ["Candidate", "Final Match Score (%)"]
                        ].dropna().copy()

                        if not final_chart.empty:
                            final_chart = final_chart.set_index("Candidate")
                            st.bar_chart(final_chart,horizontal=True)
                        else:
                            st.info(
                                "Final match score data is unavailable."
                            )

                        # Chart 2: Text Similarity
                        st.subheader("📝 Text Similarity")

                        text_chart = display_df[
                            ["Candidate", "Text Similarity (%)"]
                        ].dropna().copy()

                        if not text_chart.empty:
                            text_chart = text_chart.set_index("Candidate")
                            st.bar_chart(text_chart,horizontal=True)
                        else:
                            st.info(
                                "Text similarity data is unavailable."
                            )

                        # Chart 3: Semantic Similarity
                        semantic_chart = display_df[
                            ["Candidate", "Semantic Similarity (%)"]
                        ].dropna().copy()

                        if not semantic_chart.empty:
                            st.subheader("🧠 Semantic Similarity")
                            semantic_chart = semantic_chart.set_index(
                                "Candidate"
                            )
                            st.bar_chart(semantic_chart,horizontal=True)
                        else:
                            st.info(
                                "Semantic similarity is unavailable. "
                                "Check whether the semantic model is installed "
                                "and loaded in matching_engine.py."
                            )

                        # -------------------------------
                        # Download Results
                        # -------------------------------

                        st.header("📥 Download Results")

                        csv_data = display_df.to_csv(
                            index=False
                        ).encode("utf-8-sig")

                        st.download_button(
                            label="⬇️ Download Candidate Results (CSV)",
                            data=csv_data,
                            file_name="candidate_ranking_results.csv",
                            mime="text/csv"
                        )

                except Exception as error:
                    st.error(
                        f"An error occurred during analysis: {error}"
                    )
                    st.exception(error)
