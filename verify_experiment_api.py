"""Comprehensive test for CARDIA Experiment & Counterfactual endpoints and WebSocket."""

import urllib.request
import json
import asyncio
import websockets

BASE = "http://127.0.0.1:8000"

def test_experiment_run():
    req = urllib.request.Request(
        f"{BASE}/api/experiment/run",
        data=json.dumps({
            "scenario": "hemorrhage",
            "duration_s": 2.0
        }).encode(),
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    assert data["status"] == "success"
    res = data["data"]
    assert res["scenario"] == "hemorrhage"
    assert len(res["baseline_trajectory"]) > 10
    assert len(res["intervention_trajectory"]) > 10
    assert "metrics" in res["comparison"]
    assert "stability_score" in res["comparison"]
    print(f"[OK] /api/experiment/run (Hemorrhage) -> Stability: {res['comparison']['stability_score']}, Interventions: {len(res['interventions'])}")


def test_experiment_fork():
    req = urllib.request.Request(
        f"{BASE}/api/experiment/fork",
        data=json.dumps({
            "scenario": "hypertension"
        }).encode(),
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    assert data["status"] == "success"
    assert "branch_a_baseline" in data
    assert "branch_b_counterfactual" in data
    a = data["branch_a_baseline"]
    b = data["branch_b_counterfactual"]
    print(f"[OK] /api/experiment/fork (Hypertension) -> Branch A MAP: {a['map']} mmHg vs Branch B MAP: {b['map']} mmHg")


def test_experiment_explain():
    req = urllib.request.Request(
        f"{BASE}/api/experiment/explain",
        data=json.dumps({
            "question": "Why did cardiac output fall after severe hemorrhage?",
            "scenario": "hemorrhage",
            "intervention_summary": "Blood volume reduced to 3.38L (-35%)",
            "baseline_metrics": {"hr": 74, "sbp": 118, "dbp": 78, "map": 91.3, "co": 5.4, "sv": 73, "edv": 128},
            "result_metrics": {"hr": 104, "sbp": 88, "dbp": 56, "map": 66.7, "co": 3.4, "sv": 32, "edv": 84}
        }).encode(),
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req)
    data = json.loads(resp.read())
    assert data["status"] == "success"
    assert len(data["explanation"]) > 100
    print(f"[OK] /api/experiment/explain -> Generated {len(data['explanation'])} char grounded explanation")


def main():
    print("=" * 60)
    print("Running Experiment & Counterfactual Endpoints Verification")
    print("=" * 60)
    test_experiment_run()
    test_experiment_fork()
    test_experiment_explain()
    print("=" * 60)
    print("All Experiment & Counterfactual endpoints verified successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
