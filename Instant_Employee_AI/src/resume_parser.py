from pypdf import PdfReader
from pathlib import Path


def extract_resume_text(pdf_path):

    file_path = Path(pdf_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Resume file not found: {pdf_path}"
        )

    if file_path.suffix.lower() != ".pdf":
        raise ValueError("Please provide a PDF file.")

    reader = PdfReader(str(file_path))

    text_pages = []

    for page in reader.pages:
        page_text = page.extract_text() or ""
        text_pages.append(page_text)

    resume_text = "\n".join(text_pages).strip()

    if not resume_text:
        raise ValueError(
            "No readable text found in this PDF."
        )

    return resume_text


if __name__ == "__main__":

    print("INSTANT EMPLOYEE AI")
    print("-" * 40)

    pdf_path = input(
        "Enter the full path of your resume PDF: "
    ).strip().strip('"')

    try:
        text = extract_resume_text(pdf_path)

        print("\nResume text extracted successfully!")
        print("-" * 40)

        print(text[:2000])

        print("\nTotal characters:", len(text))

    except (FileNotFoundError, ValueError) as error:
        print("\nError:", error)

    except Exception as error:
        print("\nCould not read this PDF:", error)