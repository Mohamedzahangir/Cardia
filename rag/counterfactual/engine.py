"""
CARDIA Counterfactual Engine.

Runs an independent baseline and intervention trajectory using the
existing cardiovascular simulation engine.

This module NEVER modifies the simulation package.
It creates a deep copy of the supplied SimulationState, applies an
intervention to that copy, and runs both branches independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from simulation.cardiovascular import simulate
from simulation.state import (
    SimulationState,
    copy_state,
    validate_state,
)
from simulation.adapter import state_to_rag_dict


SUPPORTED_PARAMETERS = {
    "heart_rate": {
        "state_field": "heart_rate_bpm",
        "minimum": 40.0,
        "maximum": 180.0,
        "unit": "bpm",
    },
    "contractility": {
        "state_field": "contractility",
        "minimum": 0.2,
        "maximum": 3.0,
        "unit": "multiplier",
    },
    "svr": {
        "state_field": "circulation.systemic_vascular_resistance",
        "minimum": 0.3,
        "maximum": 3.5,
        "unit": "multiplier",
    },
}


@dataclass
class CounterfactualResult:
    """Complete result of one baseline/intervention comparison."""

    parameter: str
    baseline_value: float
    intervention_value: float
    change_percent: float
    duration: float
    dt: float

    baseline_trajectory: list[dict[str, Any]]
    intervention_trajectory: list[dict[str, Any]]

    baseline_final_state: dict[str, Any]
    intervention_final_state: dict[str, Any]

    metrics: dict[str, Any]
    stability_score: float


def _validate_intervention(
    parameter: str,
    value: float,
) -> None:
    """Validate the requested intervention."""

    if parameter not in SUPPORTED_PARAMETERS:
        supported = ", ".join(
            sorted(SUPPORTED_PARAMETERS.keys())
        )

        raise ValueError(
            f"Unsupported counterfactual parameter "
            f"'{parameter}'. Supported parameters: {supported}"
        )

    limits = SUPPORTED_PARAMETERS[parameter]

    if value < limits["minimum"]:
        raise ValueError(
            f"{parameter} intervention value {value} "
            f"is below the minimum {limits['minimum']}."
        )

    if value > limits["maximum"]:
        raise ValueError(
            f"{parameter} intervention value {value} "
            f"is above the maximum {limits['maximum']}."
        )


def _apply_intervention(
    state: SimulationState,
    parameter: str,
    value: float,
) -> SimulationState:
    """
    Apply an intervention to an independent copy of the state.

    The supplied state is never modified.
    """

    intervention_state = copy_state(state)

    if parameter == "heart_rate":
        intervention_state.heart_rate_bpm = value

    elif parameter == "contractility":
        intervention_state.contractility = value

    elif parameter == "svr":
        intervention_state.circulation.systemic_vascular_resistance = value

    else:
        raise ValueError(
            f"Unsupported counterfactual parameter: {parameter}"
        )

    validate_state(intervention_state)

    return intervention_state


def _extract_trajectory(
    trajectory: list[SimulationState],
) -> list[dict[str, Any]]:
    """
    Convert SimulationState objects into RAG-compatible dictionaries.
    """

    return [
        state_to_rag_dict(state)
        for state in trajectory
    ]


def _percent_change(
    baseline: float,
    intervention: float,
) -> float:
    """Calculate percentage change relative to baseline."""

    if baseline == 0:
        return 0.0

    return (
        (intervention - baseline)
        / abs(baseline)
    ) * 100.0


def _safe_difference(
    baseline: float,
    intervention: float,
) -> dict[str, float]:
    """Return absolute and percentage differences."""

    return {
        "absolute": round(
            intervention - baseline,
            4,
        ),
        "percent": round(
            _percent_change(
                baseline,
                intervention,
            ),
            3,
        ),
    }


def _calculate_metrics(
    baseline_final: dict[str, Any],
    intervention_final: dict[str, Any],
) -> dict[str, Any]:
    """
    Compare clinically meaningful simulation outputs.

    These are simulation observations, not clinical diagnoses.
    """

    metric_names = [
        "heart_rate",
        "systolic_bp",
        "diastolic_bp",
        "map",
        "cardiac_output",
        "stroke_volume",
        "edv",
        "esv",
        "lv_pressure",
        "aortic_pressure",
        "blood_volume",
        "contractility",
        "svr",
    ]

    differences: dict[str, Any] = {}

    for name in metric_names:
        baseline_value = baseline_final.get(name)
        intervention_value = intervention_final.get(name)

        if not isinstance(
            baseline_value,
            (int, float),
        ):
            continue

        if not isinstance(
            intervention_value,
            (int, float),
        ):
            continue

        differences[name] = {
            "baseline": baseline_value,
            "intervention": intervention_value,
            "difference": _safe_difference(
                baseline_value,
                intervention_value,
            ),
        }

    return differences


def _calculate_stability_score(
    trajectory: list[dict[str, Any]],
) -> float:
    """
    Calculate a basic numerical stability score.

    This score reflects whether the simulated trajectory remains
    numerically usable. It is NOT clinical stability or patient safety.
    """

    if not trajectory:
        return 0.0

    required_metrics = [
        "heart_rate",
        "systolic_bp",
        "diastolic_bp",
        "map",
        "cardiac_output",
        "stroke_volume",
        "edv",
        "esv",
    ]

    valid_points = 0
    total_points = len(trajectory)

    for state in trajectory:
        valid = True

        for metric in required_metrics:
            value = state.get(metric)

            if not isinstance(
                value,
                (int, float),
            ):
                valid = False
                break

            if not (
                float("-inf")
                < float(value)
                < float("inf")
            ):
                valid = False
                break

        if valid:
            valid_points += 1

    score = valid_points / total_points

    return round(
        max(
            0.0,
            min(1.0, score),
        ),
        3,
    )


def run_counterfactual(
    state: SimulationState,
    parameter: str,
    intervention_value: float,
    duration: float,
    dt: float = 0.01,
) -> CounterfactualResult:
    """
    Run a baseline and intervention simulation.

    Parameters
    ----------
    state:
        Starting SimulationState.

    parameter:
        One of:
        - heart_rate
        - contractility
        - svr

    intervention_value:
        New value applied to the intervention branch.

    duration:
        Simulation duration in seconds.

    dt:
        Simulation timestep in seconds.

    Returns
    -------
    CounterfactualResult
        Baseline and intervention trajectories plus comparison metrics.
    """

    if duration <= 0:
        raise ValueError(
            f"duration must be > 0, got {duration}"
        )

    if dt <= 0:
        raise ValueError(
            f"dt must be > 0, got {dt}"
        )

    validate_state(state)

    intervention_value = float(
        intervention_value
    )

    _validate_intervention(
        parameter,
        intervention_value,
    )

    baseline_value = {
        "heart_rate": state.heart_rate_bpm,
        "contractility": state.contractility,
        "svr": state.circulation.systemic_vascular_resistance,
    }[parameter]

    baseline_state = copy_state(state)

    intervention_state = _apply_intervention(
        state=state,
        parameter=parameter,
        value=intervention_value,
    )

    baseline_trajectory_states = simulate(
        state=baseline_state,
        duration=duration,
        dt=dt,
    )

    intervention_trajectory_states = simulate(
        state=intervention_state,
        duration=duration,
        dt=dt,
    )

    baseline_trajectory = _extract_trajectory(
        baseline_trajectory_states
    )

    intervention_trajectory = _extract_trajectory(
        intervention_trajectory_states
    )

    baseline_final_state = baseline_trajectory[-1]
    intervention_final_state = intervention_trajectory[-1]

    metrics = _calculate_metrics(
        baseline_final=baseline_final_state,
        intervention_final=intervention_final_state,
    )

    baseline_stability = _calculate_stability_score(
        baseline_trajectory
    )

    intervention_stability = _calculate_stability_score(
        intervention_trajectory
    )

    stability_score = round(
        min(
            baseline_stability,
            intervention_stability,
        ),
        3,
    )

    change_percent = round(
        _percent_change(
            baseline_value,
            intervention_value,
        ),
        3,
    )

    return CounterfactualResult(
        parameter=parameter,
        baseline_value=float(baseline_value),
        intervention_value=intervention_value,
        change_percent=change_percent,
        duration=float(duration),
        dt=float(dt),
        baseline_trajectory=baseline_trajectory,
        intervention_trajectory=intervention_trajectory,
        baseline_final_state=baseline_final_state,
        intervention_final_state=intervention_final_state,
        metrics=metrics,
        stability_score=stability_score,
    )