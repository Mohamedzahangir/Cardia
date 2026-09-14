"""
CARDIA Counterfactual State Adapter.

Converts the public CARDIA/RAG simulation-state dictionary into a valid
SimulationState without modifying the simulation package.

The simulation package remains the single source of truth for the
internal state structure.
"""

from __future__ import annotations

from typing import Any

from simulation.state import (
    SimulationState,
    create_initial_state,
    copy_state,
    validate_state,
)


SUPPORTED_INPUT_FIELDS = {
    "time": "time_s",
    "heart_rate": "heart_rate_bpm",
    "contractility": "contractility",
    "svr": "circulation.systemic_vascular_resistance",
}


def rag_dict_to_simulation_state(
    state_data: dict[str, Any] | None,
) -> SimulationState:
    """
    Convert a RAG-compatible state dictionary into a SimulationState.

    The conversion starts from CARDIA's official initial-state factory
    and applies only supported top-level intervention/state fields.

    This function does not modify the supplied dictionary.
    """

    state = create_initial_state()

    if not state_data:
        return state

    state = copy_state(state)

    if "time" in state_data:
        state.time_s = float(state_data["time"])

    if "heart_rate" in state_data:
        state.heart_rate_bpm = float(
            state_data["heart_rate"]
        )

    if "contractility" in state_data:
        state.contractility = float(
            state_data["contractility"]
        )

    if "svr" in state_data:
        state.circulation.systemic_vascular_resistance = float(
            state_data["svr"]
        )

    validate_state(state)

    return state