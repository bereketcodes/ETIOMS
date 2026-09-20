import math
import os
from google import genai
from fastapi import HTTPException

def generate_text_embedding(text: str) -> list[float]:
    """Turns a sentence into a list of 768 numbers."""
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Cannot create an embedding for empty text.")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set.")

    try:
        client = genai.Client(api_key=api_key)
        result = client.models.embed_content(
            model="text-embedding-004",
            contents=text,
        )
        return result.embeddings[0].values
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Google Embedding Service failed: {str(e)}")


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Calculates how closely two lists of numbers match (0.0 to 1.0)."""
    # 1. Error check: Are the vectors empty?
    if not vec_a or not vec_b:
        return 0.0

    # 2. Error check: Are the rulers different lengths?
    if len(vec_a) != len(vec_b):
        raise ValueError(f"Vector sizes do not match! Vector A: {len(vec_a)}, Vector B: {len(vec_b)}")

    # 3. Calculate the match score
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    # Guard against dividing by zero
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)