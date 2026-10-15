
import re
from functools import lru_cache

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# Common technical skills and alternative names
@lru_cache(maxsize=1)
def _get_sentence_transformer_model():
    """Load the optional embedding model once per app process, not on every match."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


SKILL_CATALOG = {
    "Python": ["python"],
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning", "dl"],
    "NLP": ["nlp", "natural language processing"],
    "SQL": ["sql", "structured query language"],
    "TensorFlow": ["tensorflow"],
    "PyTorch": ["pytorch"],
    "Scikit-learn": ["scikit-learn", "scikit learn", "sklearn"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Data Analysis": ["data analysis", "data analytics"],
    "Data Science": ["data science"],
    "Power BI": ["power bi"],
    "Excel": ["excel", "microsoft excel"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "Java": ["java"],
    "JavaScript": ["javascript"],
    "HTML": ["html"],
    "CSS": ["css"],
    "React": ["react", "reactjs"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi"],
    "Django": ["django"],
    "Node.js": ["node.js", "node js", "nodejs"],
    "Express.js": ["express.js", "express js", "expressjs"],
    "REST API": ["rest api", "rest apis", "restful api", "restful apis", "restful services"],
    "GraphQL": ["graphql"],
    "MongoDB": ["mongodb", "mongo db"],
    "Redis": ["redis"],
    "Linux": ["linux"],
    "Bash": ["bash", "shell scripting"],
    "Jenkins": ["jenkins"],
    "CI/CD": ["ci cd", "continuous integration", "continuous delivery"],
    "Terraform": ["terraform"],
    "Apache Spark": ["apache spark", "pyspark", "spark"],
    "Hadoop": ["hadoop"],
    "Airflow": ["airflow", "apache airflow"],
    "Snowflake": ["snowflake"],
    "Tableau": ["tableau"],
    "Looker": ["looker"],
    "XGBoost": ["xgboost"],
    "LightGBM": ["lightgbm"],
    "Hugging Face": ["hugging face", "huggingface"],
    "OpenCV": ["opencv", "open cv"],
    "LangChain": ["langchain"],
    "Vector Databases": ["vector database", "vector databases", "vector db"],
    "Streamlit": ["streamlit"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure", "microsoft azure"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes"],
    "Git": ["git"],
    "GitHub": ["github"],
    "Computer Vision": ["computer vision"],
    "CNN": ["cnn", "convolutional neural network"],
    "LSTM": ["lstm"],
    "Statistics": ["statistics", "statistical analysis"],
    "Data Visualization": [
        "data visualization", "data visualisation"
    ],
    "Generative AI": ["generative ai", "gen ai"],
    "RAG": ["rag", "retrieval augmented generation"],
    "Transformers": ["transformers", "transformer models"],
}


def normalize_text(text):
    """Normalize text before matching."""
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def extract_skills(text):
    """Extract recognized technical skills."""
    normalized_text = " " + normalize_text(text) + " "
    found_skills = []

    for skill, aliases in SKILL_CATALOG.items():
        for alias in aliases:
            normalized_alias = normalize_text(alias)

            if f" {normalized_alias} " in normalized_text:
                found_skills.append(skill)
                break

    return found_skills


def calculate_similarity(job_description, resume_texts):
    """Calculate lexical similarity using TF-IDF."""
    documents = [job_description] + resume_texts

    try:
        vectorizer = TfidfVectorizer(stop_words="english")
        vectors = vectorizer.fit_transform(documents)

        scores = cosine_similarity(
            vectors[0:1], vectors[1:]
        )[0]

        return [float(score) for score in scores]

    except ValueError:
        return [0.0] * len(resume_texts)


def calculate_semantic_similarity(job_description, resume_texts):
    """
    Compare meaning using sentence embeddings.
    If the optional model is unavailable, return None.
    """
    if not resume_texts:
        return []

    try:
        model = _get_sentence_transformer_model()

        embeddings = model.encode(
            [job_description] + resume_texts,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        scores = cosine_similarity(
            embeddings[0:1], embeddings[1:]
        )[0]

        # Convert cosine similarity into a 0-100 score.
        return [
            round(max(0.0, min(1.0, float(score))) * 100, 2)
            for score in scores
        ]

    except Exception as error:
        print(
            "Semantic model unavailable. Using TF-IDF instead.",
            error
        )
        return None



def extract_required_experience_years(text):
    """Read an explicit experience requirement such as '2+ years' from job text."""
    normalized = normalize_text(text)
    patterns = [
        r"(\d+)\s*\+?\s*(?:years|year|yrs|yr)\s+(?:of\s+)?(?:relevant\s+)?experience",
        r"experience\s+(?:of\s+)?(\d+)\s*\+?\s*(?:years|year|yrs|yr)",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return int(match.group(1))
    return None


def extract_candidate_experience_years(text):
    """Estimate years only when a resume states an explicit duration near experience."""
    normalized = normalize_text(text)
    patterns = [
        r"(\d+)\s*\+?\s*(?:years|year|yrs|yr)\s+(?:of\s+)?(?:professional\s+)?experience",
        r"(\d+)\s*\+?\s*(?:years|year|yrs|yr)\s+(?:in|with)\s+",
    ]
    matches = []
    for pattern in patterns:
        matches.extend(int(value) for value in re.findall(pattern, normalized))
    return max(matches) if matches else None


def education_level(text):
    """Return the highest explicitly mentioned education level, without inferring it."""
    normalized = " " + normalize_text(text) + " "
    levels = [
        (5, ["phd", "doctorate", "doctoral"]),
        (4, ["master", "masters", "m tech", "mtech", "mba", "msc", "m sc", "m a"]),
        (3, ["bachelor", "bachelors", "b tech", "btech", "b e", "bsc", "b sc", "ba", "bca"]),
        (2, ["diploma", "associate degree"]),
        (1, ["high school", "12th", "higher secondary", "intermediate"]),
    ]
    for level, terms in levels:
        if any(" " + term + " " in normalized for term in terms):
            return level
    return None

def experience_fit_score(job_text, resume_text):
    """Score explicit experience requirements; unknown requirements stay neutral."""
    required = extract_required_experience_years(job_text)
    candidate = extract_candidate_experience_years(resume_text)
    if required is None:
        return 100.0, required, candidate
    if candidate is None:
        return 50.0, required, candidate
    return min(100.0, candidate / max(required, 1) * 100), required, candidate


def education_fit_score(job_text, resume_text):
    """Score education only if the job explicitly mentions a qualification level."""
    required = education_level(job_text)
    candidate = education_level(resume_text)
    if required is None:
        return 100.0, required, candidate
    if candidate is None:
        return 50.0, required, candidate
    return min(100.0, candidate / max(required, 1) * 100), required, candidate

def match_resume_to_jobs(resume_text, jobs):
    """
    Score one resume against a list of job dictionaries in a single AI pass.
    Each job may contain title, description, required_skills and other display fields.
    Returns job dictionaries with scores, skill gaps and an explainable match summary.
    """
    if not isinstance(resume_text, str) or not resume_text.strip():
        raise ValueError("Resume text cannot be empty.")
    if not jobs:
        return []

    job_documents = []
    for job in jobs:
        title = str(job.get("title") or job.get("job_title") or "Open role")
        description = str(job.get("description") or job.get("job_description") or "")
        required = str(job.get("required_skills") or job.get("skills") or "")
        job_documents.append(
            f"{title}. {description}. Required skills: {required}"
        )

    # Fit one shared vector space so job-to-resume scores are comparable.
    try:
        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform([resume_text] + job_documents)
        lexical_scores = cosine_similarity(matrix[1:], matrix[0:1]).ravel()
        lexical_scores = [float(score) * 100 for score in lexical_scores]
    except ValueError:
        lexical_scores = [0.0] * len(jobs)

    # Optional semantic embeddings; if the model/package is unavailable, use TF-IDF.
    semantic_scores = None
    try:
        model = _get_sentence_transformer_model()
        vectors = model.encode(
            [resume_text] + job_documents,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        semantic_scores = [
            max(0.0, min(100.0, float(score) * 100))
            for score in cosine_similarity(vectors[1:], vectors[0:1]).ravel()
        ]
    except Exception:
        semantic_scores = None

    candidate_skills = set(extract_skills(resume_text))
    results = []
    for index, job in enumerate(jobs):
        required_skills = extract_skills(job_documents[index])
        matched = [skill for skill in required_skills if skill in candidate_skills]
        missing = [skill for skill in required_skills if skill not in candidate_skills]
        coverage = (len(matched) / len(required_skills) * 100) if required_skills else 0.0
        lexical = lexical_scores[index]
        experience_score, required_years, candidate_years = experience_fit_score(job_documents[index], resume_text)
        education_score, required_education, candidate_education = education_fit_score(job_documents[index], resume_text)

        if semantic_scores is not None:
            semantic = semantic_scores[index]
            if required_skills:
                score = (
                    0.25 * semantic + 0.15 * lexical + 0.40 * coverage
                    + 0.10 * experience_score + 0.10 * education_score
                )
            else:
                score = (
                    0.50 * semantic + 0.30 * lexical
                    + 0.10 * experience_score + 0.10 * education_score
                )
        else:
            semantic = None
            if required_skills:
                score = (
                    0.25 * lexical + 0.50 * coverage
                    + 0.15 * experience_score + 0.10 * education_score
                )
            else:
                score = (
                    0.70 * lexical + 0.20 * experience_score
                    + 0.10 * education_score
                )

        reasons = []
        if matched:
            reasons.append("Matched skills: " + ", ".join(matched[:5]))
        if required_years is not None:
            reasons.append(
                f"Experience: {candidate_years if candidate_years is not None else 'not stated'} / {required_years} required years"
            )
        if required_education is not None:
            reasons.append(
                f"Education level: {candidate_education if candidate_education is not None else 'not stated'} (job requirement level {required_education})"
            )
        if missing:
            reasons.append("Skills to improve: " + ", ".join(missing[:5]))
        if not reasons:
            reasons.append("Text relevance is the main available signal; review the resume manually.")

        item = dict(job)
        item.update({
            "score": round(max(0.0, min(100.0, score)), 1),
            "lexical": round(lexical, 1),
            "semantic": round(semantic, 1) if semantic is not None else None,
            "skill_coverage": round(coverage, 1),
            "experience_fit": round(experience_score, 1),
            "required_experience_years": required_years,
            "candidate_experience_years": candidate_years,
            "education_fit": round(education_score, 1),
            "required_education_level": required_education,
            "candidate_education_level": candidate_education,
            "reasons": reasons,
            "matched": matched,
            "missing": missing,
            "candidate_skills": sorted(candidate_skills),
            "required_skill_count": len(required_skills),
        })
        results.append(item)

    results.sort(key=lambda item: item["score"], reverse=True)
    return results


def match_candidates(job_description, resumes):
    """
    Rank candidates for Instant Employee.

    With semantic model:
        30% semantic similarity
        20% TF-IDF similarity
        50% skill coverage

    Without semantic model:
        50% TF-IDF similarity
        50% skill coverage

    If no recognized job skills exist, use text similarity.
    """
    if not isinstance(job_description, str):
        raise TypeError("Job description must be text.")

    if not job_description.strip():
        raise ValueError("Job description cannot be empty.")

    if not isinstance(resumes, dict) or not resumes:
        return []

    names = list(resumes.keys())
    resume_texts = [
        str(resumes[name] or "") for name in names
    ]

    required_skills = extract_skills(job_description)

    lexical_scores = calculate_similarity(
        job_description, resume_texts
    )

    semantic_scores = calculate_semantic_similarity(
        job_description, resume_texts
    )

    results = []

    for index, (name, resume) in enumerate(
        zip(names, resume_texts)
    ):
        lexical_score = lexical_scores[index] * 100

        # A missing or unreadable resume must not receive a positive score
        # from neutral experience/education defaults.
        if not resume.strip():
            results.append({
                "name": name,
                "similarity": 0.0,
                "semantic_similarity": None,
                "skill_coverage": 0.0,
                "experience_fit": 0.0,
                "required_experience_years": extract_required_experience_years(job_description),
                "candidate_experience_years": None,
                "education_fit": 0.0,
                "required_education_level": education_level(job_description),
                "candidate_education_level": None,
                "reasons": ["No readable resume text was provided."],
                "final_score": 0.0,
                "matched_skills": [],
                "missing_skills": required_skills,
            })
            continue

        candidate_skills = extract_skills(resume)

        matched_skills = [
            skill for skill in required_skills
            if skill in candidate_skills
        ]

        missing_skills = [
            skill for skill in required_skills
            if skill not in candidate_skills
        ]

        if required_skills:
            skill_coverage = (len(matched_skills) / len(required_skills)) * 100
        else:
            # Do not penalize a candidate because a job has no recognizable skills.
            skill_coverage = 0.0

        experience_score, required_years, candidate_years = experience_fit_score(
            job_description, resume
        )
        education_score, required_education, candidate_education = education_fit_score(
            job_description, resume
        )

        if semantic_scores is not None:
            semantic_score = semantic_scores[index]
            if required_skills:
                final_score = (
                    0.25 * semantic_score
                    + 0.15 * lexical_score
                    + 0.40 * skill_coverage
                    + 0.10 * experience_score
                    + 0.10 * education_score
                )
            else:
                final_score = (
                    0.50 * semantic_score + 0.30 * lexical_score
                    + 0.10 * experience_score + 0.10 * education_score
                )
        else:
            semantic_score = None
            if required_skills:
                final_score = (
                    0.25 * lexical_score
                    + 0.50 * skill_coverage
                    + 0.15 * experience_score
                    + 0.10 * education_score
                )
            else:
                final_score = (
                    0.70 * lexical_score + 0.20 * experience_score
                    + 0.10 * education_score
                )

        reasons = []
        if matched_skills:
            reasons.append("Matched skills: " + ", ".join(matched_skills[:5]))
        if missing_skills:
            reasons.append("Missing skills: " + ", ".join(missing_skills[:5]))
        if required_years is not None:
            reasons.append(
                f"Experience stated: {candidate_years if candidate_years is not None else 'unknown'} years; job asks for {required_years}"
            )
        if required_education is not None:
            reasons.append(
                f"Education requirement level {required_education}; candidate level {candidate_education if candidate_education is not None else 'not stated'}"
            )
        if not reasons:
            reasons.append("Ranking is based mainly on resume/job text relevance.")

        results.append({
            "name": name,
            "similarity": round(lexical_score, 2),
            "semantic_similarity": (
                round(semantic_score, 2)
                if semantic_score is not None else None
            ),
            "skill_coverage": round(skill_coverage, 2),
            "experience_fit": round(experience_score, 2),
            "required_experience_years": required_years,
            "candidate_experience_years": candidate_years,
            "education_fit": round(education_score, 2),
            "required_education_level": required_education,
            "candidate_education_level": candidate_education,
            "reasons": reasons,
            "final_score": round(max(0.0, min(100.0, final_score)), 2),
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
        })

    results.sort(
        key=lambda candidate: candidate["final_score"],
        reverse=True
    )

    return results


if __name__ == "__main__":
    job_description = """
    Machine Learning Engineer with Python, NLP,
    SQL and TensorFlow experience.
    Knowledge of data preprocessing and model evaluation.
    """

    resumes = {
        "Candidate A": """
        Python developer with machine learning, NLP,
        SQL and TensorFlow project experience.
        """,
        "Candidate B": """
        Web developer with HTML, CSS, JavaScript
        and React experience.
        """,
        "Candidate C": """
        Data analyst with Python, SQL, pandas
        and machine learning knowledge.
        """,
    }

    results = match_candidates(job_description, resumes)

    print("\nINSTANT EMPLOYEE - AI CANDIDATE MATCHING")
    print("=" * 52)

    for rank, candidate in enumerate(results, start=1):
        print(f"\nRank: {rank}")
        print(f"Candidate: {candidate['name']}")
        print(f"TF-IDF Similarity: {candidate['similarity']}%")
        print(
            "Semantic Similarity:",
            f"{candidate['semantic_similarity']}%"
            if candidate["semantic_similarity"] is not None
            else "Unavailable (TF-IDF fallback)"
        )
        print(f"Skill Coverage: {candidate['skill_coverage']}%")
        print(f"Final Match Score: {candidate['final_score']}%")
        print("Matched Skills:", candidate["matched_skills"] or ["None"])
        print("Missing Skills:", candidate["missing_skills"] or ["None"])
        