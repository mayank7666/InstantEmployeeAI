
def extract_skills(resume_text):
    skills_list = {
        "Programming": [
            "python", "java", "c++", "html", "css", "javascript"
        ],
        "Machine Learning": [
            "machine learning", "regression", "classification",
            "clustering", "scikit-learn"
        ],
        "Deep Learning": [
            "deep learning", "neural networks", "cnn",
            "lstm", "tensorflow", "pytorch"
        ],
        "NLP": [
            "nlp", "natural language processing",
            "text preprocessing", "semantic matching"
        ],
        "Data Analysis": [
            "sql", "pandas", "numpy", "excel",
            "power bi", "matplotlib"
        ]
    }

    resume_text = resume_text.lower()
    extracted_skills = {}

    for category, skills in skills_list.items():
        matched = []

        for skill in skills:
            if skill in resume_text:
                matched.append(skill)

        if matched:
            extracted_skills[category] = matched

    return extracted_skills


if __name__ == "__main__":
    resume_text = """
    Python developer with machine learning experience.
    Worked with NLP, SQL, TensorFlow, Pandas and NumPy.
    Experience in classification and neural networks.
    """

    result = extract_skills(resume_text)

    print("\nEXTRACTED RESUME SKILLS")
    print("=" * 35)

    for category, skills in result.items():
        print(f"\n{category}:")
        print(", ".join(skills))
