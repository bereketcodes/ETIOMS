import pypdf
from fastapi import HTTPException

def extract_text_from_pdf(file_path: str) -> str:
    """Reads pages from a PDF file and returns aggregated plain text."""
    try:
        reader = pypdf.PdfReader(file_path)
        extracted_pages = []
        for index, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                extracted_pages.append(f"--- Page {index + 1} ---\n{page_text}")
        
        full_text = "\n\n".join(extracted_pages).strip()
        if not full_text:
            raise ValueError("No extractable text found in PDF.")
        return full_text
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to process PDF document: {str(e)}"
        )