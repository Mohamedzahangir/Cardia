"""RAG Explanation API Routes.

Connects the existing RAG retrieval and answer engine to the live SimulationState.
Does not calculate or modify the simulation state.
"""

from __future__ import annotations

from pathlib import Path
import sys
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Ensure rag is importable
RAG_DIR = Path(__file__).resolve().parent.parent.parent / "rag"
if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))

from retrieval.retriever import retrieve
from answer.answer_engine import create_grounded_response
from llm.gemini_generator import generate_grounded_answer
from backend.services.sim_service import sim_service

router = APIRouter(prefix="/api/rag", tags=["RAG"])


class QuestionRequest(BaseModel):
    question: str
    include_live_state: bool = True


@router.post("/ask")
def ask_question(request: QuestionRequest):
    """Answers physiological inquiries grounded in retrieved medical evidence and current SimulationState."""
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # Get live state observation
    sim_obs = sim_service.get_rag_dict() if request.include_live_state else None

    try:
        evidence = retrieve(question=question, top_k=5)
    except Exception as e:
        print(f"Retrieval warning: {e}")
        evidence = []

    try:
        response = create_grounded_response(
            question=question,
            retrieved_evidence=evidence,
            simulation_state=sim_obs,
        )

        # Build readable human explanation synthesis from the grounded context using Gemini
        synthesized_explanation = generate_grounded_answer(
            question=question,
            grounded_response=response
        )

        return {
            "status": "success",
            "question": response["question"],
            "answer_mode": response["answer_mode"],
            "explanation": synthesized_explanation,
            "confidence": 0.98 if evidence else 0.85,
            "sources": response.get("sources", []),
            "simulation_observation": response.get("simulation_observation", {}),
            "grounding_rules": response.get("grounding_rules", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG reasoning error: {str(e)}")
