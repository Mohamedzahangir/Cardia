from typing import Any

from rag.database.supabase_client import get_supabase


VALID_TRAJECTORIES = {
    "baseline",
    "intervention",
}


def create_counterfactual_run(
    session_id: str | None = None,
    experiment_id: str | None = None,
    baseline_duration: float | None = None,
) -> dict[str, Any]:
    """
    Create a CARDIA counterfactual run record.

    This stores metadata about the counterfactual execution.
    The actual trajectory results are stored separately in
    counterfactual_results.
    """

    row: dict[str, Any] = {}

    if session_id:
        row["session_id"] = session_id

    if experiment_id:
        row["experiment_id"] = experiment_id

    if baseline_duration is not None:
        row["baseline_duration"] = baseline_duration

    response = (
        get_supabase()
        .table("counterfactual_runs")
        .insert(row)
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Supabase did not return the created "
            "counterfactual run."
        )

    return response.data[0]


def save_counterfactual_result(
    counterfactual_id: str,
    trajectory: str,
    final_state: dict[str, Any] | None = None,
    metrics: dict[str, Any] | None = None,
    stability_score: float | None = None,
) -> dict[str, Any]:
    """
    Save one trajectory produced by a CARDIA counterfactual run.

    Valid trajectories are:
    - baseline
    - intervention

    The repository does not modify the simulation.
    It only persists the result supplied by the simulation
    or counterfactual engine.
    """

    if trajectory not in VALID_TRAJECTORIES:
        raise ValueError(
            f"Invalid trajectory '{trajectory}'. "
            f"Expected one of: "
            f"{sorted(VALID_TRAJECTORIES)}"
        )

    row: dict[str, Any] = {
        "counterfactual_id": counterfactual_id,
        "trajectory": trajectory,
        "final_state": final_state,
        "metrics": metrics,
        "stability_score": stability_score,
    }

    response = (
        get_supabase()
        .table("counterfactual_results")
        .insert(row)
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            "Supabase did not return the saved "
            "counterfactual result."
        )

    return response.data[0]


def get_counterfactual_run(
    counterfactual_id: str,
) -> dict[str, Any]:
    """
    Retrieve a counterfactual run by ID.
    """

    response = (
        get_supabase()
        .table("counterfactual_runs")
        .select("*")
        .eq("id", counterfactual_id)
        .single()
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            f"Counterfactual run "
            f"'{counterfactual_id}' was not found."
        )

    return response.data


def get_counterfactual_results(
    counterfactual_id: str,
) -> list[dict[str, Any]]:
    """
    Retrieve all trajectories belonging to a
    counterfactual run.

    Results are returned in deterministic order:
    baseline first, intervention second.
    """

    response = (
        get_supabase()
        .table("counterfactual_results")
        .select("*")
        .eq(
            "counterfactual_id",
            counterfactual_id,
        )
        .order("trajectory")
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            f"No counterfactual results were found for "
            f"run '{counterfactual_id}'."
        )

    return list(response.data)


def get_counterfactual_result(
    counterfactual_id: str,
    trajectory: str,
) -> dict[str, Any]:
    """
    Retrieve one specific trajectory belonging to
    a counterfactual run.
    """

    if trajectory not in VALID_TRAJECTORIES:
        raise ValueError(
            f"Invalid trajectory '{trajectory}'. "
            f"Expected one of: "
            f"{sorted(VALID_TRAJECTORIES)}"
        )

    response = (
        get_supabase()
        .table("counterfactual_results")
        .select("*")
        .eq(
            "counterfactual_id",
            counterfactual_id,
        )
        .eq(
            "trajectory",
            trajectory,
        )
        .limit(1)
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            f"No '{trajectory}' counterfactual result "
            f"was found for run '{counterfactual_id}'."
        )

    return response.data[0]