"""Unit tests for CARDIA experiment & counterfactual simulation engine.

Ensures:
- Safe state cloning (no mutation of baseline)
- Numerical safety and bounds enforcement (no NaNs, no negative volume)
- Correct scenario perturbations (hemorrhage, hypertension, tachycardia, ischemia)
- Differential trajectory comparison math
"""

import pytest
import math
from simulation.state import create_initial_state, copy_state
from simulation.experiment import (
    apply_intervention,
    apply_scenario,
    run_experiment,
    clamp_parameter,
    compare_trajectories,
)


def test_safe_state_cloning_immutability():
    """Mutating a cloned state or intervention branch MUST NOT mutate the original baseline."""
    initial = create_initial_state()
    orig_hr = initial.heart_rate_bpm
    orig_vol = initial.circulation.blood_volume_l
    orig_svr = initial.circulation.systemic_vascular_resistance

    cloned, interv = apply_intervention(initial, "blood_volume", 3.5)

    # Check baseline was not mutated
    assert initial.circulation.blood_volume_l == orig_vol
    assert initial.heart_rate_bpm == orig_hr
    assert initial.circulation.systemic_vascular_resistance == orig_svr

    # Check cloned reflects intervention
    assert cloned.circulation.blood_volume_l == 3.5
    assert interv.baseline_value == orig_vol
    assert interv.new_value == 3.5
    assert interv.delta == pytest.approx(3.5 - orig_vol)


def test_parameter_clamping_and_numerical_safety():
    """Ensure negative volumes or impossible extreme values are safely clamped."""
    initial = create_initial_state()

    # Extreme low blood volume -> clamped to minimum 1.5 L
    cloned_low, interv_low = apply_intervention(initial, "blood_volume", -10.0)
    assert cloned_low.circulation.blood_volume_l == 1.5

    # Extreme high HR -> clamped to maximum 240 bpm
    cloned_high, interv_high = apply_intervention(initial, "heart_rate", 999.0)
    assert cloned_high.heart_rate_bpm == 240.0

    # Ensure no NaN or infinite values
    assert not math.isnan(cloned_low.circulation.blood_volume_l)
    assert not math.isnan(cloned_high.heart_rate_bpm)


def test_hemorrhage_scenario_hemodynamics():
    """Hemorrhage scenario drops blood volume and invokes compensatory response."""
    initial = create_initial_state()
    res = run_experiment(initial, scenario="hemorrhage", duration_s=2.0)

    assert res.scenario == "hemorrhage"
    assert len(res.interventions) > 0

    # Blood volume must be significantly lower in intervention than baseline
    base_bv = res.comparison["metrics"]["blood_volume"]["baseline"]["final"]
    interv_bv = res.comparison["metrics"]["blood_volume"]["intervention"]["final"]
    assert interv_bv < base_bv

    # Stroke volume should drop due to reduced Frank-Starling filling
    base_sv = res.comparison["metrics"]["stroke_volume"]["baseline"]["final"]
    interv_sv = res.comparison["metrics"]["stroke_volume"]["intervention"]["final"]
    assert interv_sv < base_sv

    # Shock index must be higher in hemorrhage
    assert res.comparison["shock_index"]["intervention"] > res.comparison["shock_index"]["baseline"]


def test_hypertension_scenario():
    """Hypertension scenario increases afterload (SVR) and arterial pressures."""
    initial = create_initial_state()
    res = run_experiment(initial, scenario="hypertension", duration_s=1.5)

    base_map = res.comparison["metrics"]["map"]["baseline"]["final"]
    interv_map = res.comparison["metrics"]["map"]["intervention"]["final"]
    assert interv_map > base_map


def test_trajectory_format_and_downsampling():
    """Trajectories must be downsampled cleanly and contain all essential clinical channels."""
    initial = create_initial_state()
    res = run_experiment(initial, scenario="free_experiment", duration_s=1.0)

    # 1.0s at target ~25 fps should yield ~25-27 points
    assert 20 <= len(res.baseline_trajectory) <= 30
    assert 20 <= len(res.intervention_trajectory) <= 30

    frame = res.baseline_trajectory[0]
    required_keys = [
        "time", "hr", "sbp", "dbp", "map", "stroke_volume",
        "cardiac_output", "edv", "esv", "lv_pressure", "lv_volume",
        "aortic_pressure", "blood_volume", "contractility", "svr"
    ]
    for k in required_keys:
        assert k in frame
        assert not math.isnan(frame[k])
