"""
CARDIA Pure RAG Response Generator.

Generates structured, grounded answers from retrieved
physiology evidence and simulation observations.

No external LLM is used. All responses are deterministic
and grounded in the CARDIA knowledge base.

This module preserves the same function signature as the
previous Gemini-based generator so that existing imports
in rag/api.py and backend/api/rag_routes.py remain valid.
"""

from typing import Any


# ============================================================
# PHYSIOLOGICAL REFERENCE RANGES
# ============================================================
#
# Used only for identifying which simulation values to
# discuss. These are NOT clinical diagnostic thresholds.

TYPICAL_VALUES = {
    "heart_rate": {"low": 60.0, "high": 100.0, "unit": "bpm"},
    "systolic_bp": {"low": 90.0, "high": 140.0, "unit": "mmHg"},
    "diastolic_bp": {"low": 60.0, "high": 90.0, "unit": "mmHg"},
    "map": {"low": 65.0, "high": 105.0, "unit": "mmHg"},
    "cardiac_output": {"low": 4.0, "high": 8.0, "unit": "L/min"},
    "stroke_volume": {"low": 50.0, "high": 100.0, "unit": "mL"},
    "edv": {"low": 90.0, "high": 140.0, "unit": "mL"},
    "esv": {"low": 20.0, "high": 60.0, "unit": "mL"},
    "blood_volume": {"low": 4.0, "high": 5.5, "unit": "L"},
    "contractility": {"low": 0.7, "high": 1.3, "unit": "multiplier"},
    "svr": {"low": 0.7, "high": 1.3, "unit": "multiplier"},
    "lv_pressure": {"low": 100.0, "high": 140.0, "unit": "mmHg"},
    "aortic_pressure": {"low": 80.0, "high": 130.0, "unit": "mmHg"},
}


# ============================================================
# SECTION FORMATTERS
# ============================================================

def _format_observation(
    simulation_observation: dict[str, Any],
) -> str:
    """
    Format the OBSERVATION section from simulation state.
    """

    lines = ["OBSERVATION"]

    if not simulation_observation.get("available"):
        lines.append(
            "No live CARDIA simulation state was supplied."
        )
        return "\n".join(lines)

    values = simulation_observation.get("values", {})

    if not values:
        lines.append(
            "Simulation state was supplied but contains "
            "no values."
        )
        return "\n".join(lines)

    lines.append("Current simulation observations:")

    for key, value in values.items():
        if isinstance(value, float):
            lines.append(f"  {key}: {value:.2f}")
        elif isinstance(value, dict):
            for sub_key, sub_val in value.items():
                if isinstance(sub_val, float):
                    lines.append(
                        f"  {key}.{sub_key}: {sub_val:.2f}"
                    )
                elif isinstance(sub_val, dict):
                    for k3, v3 in sub_val.items():
                        if isinstance(v3, (int, float)):
                            lines.append(
                                f"  {key}.{sub_key}.{k3}: {v3:.2f}"
                            )
                        else:
                            lines.append(
                                f"  {key}.{sub_key}.{k3}: {v3}"
                            )
                else:
                    lines.append(
                        f"  {key}.{sub_key}: {sub_val}"
                    )
        else:
            lines.append(f"  {key}: {value}")

    return "\n".join(lines)


def _format_counterfactual_observation(
    counterfactual: dict[str, Any],
) -> str:
    """
    Format counterfactual comparison in the OBSERVATION section.
    """

    if not counterfactual:
        return ""

    parameter = counterfactual.get("parameter", "unknown")
    baseline = counterfactual.get("baseline_value")
    intervention = counterfactual.get("intervention_value")
    change = counterfactual.get("change_percent")
    duration = counterfactual.get("duration")
    comparison = counterfactual.get("comparison", {})

    lines = [
        "",
        "Counterfactual simulation observation:",
        f"  Parameter: {parameter}",
        f"  Baseline: {baseline}",
        f"  Intervention: {intervention}",
        f"  Change: {change}%",
        f"  Duration: {duration} seconds",
        "",
        "Observed comparisons:",
    ]

    for metric, vals in comparison.items():
        b = vals.get("baseline")
        iv = vals.get("intervention")
        diff = vals.get("difference", {})
        abs_d = diff.get("absolute")
        pct_d = diff.get("percent")
        lines.append(
            f"  {metric}: baseline={b}, "
            f"intervention={iv}, "
            f"change={abs_d} ({pct_d}%)"
        )

    return "\n".join(lines)


def _format_retrieved_physiology(
    evidence: list[dict[str, Any]],
) -> str:
    """
    Format the RETRIEVED PHYSIOLOGY section.
    """

    lines = ["", "RETRIEVED PHYSIOLOGY"]

    if not evidence:
        lines.append(
            "No relevant evidence was retrieved from the "
            "CARDIA knowledge base."
        )
        return "\n".join(lines)

    for index, item in enumerate(evidence, start=1):
        title = item.get("title", "Untitled")
        text = item.get("text", "No text available.")
        topic = item.get("topic", "")
        organ = item.get("organ", "")
        source_title = item.get("source_title", "")
        author = item.get("author", "")
        score = item.get("score", 0)
        mechanisms = item.get("mechanism", [])
        equations = item.get("equation", [])

        lines.append("")
        lines.append(f"Evidence {index}: {title}")
        if topic:
            lines.append(f"  Topic: {topic}")
        if organ:
            lines.append(f"  Organ: {organ}")
        lines.append(f"  Source: {source_title}")
        if author:
            lines.append(f"  Author: {author}")
        lines.append(f"  Similarity: {score:.3f}")
        lines.append(f"  Content: {text}")

        if mechanisms:
            lines.append(
                f"  Mechanisms: {', '.join(str(m) for m in mechanisms)}"
            )
        if equations:
            lines.append(
                f"  Equations: {', '.join(str(e) for e in equations)}"
            )

    return "\n".join(lines)


def _format_sources(
    evidence: list[dict[str, Any]],
) -> str:
    """
    Format the SOURCES section.
    """

    lines = ["", "SOURCES"]

    if not evidence:
        lines.append("No sources available.")
        return "\n".join(lines)

    seen = set()

    for item in evidence:
        source_title = item.get("source_title", "")
        author = item.get("author", "")
        chapter = item.get("chapter", "")
        page = item.get("page", "")

        key = (source_title, author, chapter, page)

        if key in seen:
            continue

        seen.add(key)

        parts = []
        if source_title:
            parts.append(source_title)
        if author:
            parts.append(f"by {author}")
        if chapter:
            parts.append(f"Ch. {chapter}")
        if page:
            parts.append(f"p. {page}")

        if parts:
            lines.append(f"  - {', '.join(parts)}")

    return "\n".join(lines)


# ============================================================
# RULE-BASED INTERPRETATION
# ============================================================

def _classify_value(
    key: str,
    value: float,
) -> str | None:
    """
    Classify a simulation value as low, normal, or high.
    Returns None if no reference range exists.
    """

    ref = TYPICAL_VALUES.get(key)
    if ref is None:
        return None

    if value < ref["low"]:
        return "low"

    if value > ref["high"]:
        return "high"

    return "normal"


def _interpret_blood_volume(
    values: dict[str, Any],
    evidence_topics: set[str],
) -> list[str]:
    """
    Interpret blood volume effects on hemodynamics.
    """

    bv = values.get("blood_volume")
    if bv is None or not isinstance(bv, (int, float)):
        return []

    classification = _classify_value("blood_volume", bv)
    if classification == "normal":
        return []

    lines = []

    if classification == "low":
        lines.append(
            f"Blood volume ({bv:.2f} L) is below the typical "
            f"resting range. Reduced blood volume decreases "
            f"venous return and preload, which reduces "
            f"end-diastolic volume (Frank-Starling mechanism) "
            f"and consequently reduces stroke volume and "
            f"cardiac output."
        )

    elif classification == "high":
        lines.append(
            f"Blood volume ({bv:.2f} L) is above the typical "
            f"resting range. Increased blood volume increases "
            f"venous return and preload, which raises "
            f"end-diastolic volume and may increase stroke "
            f"volume via the Frank-Starling mechanism."
        )

    return lines


def _interpret_svr(
    values: dict[str, Any],
    evidence_topics: set[str],
) -> list[str]:
    """
    Interpret systemic vascular resistance effects.
    """

    svr = values.get("svr")
    if svr is None or not isinstance(svr, (int, float)):
        return []

    classification = _classify_value("svr", svr)
    if classification == "normal":
        return []

    lines = []

    if classification == "high":
        lines.append(
            f"Systemic vascular resistance ({svr:.2f}) is "
            f"elevated, indicating increased afterload. "
            f"The left ventricle must generate greater "
            f"pressure to eject blood against higher "
            f"systemic resistance, increasing myocardial "
            f"oxygen demand."
        )

    elif classification == "low":
        lines.append(
            f"Systemic vascular resistance ({svr:.2f}) is "
            f"reduced, indicating decreased afterload. "
            f"Lower systemic resistance reduces the "
            f"pressure workload on the left ventricle, "
            f"which may facilitate increased stroke volume."
        )

    return lines


def _interpret_heart_rate(
    values: dict[str, Any],
    evidence_topics: set[str],
) -> list[str]:
    """
    Interpret heart rate effects on cardiac output and filling.
    """

    hr = values.get("heart_rate")
    if hr is None or not isinstance(hr, (int, float)):
        return []

    classification = _classify_value("heart_rate", hr)
    if classification == "normal":
        return []

    lines = []

    if classification == "high":
        lines.append(
            f"Heart rate ({hr:.1f} bpm) is elevated. "
            f"Tachycardia reduces diastolic filling time, "
            f"which may limit end-diastolic volume. While "
            f"heart rate is a direct determinant of cardiac "
            f"output (CO = HR x SV), excessively high rates "
            f"can impair ventricular filling and reduce "
            f"stroke volume."
        )

    elif classification == "low":
        lines.append(
            f"Heart rate ({hr:.1f} bpm) is reduced. "
            f"Bradycardia extends diastolic filling time, "
            f"which may increase end-diastolic volume. "
            f"However, cardiac output depends on both "
            f"heart rate and stroke volume; a low heart "
            f"rate may reduce cardiac output if stroke "
            f"volume does not compensate."
        )

    return lines


def _interpret_contractility(
    values: dict[str, Any],
    evidence_topics: set[str],
) -> list[str]:
    """
    Interpret contractility effects on ejection.
    """

    ct = values.get("contractility")
    if ct is None or not isinstance(ct, (int, float)):
        return []

    classification = _classify_value("contractility", ct)
    if classification == "normal":
        return []

    lines = []

    if classification == "high":
        lines.append(
            f"Contractility ({ct:.2f}) is elevated. "
            f"Enhanced myocardial contractility increases "
            f"the rate and extent of ventricular ejection, "
            f"reducing end-systolic volume and increasing "
            f"stroke volume."
        )

    elif classification == "low":
        lines.append(
            f"Contractility ({ct:.2f}) is reduced. "
            f"Decreased myocardial contractility impairs "
            f"ventricular ejection, increasing end-systolic "
            f"volume and reducing stroke volume."
        )

    return lines


def _interpret_cardiac_output(
    values: dict[str, Any],
    evidence_topics: set[str],
) -> list[str]:
    """
    Interpret cardiac output in the context of its determinants.
    """

    co = values.get("cardiac_output")
    if co is None or not isinstance(co, (int, float)):
        return []

    classification = _classify_value("cardiac_output", co)
    if classification == "normal":
        return []

    hr = values.get("heart_rate")
    sv = values.get("stroke_volume")

    lines = []

    if classification == "low":
        detail = "Cardiac output is determined by heart rate "
        if isinstance(hr, (int, float)):
            detail += f"(currently {hr:.1f} bpm) "
        detail += "times stroke volume"
        if isinstance(sv, (int, float)):
            detail += f" (currently {sv:.1f} mL)"
        detail += (
            ". A reduced cardiac output may reflect "
            "decreased heart rate, decreased stroke volume, "
            "or both."
        )
        lines.append(detail)

    elif classification == "high":
        detail = "Cardiac output is elevated"
        parts = []
        if isinstance(hr, (int, float)):
            parts.append(f"heart rate {hr:.1f} bpm")
        if isinstance(sv, (int, float)):
            parts.append(f"stroke volume {sv:.1f} mL")
        if parts:
            detail += f", driven by {', '.join(parts)}"
        detail += "."
        lines.append(detail)

    return lines


def _interpret_blood_pressure(
    values: dict[str, Any],
    evidence_topics: set[str],
) -> list[str]:
    """
    Interpret arterial blood pressure values.
    """

    map_val = values.get("map")

    lines = []

    if isinstance(map_val, (int, float)):
        classification = _classify_value("map", map_val)
        if classification == "high":
            lines.append(
                f"Mean arterial pressure ({map_val:.1f} "
                f"mmHg) is elevated, reflecting increased "
                f"systemic vascular resistance or cardiac "
                f"output. This increases ventricular "
                f"afterload."
            )
        elif classification == "low":
            lines.append(
                f"Mean arterial pressure ({map_val:.1f} "
                f"mmHg) is reduced, which may indicate "
                f"insufficient perfusion pressure."
            )

    return lines


def _interpret_edv_esv(
    values: dict[str, Any],
    evidence_topics: set[str],
) -> list[str]:
    """
    Interpret EDV and ESV in relation to stroke volume.
    """

    edv = values.get("edv")
    esv = values.get("esv")
    sv = values.get("stroke_volume")

    if not all(
        isinstance(v, (int, float))
        for v in [edv, esv, sv]
    ):
        return []

    lines = []

    edv_class = _classify_value("edv", edv)
    esv_class = _classify_value("esv", esv)

    if edv_class == "low":
        lines.append(
            f"End-diastolic volume ({edv:.1f} mL) is "
            f"reduced, indicating decreased ventricular "
            f"filling. According to the Frank-Starling "
            f"mechanism, reduced preload leads to reduced "
            f"stroke volume."
        )
    elif edv_class == "high":
        lines.append(
            f"End-diastolic volume ({edv:.1f} mL) is "
            f"elevated, indicating increased ventricular "
            f"filling. The Frank-Starling mechanism "
            f"predicts increased stroke volume from "
            f"increased preload."
        )

    if esv_class == "high":
        lines.append(
            f"End-systolic volume ({esv:.1f} mL) is "
            f"elevated, suggesting reduced ejection "
            f"efficiency. This may reflect decreased "
            f"contractility or increased afterload."
        )
    elif esv_class == "low":
        lines.append(
            f"End-systolic volume ({esv:.1f} mL) is "
            f"reduced, indicating effective ventricular "
            f"ejection. This may reflect enhanced "
            f"contractility or reduced afterload."
        )

    return lines


def _interpret_counterfactual(
    counterfactual: dict[str, Any],
    evidence_topics: set[str],
) -> list[str]:
    """
    Generate interpretation for counterfactual simulation results.
    """

    if not counterfactual:
        return []

    parameter = counterfactual.get("parameter", "unknown")
    baseline = counterfactual.get("baseline_value")
    intervention = counterfactual.get("intervention_value")
    comparison = counterfactual.get("comparison", {})

    lines = [
        f"The counterfactual simulation changed {parameter} "
        f"from {baseline} to {intervention}.",
    ]

    if parameter == "heart_rate":
        if isinstance(intervention, (int, float)) and isinstance(baseline, (int, float)):
            if intervention > baseline:
                lines.append(
                    "Increased heart rate reduces diastolic "
                    "filling time, which may limit "
                    "end-diastolic volume. Cardiac output "
                    "= HR x SV, so the net effect on cardiac "
                    "output depends on whether stroke volume "
                    "compensates."
                )
            else:
                lines.append(
                    "Decreased heart rate extends diastolic "
                    "filling time, which may increase "
                    "end-diastolic volume and stroke volume "
                    "via the Frank-Starling mechanism."
                )

    elif parameter == "contractility":
        if isinstance(intervention, (int, float)) and isinstance(baseline, (int, float)):
            if intervention > baseline:
                lines.append(
                    "Increased contractility enhances "
                    "ventricular ejection, reducing "
                    "end-systolic volume and increasing "
                    "stroke volume."
                )
            else:
                lines.append(
                    "Decreased contractility impairs "
                    "ventricular ejection, increasing "
                    "end-systolic volume and reducing "
                    "stroke volume."
                )

    elif parameter == "svr":
        if isinstance(intervention, (int, float)) and isinstance(baseline, (int, float)):
            if intervention > baseline:
                lines.append(
                    "Increased systemic vascular resistance "
                    "raises afterload, requiring greater "
                    "ventricular pressure generation and "
                    "increasing myocardial oxygen demand."
                )
            else:
                lines.append(
                    "Decreased systemic vascular resistance "
                    "reduces afterload, lowering the "
                    "pressure workload on the ventricle."
                )

    if comparison:
        lines.append("")
        lines.append("Observed changes:")
        for metric, vals in comparison.items():
            b = vals.get("baseline")
            iv = vals.get("intervention")
            diff = vals.get("difference", {})
            pct = diff.get("percent")
            if isinstance(b, (int, float)) and isinstance(iv, (int, float)):
                direction = "increased" if iv > b else "decreased"
                lines.append(
                    f"  - {metric}: {direction} from "
                    f"{b:.2f} to {iv:.2f} ({pct}%)"
                )

    return lines


def _build_interpretation(
    simulation_observation: dict[str, Any],
    evidence: list[dict[str, Any]],
    counterfactual: dict[str, Any] | None,
) -> str:
    """
    Build the INTERPRETATION section using rule-based
    physiological reasoning.
    """

    lines = ["", "INTERPRETATION"]

    values = simulation_observation.get("values", {}) if simulation_observation.get("available") else {}

    evidence_topics = set()
    for item in evidence:
        topic = item.get("topic")
        if topic:
            evidence_topics.add(topic)

    interpretation_rules = [
        _interpret_blood_volume,
        _interpret_svr,
        _interpret_heart_rate,
        _interpret_contractility,
        _interpret_cardiac_output,
        _interpret_blood_pressure,
        _interpret_edv_esv,
    ]

    explanations = []

    for rule_fn in interpretation_rules:
        result = rule_fn(values, evidence_topics)
        explanations.extend(result)

    if counterfactual:
        cf_explanations = _interpret_counterfactual(
            counterfactual, evidence_topics
        )
        explanations.extend(cf_explanations)

    if explanations:
        lines.append(
            "Based on the retrieved CARDIA physiology "
            "knowledge base and the current simulation "
            "observations:"
        )
        lines.append("")
        for explanation in explanations:
            lines.append(f"  {explanation}")
            lines.append("")
    else:
        if not evidence:
            lines.append(
                "Insufficient evidence in the CARDIA "
                "knowledge base to explain this observation. "
                "No relevant physiology was retrieved for "
                "the current question."
            )
        elif not values:
            lines.append(
                "No simulation state was supplied. The "
                "retrieved physiology provides general "
                "cardiovascular knowledge but cannot be "
                "connected to specific simulation "
                "observations without simulation data."
            )
        else:
            lines.append(
                "The current simulation values fall within "
                "typical ranges. The retrieved physiology "
                "provides relevant cardiovascular "
                "background knowledge."
            )

    return "\n".join(lines)


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def generate_grounded_answer(
    question: str,
    grounded_response: dict[str, Any],
    session_history: list[dict[str, Any]] | None = None,
    counterfactual: dict[str, Any] | None = None,
) -> str:
    """
    Generate a structured, grounded answer from the CARDIA
    knowledge base and simulation observations.

    This function is entirely deterministic. It does NOT
    call any external LLM.

    Parameters
    ----------
    question:
        The user's natural-language question.

    grounded_response:
        The structured context package produced by
        answer_engine.create_grounded_response().

    session_history:
        Optional previous Q&A for conversational context.

    counterfactual:
        Optional counterfactual simulation result.

    Returns
    -------
    str
        A structured, grounded text response containing:
        OBSERVATION, RETRIEVED PHYSIOLOGY, INTERPRETATION,
        and SOURCES sections.
    """

    evidence = grounded_response.get("evidence", [])
    simulation_observation = grounded_response.get(
        "simulation_observation", {}
    )

    sections = []

    sections.append(
        _format_observation(simulation_observation)
    )

    cf_obs = _format_counterfactual_observation(
        counterfactual
    )
    if cf_obs:
        sections.append(cf_obs)

    sections.append(
        _format_retrieved_physiology(evidence)
    )

    sections.append(
        _build_interpretation(
            simulation_observation,
            evidence,
            counterfactual,
        )
    )

    sections.append(_format_sources(evidence))

    return "\n\n".join(sections)
