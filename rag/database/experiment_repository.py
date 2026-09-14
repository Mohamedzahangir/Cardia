from typing import Any

from rag.database.supabase_client import get_supabase


def create_experiment(
    name: str,
    description: str | None = None,
    experiment_type: str | None = None,
    session_id: str | None = None,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    """
    Create a CARDIA experiment record.

    An experiment represents a persistent analysis or simulation
    experiment associated with an optional CARDIA session/scenario.
    """

    row: dict[str, Any] = {
        "name": name,
        "description": description,
        "experiment_type": experiment_type,
    }

    if session_id:
        row["session_id"] = session_id

    if scenario_id:
        row["scenario_id"] = scenario_id

    response = (
        get_supabase()
        .table("experiments")
        .insert(row)
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Supabase did not return the created experiment."
        )

    return response.data[0]


def get_experiment(
    experiment_id: str,
) -> dict[str, Any]:
    """
    Retrieve a CARDIA experiment by ID.
    """

    response = (
        get_supabase()
        .table("experiments")
        .select("*")
        .eq("id", experiment_id)
        .single()
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            f"Experiment '{experiment_id}' was not found."
        )

    return response.data


def get_session_experiments(
    session_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Retrieve experiments belonging to a CARDIA simulation session.
    """

    if limit < 1:
        raise ValueError(
            "Experiment history limit must be at least 1."
        )

    response = (
        get_supabase()
        .table("experiments")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )

    if not response.data:
        return []

    return list(response.data)


def save_experiment_parameter(
    experiment_id: str,
    parameter_name: str,
    initial_value: float | None = None,
    final_value: float | None = None,
    unit: str | None = None,
) -> dict[str, Any]:
    """
    Save one parameter used by a CARDIA experiment.
    """

    row: dict[str, Any] = {
        "experiment_id": experiment_id,
        "parameter_name": parameter_name,
        "initial_value": initial_value,
        "final_value": final_value,
        "unit": unit,
    }

    response = (
        get_supabase()
        .table("experiment_parameters")
        .insert(row)
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Supabase did not return the saved experiment parameter."
        )

    return response.data[0]


def get_experiment_parameters(
    experiment_id: str,
) -> list[dict[str, Any]]:
    """
    Retrieve all parameters belonging to an experiment.
    """

    response = (
        get_supabase()
        .table("experiment_parameters")
        .select("*")
        .eq("experiment_id", experiment_id)
        .order("parameter_name")
        .execute()
    )

    if not response.data:
        return []

    return list(response.data)


def save_experiment_result(
    experiment_id: str,
    baseline_state: dict[str, Any] | None = None,
    peak_state: dict[str, Any] | None = None,
    final_state: dict[str, Any] | None = None,
    change_summary: dict[str, Any] | None = None,
    stability_score: float | None = None,
) -> dict[str, Any]:
    """
    Save the result produced by a CARDIA experiment.

    This repository only persists the result supplied by the
    simulation/analysis layer. It never modifies the simulation.
    """

    row: dict[str, Any] = {
        "experiment_id": experiment_id,
        "baseline_state": baseline_state,
        "peak_state": peak_state,
        "final_state": final_state,
        "change_summary": change_summary,
        "stability_score": stability_score,
    }

    response = (
        get_supabase()
        .table("experiment_results")
        .insert(row)
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Supabase did not return the saved experiment result."
        )

    return response.data[0]


def get_experiment_results(
    experiment_id: str,
) -> list[dict[str, Any]]:
    """
    Retrieve all results belonging to an experiment.
    """

    response = (
        get_supabase()
        .table("experiment_results")
        .select("*")
        .eq("experiment_id", experiment_id)
        .order("created_at")
        .execute()
    )

    if not response.data:
        return []

    return list(response.data)


def get_latest_experiment_result(
    experiment_id: str,
) -> dict[str, Any] | None:
    """
    Retrieve the most recent result belonging to an experiment.
    """

    response = (
        get_supabase()
        .table("experiment_results")
        .select("*")
        .eq("experiment_id", experiment_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]