from pathlib import Path
import sys

from fastapi import FastAPI
from pydantic import BaseModel

RAG_DIR = Path(__file__).resolve().parent

if str(RAG_DIR) not in sys.path:
    sys.path.insert(0, str(RAG_DIR))


from retrieval.retriever import retrieve
from answer.answer_engine import create_grounded_response
from rag.llm.gemini_generator import generate_grounded_answer
from rag.answer.confidence import (
    calculate_confidence,
    confidence_level,
)
from rag.database.explanation_repository import (
    save_explanation,
    get_session_explanations,
)
from rag.database.session_repository import get_session
from rag.database.knowledge_source_repository import (
    find_knowledge_source,
)
from rag.database.counterfactual_repository import (
    create_counterfactual_run,
    save_counterfactual_result,
)
from rag.database.experiment_repository import (
    create_experiment,
    get_experiment,
    save_experiment_parameter,
    save_experiment_result,
)
from rag.counterfactual.engine import run_counterfactual
from rag.counterfactual.state_adapter import (
    rag_dict_to_simulation_state,
)


app = FastAPI(
    title="CARDIA RAG API",
    description=(
        "Cardiology-focused retrieval, grounded reasoning, "
        "LLM generation, confidence scoring, session-aware "
        "conversation context, counterfactual simulation, "
        "experiment persistence, counterfactual explanations, "
        "and database persistence API for CARDIA."
    ),
    version="1.6.0",
)


class QuestionRequest(BaseModel):
    question: str
    simulation_state: dict | None = None
    session_id: str | None = None


class CounterfactualRequest(BaseModel):
    parameter: str
    intervention_value: float
    duration: float
    dt: float = 0.01
    simulation_state: dict | None = None
    session_id: str | None = None
    experiment_id: str | None = None


def _find_peak_state(
    trajectory: list[dict],
) -> dict:
    """
    Find the trajectory state with the highest simulated
    cardiac output.

    This is a simulation-derived observation, not a clinical
    peak-performance assessment.
    """

    if not trajectory:
        return {}

    valid_states = [
        state
        for state in trajectory
        if isinstance(
            state.get("cardiac_output"),
            (int, float),
        )
    ]

    if not valid_states:
        return trajectory[-1]

    return max(
        valid_states,
        key=lambda state: float(
            state["cardiac_output"]
        ),
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "cardia-rag",
        "version": app.version,
    }


@app.post("/ask")
def ask_question(request: QuestionRequest):
    question = request.question.strip()

    if not question:
        return {
            "status": "error",
            "message": "Question cannot be empty.",
        }

    session = None
    session_history = []

    if request.session_id:
        session = get_session(request.session_id)

        session_history = get_session_explanations(
            session_id=request.session_id,
            limit=10,
        )

    evidence = retrieve(
        question=question,
        top_k=5,
    )

    response = create_grounded_response(
        question=question,
        retrieved_evidence=evidence,
        simulation_state=request.simulation_state,
    )

    confidence = calculate_confidence(
        response["evidence"]
    )

    confidence_label = confidence_level(
        confidence
    )

    response["confidence"] = confidence
    response["confidence_level"] = confidence_label

    knowledge_sources = []

    for source in response["sources"]:
        knowledge_source = find_knowledge_source(
            title=source.get("source_title", ""),
            author=source.get("author"),
            source_type=source.get("source_type"),
        )

        if knowledge_source:
            source["knowledge_source_id"] = (
                knowledge_source["id"]
            )

            knowledge_source_summary = {
                "id": knowledge_source["id"],
                "title": knowledge_source["title"],
                "author": knowledge_source["author"],
                "source_type": knowledge_source["source_type"],
            }

            if (
                knowledge_source_summary
                not in knowledge_sources
            ):
                knowledge_sources.append(
                    knowledge_source_summary
                )

    answer = generate_grounded_answer(
        question=question,
        grounded_response=response,
        session_history=session_history,
    )

    saved_explanation = save_explanation(
        question=response["question"],
        answer=answer,
        simulation_context=response[
            "simulation_observation"
        ],
        sources=response["sources"],
        confidence=confidence,
        session_id=request.session_id,
    )

    response["answer"] = answer

    response["knowledge_sources"] = knowledge_sources

    response["database"] = {
        "saved": True,
        "explanation_id": saved_explanation["id"],
        "session_id": request.session_id,
    }

    if session:
        response["database"]["session"] = {
            "id": session["id"],
            "status": session["status"],
        }

    response["session_context"] = {
        "used": bool(session_history),
        "exchange_count": len(session_history),
    }

    return response


@app.post("/counterfactual")
def counterfactual(request: CounterfactualRequest):
    """
    Run a CARDIA baseline/intervention counterfactual experiment.

    The simulation engine remains the source of truth.

    After the simulation completes, the endpoint:

    1. creates or validates an experiment,
    2. persists experiment parameters,
    3. persists the experiment result,
    4. persists counterfactual trajectory results,
    5. retrieves relevant cardiovascular evidence,
    6. generates a grounded physiological explanation,
    7. persists that explanation,
    8. returns the numerical comparison and explanation.

    The endpoint never modifies the simulation package.
    """

    supported_parameters = {
        "heart_rate",
        "contractility",
        "svr",
    }

    if request.parameter not in supported_parameters:
        return {
            "status": "error",
            "message": (
                "Unsupported counterfactual parameter. "
                "Supported parameters: "
                "heart_rate, contractility, svr."
            ),
        }

    if request.duration <= 0:
        return {
            "status": "error",
            "message": "duration must be greater than 0.",
        }

    if request.dt <= 0:
        return {
            "status": "error",
            "message": "dt must be greater than 0.",
        }

    session = None
    session_history = []

    if request.session_id:
        session = get_session(
            request.session_id
        )

        session_history = get_session_explanations(
            session_id=request.session_id,
            limit=10,
        )

    state = rag_dict_to_simulation_state(
        request.simulation_state
    )

    result = run_counterfactual(
        state=state,
        parameter=request.parameter,
        intervention_value=request.intervention_value,
        duration=request.duration,
        dt=request.dt,
    )

    # ---------------------------------------------------------
    # Experiment persistence
    # ---------------------------------------------------------

    if request.experiment_id:
        experiment = get_experiment(
            request.experiment_id
        )
        experiment_id = experiment["id"]

    else:
        experiment = create_experiment(
            name=(
                f"CARDIA {result.parameter} "
                f"Counterfactual"
            ),
            description=(
                f"Counterfactual experiment comparing "
                f"{result.parameter} at "
                f"{result.baseline_value} versus "
                f"{result.intervention_value}."
            ),
            experiment_type="counterfactual",
            session_id=request.session_id,
        )
        experiment_id = experiment["id"]

    saved_parameter = save_experiment_parameter(
        experiment_id=experiment_id,
        parameter_name=result.parameter,
        initial_value=result.baseline_value,
        final_value=result.intervention_value,
        unit={
            "heart_rate": "bpm",
            "contractility": "multiplier",
            "svr": "multiplier",
        }[result.parameter],
    )

    baseline_metrics = {
        key: value["baseline"]
        for key, value in result.metrics.items()
    }

    intervention_metrics = {
        key: value["intervention"]
        for key, value in result.metrics.items()
    }

    baseline_peak_state = _find_peak_state(
        result.baseline_trajectory
    )

    intervention_peak_state = _find_peak_state(
        result.intervention_trajectory
    )

    peak_state = {
        "baseline": baseline_peak_state,
        "intervention": intervention_peak_state,
    }

    experiment_result = save_experiment_result(
        experiment_id=experiment_id,
        baseline_state=result.baseline_final_state,
        peak_state=peak_state,
        final_state=result.intervention_final_state,
        change_summary=result.metrics,
        stability_score=result.stability_score,
    )

    # ---------------------------------------------------------
    # Counterfactual persistence
    # ---------------------------------------------------------

    counterfactual_run = create_counterfactual_run(
        session_id=request.session_id,
        experiment_id=experiment_id,
        baseline_duration=result.duration,
    )

    baseline_result = save_counterfactual_result(
        counterfactual_id=counterfactual_run["id"],
        trajectory="baseline",
        final_state=result.baseline_final_state,
        metrics=baseline_metrics,
        stability_score=result.stability_score,
    )

    intervention_result = save_counterfactual_result(
        counterfactual_id=counterfactual_run["id"],
        trajectory="intervention",
        final_state=result.intervention_final_state,
        metrics=intervention_metrics,
        stability_score=result.stability_score,
    )

    # ---------------------------------------------------------
    # Grounded RAG explanation
    # ---------------------------------------------------------

    comparison_question = (
        f"What happens physiologically when "
        f"{result.parameter} changes from "
        f"{result.baseline_value} to "
        f"{result.intervention_value}?"
    )

    evidence = retrieve(
        question=comparison_question,
        top_k=5,
    )

    grounded_response = create_grounded_response(
        question=comparison_question,
        retrieved_evidence=evidence,
        simulation_state=result.intervention_final_state,
    )

    confidence = calculate_confidence(
        grounded_response["evidence"]
    )

    confidence_label = confidence_level(
        confidence
    )

    grounded_response["confidence"] = confidence
    grounded_response["confidence_level"] = (
        confidence_label
    )

    knowledge_sources = []

    for source in grounded_response["sources"]:
        knowledge_source = find_knowledge_source(
            title=source.get("source_title", ""),
            author=source.get("author"),
            source_type=source.get("source_type"),
        )

        if knowledge_source:
            source["knowledge_source_id"] = (
                knowledge_source["id"]
            )

            knowledge_source_summary = {
                "id": knowledge_source["id"],
                "title": knowledge_source["title"],
                "author": knowledge_source["author"],
                "source_type": knowledge_source["source_type"],
            }

            if (
                knowledge_source_summary
                not in knowledge_sources
            ):
                knowledge_sources.append(
                    knowledge_source_summary
                )

    counterfactual_context = {
        "parameter": result.parameter,
        "baseline_value": result.baseline_value,
        "intervention_value": result.intervention_value,
        "change_percent": result.change_percent,
        "duration": result.duration,
        "comparison": result.metrics,
    }

    answer = generate_grounded_answer(
        question=comparison_question,
        grounded_response=grounded_response,
        session_history=session_history,
        counterfactual=counterfactual_context,
    )

    saved_explanation = save_explanation(
        question=comparison_question,
        answer=answer,
        simulation_context={
            "counterfactual_run_id": counterfactual_run["id"],
            "parameter": result.parameter,
            "baseline_value": result.baseline_value,
            "intervention_value": result.intervention_value,
            "baseline_final_state": result.baseline_final_state,
            "intervention_final_state": result.intervention_final_state,
        },
        sources=grounded_response["sources"],
        confidence=confidence,
        session_id=request.session_id,
        experiment_id=experiment_id,
    )

    return {
        "status": "success",

        "counterfactual": {
            "parameter": result.parameter,
            "baseline_value": result.baseline_value,
            "intervention_value": result.intervention_value,
            "change_percent": result.change_percent,
            "duration": result.duration,
            "dt": result.dt,
        },

        "experiment": {
            "id": experiment_id,
            "name": experiment["name"],
            "type": experiment["experiment_type"],
            "parameter_id": saved_parameter["id"],
            "result_id": experiment_result["id"],
        },

        "baseline": {
            "final_state": result.baseline_final_state,
            "trajectory": result.baseline_trajectory,
            "metrics": baseline_metrics,
            "stability_score": result.stability_score,
            "database_result_id": baseline_result["id"],
        },

        "intervention": {
            "final_state": result.intervention_final_state,
            "trajectory": result.intervention_trajectory,
            "metrics": intervention_metrics,
            "stability_score": result.stability_score,
            "database_result_id": intervention_result["id"],
        },

        "comparison": result.metrics,

        "explanation": {
            "question": comparison_question,
            "answer": answer,
            "confidence": confidence,
            "confidence_level": confidence_label,
            "knowledge_sources": knowledge_sources,
            "grounded_sources": grounded_response[
                "sources"
            ],
            "database_explanation_id": (
                saved_explanation["id"]
            ),
        },

        "database": {
            "saved": True,
            "counterfactual_run_id": counterfactual_run["id"],
            "experiment_id": experiment_id,
            "experiment_result_id": experiment_result["id"],
            "explanation_id": saved_explanation["id"],
            "session_id": request.session_id,
        },

        "session": (
            {
                "id": session["id"],
                "status": session["status"],
            }
            if session
            else None
        ),

        "session_context": {
            "used": bool(session_history),
            "exchange_count": len(session_history),
        },
    }