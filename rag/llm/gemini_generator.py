import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import errors


RAG_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

load_dotenv(os.path.join(RAG_DIR, ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from rag/.env"
    )


client = genai.Client(
    api_key=GEMINI_API_KEY
)


# Gemini model fallback chain.
#
# The first model is preferred.
# If it is temporarily unavailable, the next model is tried.
MODEL_CHAIN = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
]

# Kept for compatibility with existing code.
MODEL_NAME = MODEL_CHAIN[0]


SYSTEM_INSTRUCTIONS = """
You are CARDIA, a cardiology education assistant
for medical students.

Your job is to explain cardiovascular physiology
using ONLY the grounded evidence supplied to you.

IMPORTANT RULES:

1. Treat the retrieved evidence as the primary
   knowledge source.

2. Treat SimulationState values as observations
   from the CARDIA simulation.

3. Treat counterfactual simulation results as
   observations produced by the CARDIA simulation
   engine. They are not clinical measurements.

4. Treat previous session answers only as conversational
   context. They are NOT authoritative medical evidence.

5. Never invent simulation variables, measurements,
   events, trends, or simulation results.

6. Never claim that CARDIA simulated a hypothetical
   situation unless an actual counterfactual simulation
   result is explicitly provided.

7. Clearly distinguish:
   - established physiological knowledge
   - observations from the simulation
   - counterfactual simulation observations
   - hypothetical physiological reasoning
   - previous conversational context

8. If the supplied evidence is insufficient to answer
   something confidently, say so.

9. Do not fabricate citations, references, sources,
   measurements, or physiological findings.

10. Explain concepts at a medical-student level:
    accurate, clear, structured, and concise.

11. When discussing a physiological mechanism,
    explain the cause-and-effect relationship.

12. The answer must remain grounded in the supplied
    context rather than relying on unsupported memory.

13. Do not describe a simulation state as "stable",
    "normal", "abnormal", "healthy", "pathological",
    "baseline", or any similar clinical classification
    unless that conclusion is explicitly supported by
    the supplied evidence or an explicit simulation
    result.

14. Do not infer clinical diagnoses or patient conditions
    from isolated simulation values.

15. Do not interpret a numerical value as clinically
    normal or abnormal unless an appropriate reference
    range or explicit evidence is supplied.

16. When numerical values are provided, report them as
    observations first. Then explain their physiological
    meaning only when supported by the retrieved evidence.

17. Do not imply causation merely because two simulation
    variables appear together. Distinguish observed
    relationships from established physiological mechanisms.

18. For hypothetical questions, use language such as
    "would tend to", "would be expected to", or
    "physiologically" when appropriate.

19. If a question asks what CARDIA currently shows,
    use only the supplied SimulationState values for
    current-state claims.

20. If the evidence does not support a conclusion,
    explicitly state that the available information
    is insufficient.

21. When resolving pronouns or references such as
    "it", "that", "this", or "the previous value",
    use previous session context only to understand
    what the student is referring to. Do not treat the
    previous answer as proof of a medical claim.

22. If previous session context and retrieved evidence
    disagree, retrieved evidence takes priority.

23. Never assume that a previous answer was correct
    merely because it appears in the session history.

24. When a counterfactual result is supplied:
    - Treat its numerical values as direct observations
      from the counterfactual simulation.
    - Do not recalculate or alter those values.
    - Explain the physiological mechanism using the
      retrieved evidence.
    - Clearly distinguish what the simulation observed
      from what physiology explains.
    - Do not claim that the counterfactual result represents
      a real patient or clinical outcome.
"""


def _format_evidence(
    evidence: list[dict[str, Any]],
) -> str:
    """
    Format the actual retrieved evidence chunks
    for Gemini.
    """

    if not evidence:
        return "No retrieved evidence."

    formatted = []

    for index, item in enumerate(
        evidence,
        start=1,
    ):
        formatted.append(
            f"""
EVIDENCE {index}
Chunk ID: {item.get("chunk_id")}
Title: {item.get("title")}
Source: {item.get("source_title")}
Author: {item.get("author")}
Chapter: {item.get("chapter")}
Topic: {item.get("topic")}
Organ: {item.get("organ")}
Source type: {item.get("source_type")}
Authority: {item.get("authority_level")}
Page: {item.get("page")}
Similarity score: {item.get("score")}

Physiological evidence:
{item.get("text") or "No text available."}

Mechanisms:
{item.get("mechanism", [])}

Equations:
{item.get("equation", [])}
""".strip()
        )

    return "\n\n".join(formatted)


def _format_simulation(
    simulation_observation: dict[str, Any],
) -> str:
    if not simulation_observation.get("available"):
        return (
            "No SimulationState was supplied. "
            "Do not describe current simulation values."
        )

    values = simulation_observation.get(
        "values",
        {},
    )

    if not values:
        return (
            "SimulationState was supplied but contains "
            "no usable values."
        )

    lines = [
        "Current CARDIA SimulationState observations:"
    ]

    for key, value in values.items():
        lines.append(
            f"- {key}: {value}"
        )

    return "\n".join(lines)


def _format_counterfactual(
    counterfactual: dict[str, Any] | None,
) -> str:
    """
    Format a completed CARDIA counterfactual result
    for Gemini.

    Counterfactual values are simulation observations.
    Gemini must explain them using retrieved physiology
    evidence rather than inventing or recalculating results.
    """

    if not counterfactual:
        return (
            "No counterfactual simulation was supplied. "
            "Do not describe a counterfactual result."
        )

    parameter = counterfactual.get(
        "parameter",
        "unknown",
    )

    baseline_value = counterfactual.get(
        "baseline_value"
    )

    intervention_value = counterfactual.get(
        "intervention_value"
    )

    change_percent = counterfactual.get(
        "change_percent"
    )

    duration = counterfactual.get(
        "duration"
    )

    comparison = counterfactual.get(
        "comparison",
        {},
    )

    lines = [
        "Completed CARDIA counterfactual simulation observation:",
        f"- Parameter: {parameter}",
        f"- Baseline parameter value: {baseline_value}",
        f"- Intervention parameter value: {intervention_value}",
        f"- Parameter change: {change_percent}%",
        f"- Simulation duration: {duration} seconds",
        "",
        "Observed baseline/intervention comparisons:",
    ]

    for metric, values in comparison.items():
        baseline = values.get("baseline")
        intervention = values.get("intervention")
        difference = values.get("difference", {})

        lines.append(
            f"- {metric}: "
            f"baseline={baseline}, "
            f"intervention={intervention}, "
            f"absolute_difference="
            f"{difference.get('absolute')}, "
            f"percent_difference="
            f"{difference.get('percent')}%"
        )

    lines.extend(
        [
            "",
            "Interpretation rule:",
            "These numerical values are direct observations "
            "from the CARDIA counterfactual simulation. "
            "Do not recalculate, modify, or invent them.",
            "Use retrieved physiological evidence to explain "
            "the mechanism behind the observed differences.",
        ]
    )

    return "\n".join(lines)


def _format_session_history(
    history: list[dict[str, Any]],
) -> str:
    """
    Format previous explanations from the current
    CARDIA simulation session.

    Session history is conversational context only.
    It must never override retrieved physiological evidence.
    """

    if not history:
        return (
            "No previous conversation exists in this session."
        )

    formatted = []

    for index, item in enumerate(
        history,
        start=1,
    ):
        formatted.append(
            f"""
PREVIOUS SESSION EXCHANGE {index}
Question:
{item.get("question")}

Previous CARDIA answer:
{item.get("answer")}

Previous confidence:
{item.get("confidence")}

Previous simulation context:
{item.get("simulation_context")}
""".strip()
        )

    return "\n\n".join(formatted)


def _generate_with_model(
    model_name: str,
    prompt: str,
) -> str:
    """
    Call Gemini using one specific model.
    """

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )

    if not response.text:
        raise RuntimeError(
            f"Gemini model '{model_name}' returned an empty response."
        )

    return response.text.strip()


def generate_grounded_answer(
    question: str,
    grounded_response: dict[str, Any],
    session_history: list[dict[str, Any]] | None = None,
    counterfactual: dict[str, Any] | None = None,
) -> str:
    """
    Generate a student-facing answer from the grounded
    CARDIA response package.

    Gemini receives:
    - retrieved physiological evidence
    - validated simulation observations
    - optional counterfactual simulation observations
    - previous session exchanges as conversational context

    Gemini does not control or modify the simulation.

    Model strategy:
    1. Try gemini-3.5-flash-lite first.
    2. If unavailable, try gemini-3.5-flash.
    3. If unavailable, try gemini-3.6-flash.
    4. If all models fail, return a controlled error.
    """

    evidence = grounded_response.get(
        "evidence",
        [],
    )

    simulation_observation = grounded_response.get(
        "simulation_observation",
        {},
    )

    answer_mode = grounded_response.get(
        "answer_mode",
        "physiology",
    )

    session_history = session_history or []

    prompt = f"""
{SYSTEM_INSTRUCTIONS}

ANSWER MODE:
{answer_mode}

STUDENT QUESTION:
{question}

PREVIOUS SESSION CONTEXT:
{_format_session_history(session_history)}

RETRIEVED CARDIOLOGY EVIDENCE:
{_format_evidence(evidence)}

SIMULATION OBSERVATION:
{_format_simulation(simulation_observation)}

COUNTERFACTUAL SIMULATION:
{_format_counterfactual(counterfactual)}

GROUNDING REQUIREMENTS:

- Answer the student's current question directly.
- Use previous session context when necessary to resolve
  references such as "it", "that", "this", or "the previous value".
- Do not treat previous answers as authoritative evidence.
- Use the retrieved evidence as the factual basis.
- If SimulationState is unavailable, do not invent
  current CARDIA values.
- If a counterfactual simulation is supplied, treat its
  numerical results as direct simulation observations.
- Never invent or recalculate counterfactual values.
- If this is a hypothetical question without an actual
  counterfactual result, explicitly identify the explanation
  as physiological reasoning rather than an actual simulation result.
- If this is a simulation question, clearly separate
  observed values from physiological interpretation.
- If this is a completed counterfactual question, clearly
  distinguish:
    1. what CARDIA observed,
    2. what established physiology explains,
    3. what remains unsupported by the retrieved evidence.
- Report simulation values as observations unless
  supporting evidence justifies further interpretation.
- Do not label a simulation state as stable, normal,
  abnormal, healthy, pathological, or baseline unless
  the supplied context explicitly supports that label.
- Do not infer a diagnosis from the simulation values.
- Do not create fake references.
- Keep the answer focused and medically accurate.
- Do not introduce physiological facts that are absent
  from the retrieved evidence unless they are directly
  necessary to interpret the supplied evidence.
- If the retrieved evidence is insufficient, say so.
- For hypothetical reasoning, distinguish expected
  physiological effects from actual CARDIA results.
- If previous session context conflicts with retrieved
  evidence, follow the retrieved evidence.

Now provide the final student-facing answer.
"""

    errors_seen = []

    for model_name in MODEL_CHAIN:
        try:
            return _generate_with_model(
                model_name,
                prompt,
            )

        except (
            errors.ServerError,
            errors.ClientError,
        ) as exc:
            errors_seen.append(
                f"{model_name}: {exc}"
            )

    raise RuntimeError(
        "CARDIA could not generate an answer because "
        "all configured Gemini models were unavailable. "
        + " | ".join(errors_seen)
    )