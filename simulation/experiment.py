"""CARDIA Experiment & Counterfactual Simulation Engine.

Operates on the REAL SimulationState using deterministic 0D cardiovascular ODEs.
Provides:
- Safe state cloning (never mutates baseline state)
- Explicit physiological interventions
- Preset pathophysiological scenarios (hemorrhage, hypertension, tachycardia, ischemia)
- Baseline vs. Intervention trajectory generation
- Real differential comparison metrics
- Latent parameter inference hook (ML)
- Hemodynamic stability quantification
"""

from __future__ import annotations

import copy
import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from simulation.state import (
    SimulationState,
    copy_state,
    validate_state,
    state_to_dict,
)
from simulation.cardiovascular import simulate
from simulation.adapter import state_to_ml_features, state_to_rag_dict


# ---------------------------------------------------------------------------
# Physiological Intervention Bounds & Clamping
# ---------------------------------------------------------------------------

PHYSIOLOGICAL_BOUNDS = {
    "blood_volume": {"min": 1.5, "max": 8.0, "unit": "L"},
    "heart_rate": {"min": 30.0, "max": 240.0, "unit": "bpm"},
    "contractility": {"min": 0.2, "max": 3.0, "unit": "x"},
    "svr": {"min": 0.2, "max": 4.0, "unit": "relative"},  # Relative multiplier to baseline 1.0 (or ~1120 dyn*s/cm5)
}


@dataclass
class Intervention:
    """Explicit representation of a single physiological parameter perturbation."""
    parameter: str
    baseline_value: float
    new_value: float
    delta: float
    unit: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parameter": self.parameter,
            "baseline_value": round(self.baseline_value, 3),
            "new_value": round(self.new_value, 3),
            "delta": round(self.delta, 3),
            "unit": self.unit,
        }


def clamp_parameter(param: str, value: float) -> float:
    """Clamps parameter values within physiologically valid and safe limits."""
    bounds = PHYSIOLOGICAL_BOUNDS.get(param)
    if bounds:
        return max(bounds["min"], min(value, bounds["max"]))
    return value


def apply_intervention(state: SimulationState, param: str, target_value: float) -> tuple[SimulationState, Intervention]:
    """Applies an intervention to an independent clone of *state*.

    The input *state* is guaranteed to NEVER be mutated.
    Returns (cloned_state_with_intervention, intervention_record).
    """
    cloned = copy_state(state)
    param_clean = param.lower().strip()
    clamped_val = clamp_parameter(param_clean, float(target_value))

    if param_clean in ("blood_volume", "blood_volume_l", "vol"):
        baseline_val = cloned.circulation.blood_volume_l
        cloned.circulation.blood_volume_l = clamped_val
        unit = "L"
        canonical_param = "blood_volume"
    elif param_clean in ("heart_rate", "heart_rate_bpm", "hr"):
        baseline_val = cloned.heart_rate_bpm
        cloned.heart_rate_bpm = clamped_val
        unit = "bpm"
        canonical_param = "heart_rate"
    elif param_clean in ("contractility", "inotropy"):
        baseline_val = cloned.contractility
        cloned.contractility = clamped_val
        unit = "x"
        canonical_param = "contractility"
    elif param_clean in ("svr", "systemic_vascular_resistance"):
        baseline_val = cloned.circulation.systemic_vascular_resistance
        # If user passed raw dyn*s/cm5 (e.g. 1600), normalize by baseline 1120
        if clamped_val > 10.0:
            clamped_val = clamped_val / 1120.0
        cloned.circulation.systemic_vascular_resistance = clamped_val
        unit = "relative"
        canonical_param = "svr"
    else:
        raise ValueError(f"Unsupported physiological intervention parameter: '{param}'")

    validate_state(cloned)

    interv = Intervention(
        parameter=canonical_param,
        baseline_value=baseline_val,
        new_value=clamped_val,
        delta=clamped_val - baseline_val,
        unit=unit,
    )
    return cloned, interv


# ---------------------------------------------------------------------------
# Pathophysiological Scenarios
# ---------------------------------------------------------------------------

def apply_scenario(state: SimulationState, scenario_name: str) -> tuple[SimulationState, list[Intervention]]:
    """Applies a clinical scenario to an independent clone of *state*.

    Supported scenarios:
    - 'hemorrhage': Acute blood loss (-35% blood volume, compensatory tachycardia)
    - 'hypertension': Severe systemic vasoconstriction (+65% SVR, mild contractility bump)
    - 'tachycardia': Supraventricular tachycardia (145 bpm)
    - 'ischemia': Left ventricular myocardial ischemia (reduced contractility to 0.55x, compensatory SVR)
    - 'free_experiment': Baseline clone without perturbations
    """
    cloned = copy_state(state)
    scen = scenario_name.lower().strip()
    interventions: list[Intervention] = []

    if scen == "hemorrhage":
        # Acute hypovolemia
        cloned, i1 = apply_intervention(cloned, "blood_volume", cloned.circulation.blood_volume_l * 0.65)
        cloned, i2 = apply_intervention(cloned, "heart_rate", min(140.0, cloned.heart_rate_bpm * 1.45))
        cloned, i3 = apply_intervention(cloned, "svr", cloned.circulation.systemic_vascular_resistance * 1.35)
        interventions.extend([i1, i2, i3])
    elif scen == "hypertension":
        # Hypertensive crisis / increased afterload
        cloned, i1 = apply_intervention(cloned, "svr", cloned.circulation.systemic_vascular_resistance * 1.65)
        cloned, i2 = apply_intervention(cloned, "contractility", min(2.0, cloned.contractility * 1.1))
        interventions.extend([i1, i2])
    elif scen == "tachycardia":
        # SVT
        cloned, i1 = apply_intervention(cloned, "heart_rate", 145.0)
        interventions.append(i1)
    elif scen == "ischemia":
        # Pump failure
        cloned, i1 = apply_intervention(cloned, "contractility", 0.55)
        cloned, i2 = apply_intervention(cloned, "svr", cloned.circulation.systemic_vascular_resistance * 1.25)
        cloned, i3 = apply_intervention(cloned, "heart_rate", max(85.0, cloned.heart_rate_bpm * 1.15))
        interventions.extend([i1, i2, i3])
    elif scen in ("free_experiment", "baseline", "nominal"):
        pass
    else:
        raise ValueError(f"Unknown scenario name: '{scenario_name}'")

    validate_state(cloned)
    return cloned, interventions


# ---------------------------------------------------------------------------
# Trajectory Downsampling & Serialization
# ---------------------------------------------------------------------------

def extract_trajectory_frame(s: SimulationState, time_offset: float = 0.0) -> Dict[str, Any]:
    """Extracts lightweight trajectory points suitable for chart rendering."""
    m = s.metrics
    c = s.circulation
    lv = s.chambers["left_ventricle"]
    return {
        "time": round(s.time_s - time_offset, 3),
        "hr": round(s.heart_rate_bpm, 1),
        "sbp": round(m.systolic_bp_mmhg, 1),
        "dbp": round(m.diastolic_bp_mmhg, 1),
        "map": round(m.map_mmhg, 1),
        "stroke_volume": round(m.stroke_volume_ml, 1),
        "cardiac_output": round(m.cardiac_output_l_min, 2),
        "edv": round(m.end_diastolic_volume_ml, 1),
        "esv": round(m.end_systolic_volume_ml, 1),
        "lv_pressure": round(lv.pressure_mmhg, 1),
        "lv_volume": round(lv.volume_ml, 1),
        "aortic_pressure": round(c.aortic_pressure_mmhg, 1),
        "blood_volume": round(c.blood_volume_l, 2),
        "contractility": round(s.contractility, 2),
        "svr": round(c.systemic_vascular_resistance * 1120.0, 1),
    }


def downsample_trajectory(states: List[SimulationState], target_fps: int = 25) -> List[Dict[str, Any]]:
    """Downsamples a raw 100 Hz simulation state list to ~target_fps frames per second."""
    if not states:
        return []
    total_steps = len(states)
    if total_steps <= target_fps:
        return [extract_trajectory_frame(s) for s in states]

    # Sample interval in steps (assuming dt = 0.01)
    step_stride = max(1, int(round(100.0 / target_fps)))
    sampled = [extract_trajectory_frame(states[i]) for i in range(0, total_steps, step_stride)]
    # Always include the exact final frame
    if (total_steps - 1) % step_stride != 0:
        sampled.append(extract_trajectory_frame(states[-1]))
    return sampled


# ---------------------------------------------------------------------------
# Trajectory Differential Comparison
# ---------------------------------------------------------------------------

@dataclass
class MetricSummary:
    initial: float
    final: float
    min_val: float
    max_val: float
    delta: float
    pct_change: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initial": round(self.initial, 2),
            "final": round(self.final, 2),
            "min": round(self.min_val, 2),
            "max": round(self.max_val, 2),
            "delta": round(self.delta, 2),
            "pct_change": round(self.pct_change, 2),
        }


def _calc_summary(values: List[float]) -> MetricSummary:
    if not values:
        return MetricSummary(0, 0, 0, 0, 0, 0)
    init_val = values[0]
    fin_val = values[-1]
    min_val = min(values)
    max_val = max(values)
    delta = fin_val - init_val
    pct = (delta / init_val * 100.0) if abs(init_val) > 1e-4 else 0.0
    return MetricSummary(init_val, fin_val, min_val, max_val, delta, pct)


def compare_trajectories(
    baseline_states: List[SimulationState],
    intervention_states: List[SimulationState],
) -> Dict[str, Any]:
    """Performs differential analysis between baseline and intervention trajectories."""
    base_final = baseline_states[-1]
    interv_final = intervention_states[-1]

    keys = [
        ("heart_rate", lambda s: s.heart_rate_bpm),
        ("systolic_bp", lambda s: s.metrics.systolic_bp_mmhg),
        ("diastolic_bp", lambda s: s.metrics.diastolic_bp_mmhg),
        ("map", lambda s: s.metrics.map_mmhg),
        ("stroke_volume", lambda s: s.metrics.stroke_volume_ml),
        ("cardiac_output", lambda s: s.metrics.cardiac_output_l_min),
        ("edv", lambda s: s.metrics.end_diastolic_volume_ml),
        ("esv", lambda s: s.metrics.end_systolic_volume_ml),
        ("blood_volume", lambda s: s.circulation.blood_volume_l),
        ("contractility", lambda s: s.contractility),
        ("svr", lambda s: s.circulation.systemic_vascular_resistance),
    ]

    metrics_comparison: Dict[str, Any] = {}
    for name, extractor in keys:
        b_series = [extractor(s) for s in baseline_states]
        i_series = [extractor(s) for s in intervention_states]
        b_sum = _calc_summary(b_series)
        i_sum = _calc_summary(i_series)

        diff_final = i_sum.final - b_sum.final
        diff_pct = (diff_final / b_sum.final * 100.0) if abs(b_sum.final) > 1e-4 else 0.0

        metrics_comparison[name] = {
            "baseline": b_sum.to_dict(),
            "intervention": i_sum.to_dict(),
            "final_difference": round(diff_final, 2),
            "final_pct_difference": round(diff_pct, 2),
        }

    # Simulation-derived hemodynamic stability score
    # Computed from the rate of change of MAP and CO over the last 20% of the intervention run
    tail_len = max(2, int(len(intervention_states) * 0.2))
    tail_states = intervention_states[-tail_len:]
    map_tail = [s.metrics.map_mmhg for s in tail_states]
    co_tail = [s.metrics.cardiac_output_l_min for s in tail_states]

    map_drift = max(map_tail) - min(map_tail)
    co_drift = max(co_tail) - min(co_tail)
    # Higher score (closer to 1.0) = more stabilized / settled hemodynamic state
    instability_penalty = min(1.0, (map_drift / 20.0) + (co_drift / 2.0))
    stability_score = round(max(0.0, 1.0 - instability_penalty), 3)

    # Shock index: HR / SBP
    base_si = base_final.heart_rate_bpm / max(1.0, base_final.metrics.systolic_bp_mmhg)
    interv_si = interv_final.heart_rate_bpm / max(1.0, interv_final.metrics.systolic_bp_mmhg)

    return {
        "metrics": metrics_comparison,
        "stability_score": stability_score,
        "shock_index": {
            "baseline": round(base_si, 2),
            "intervention": round(interv_si, 2),
            "delta": round(interv_si - base_si, 2),
        },
    }


# ---------------------------------------------------------------------------
# Master Experiment Runner
# ---------------------------------------------------------------------------

@dataclass
class ExperimentResult:
    experiment_id: str
    scenario: str
    duration_s: float
    dt_s: float
    interventions: List[Intervention]
    baseline_trajectory: List[Dict[str, Any]]
    intervention_trajectory: List[Dict[str, Any]]
    comparison: Dict[str, Any]
    initial_baseline_state: Dict[str, Any]
    final_baseline_state: Dict[str, Any]
    final_intervention_state: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "scenario": self.scenario,
            "duration_s": self.duration_s,
            "dt_s": self.dt_s,
            "interventions": [i.to_dict() for i in self.interventions],
            "baseline_trajectory": self.baseline_trajectory,
            "intervention_trajectory": self.intervention_trajectory,
            "comparison": self.comparison,
            "initial_baseline_state": self.initial_baseline_state,
            "final_baseline_state": self.final_baseline_state,
            "final_intervention_state": self.final_intervention_state,
        }


def run_experiment(
    current_state: SimulationState,
    scenario: str = "free_experiment",
    custom_interventions: Optional[List[Dict[str, Any]]] = None,
    duration_s: float = 6.0,
    dt_s: float = 0.01,
) -> ExperimentResult:
    """Executes a dual-branch in-silico experiment from the current simulation state.

    1. Safely clones current_state as baseline_state.
    2. Safely clones baseline_state as intervention_state.
    3. Applies scenario perturbations and any custom interventions to intervention_state.
    4. Simulates baseline for duration_s.
    5. Simulates intervention for duration_s.
    6. Downsamples trajectories for lightweight visual rendering.
    7. Calculates exact differential comparisons across all cardiac parameters.
    """
    exp_id = str(uuid.uuid4())

    # Step 1 & 2: Safe state cloning
    baseline_initial = copy_state(current_state)
    intervention_initial = copy_state(baseline_initial)

    # Step 3: Apply scenario perturbations
    interventions_applied: List[Intervention] = []
    if scenario and scenario != "free_experiment":
        intervention_initial, scen_interventions = apply_scenario(intervention_initial, scenario)
        interventions_applied.extend(scen_interventions)

    # Apply any explicit parameter adjustments
    if custom_interventions:
        for item in custom_interventions:
            param = item.get("parameter")
            val = item.get("value")
            if param is not None and val is not None:
                intervention_initial, custom_inv = apply_intervention(intervention_initial, param, float(val))
                interventions_applied.append(custom_inv)

    # Step 4: Simulate baseline trajectory
    baseline_states = simulate(baseline_initial, duration=duration_s, dt=dt_s)

    # Step 5: Simulate intervention trajectory
    intervention_states = simulate(intervention_initial, duration=duration_s, dt=dt_s)

    # Step 6: Downsample trajectories
    baseline_downsampled = downsample_trajectory(baseline_states, target_fps=25)
    intervention_downsampled = downsample_trajectory(intervention_states, target_fps=25)

    # Step 7: Compare trajectories
    comparison = compare_trajectories(baseline_states, intervention_states)

    return ExperimentResult(
        experiment_id=exp_id,
        scenario=scenario,
        duration_s=duration_s,
        dt_s=dt_s,
        interventions=interventions_applied,
        baseline_trajectory=baseline_downsampled,
        intervention_trajectory=intervention_downsampled,
        comparison=comparison,
        initial_baseline_state=state_to_dict(baseline_initial),
        final_baseline_state=state_to_dict(baseline_states[-1]),
        final_intervention_state=state_to_dict(intervention_states[-1]),
    )
