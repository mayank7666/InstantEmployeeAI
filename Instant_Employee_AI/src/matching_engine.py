
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# Common technical skills and alternative names
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
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )

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
            skill_coverage = (
                len(matched_skills) / len(required_skills)
            ) * 100
        else:
            skill_coverage = 0.0

        if semantic_scores is not None:
            semantic_score = semantic_scores[index]

            if required_skills:
                final_score = (
                    0.30 * semantic_score
                    + 0.20 * lexical_score
                    + 0.50 * skill_coverage
                )
            else:
                final_score = (
                    0.60 * semantic_score
                    + 0.40 * lexical_score
                )

        else:
            semantic_score = None

            if required_skills:
                final_score = (
                    0.50 * lexical_score
                    + 0.50 * skill_coverage
                )
            else:
                final_score = lexical_score

        results.append({
            "name": name,
            "similarity": round(lexical_score, 2),
            "semantic_similarity": (
                round(semantic_score, 2)
                if semantic_score is not None else None
            ),
            "skill_coverage": round(skill_coverage, 2),
            "final_score": round(
                max(0.0, min(100.0, final_score)), 2
            ),
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
        