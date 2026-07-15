"""
scripts/try_prediction.py
==========================
A friendly, one-command way to see the prediction API in action.

WHY THIS SCRIPT EXISTS
-----------------------
The README's raw curl / PowerShell / Command Prompt examples are correct and
useful for developers, but they ask a non-technical reader to first figure out
which shell they're in, then read a wall of JSON to find the one number that
matters. This script asks nothing and explains the result in plain language —
same request, same API, no shell-specific syntax to get right.

It's meant to run INSIDE the already-running api container (see README), so
it needs no local Python install and no networking setup: `localhost:8000`
from inside that container reaches the API directly, the same way it would
from any terminal on the host once the port is published.

  docker compose exec api python scripts/try_prediction.py
"""

import sys

import httpx


# ── Sample reading ────────────────────────────────────────────────────────────
# One representative "normal" reading — the same values used in the README's
# curl examples, so a reader comparing the two sees the same request either way.
SAMPLE_READING = {
    "machine_type": "M",
    "air_temperature_kelvin": 298.1,
    "process_temperature_kelvin": 308.6,
    "rotational_speed_rpm": 1551,
    "torque_nm": 42.8,
    "tool_wear_minutes": 0,
}

API_URL = "http://localhost:8000"


def main() -> None:
    # ── Primer ───────────────────────────────────────────────────────────────
    # Front-loads what's about to happen and what the six numbers mean before
    # any output appears — the request itself is the least interesting part,
    # so it's named here rather than left for the reader to reverse-engineer.
    print()
    print("  Sending one sample sensor reading to your prediction API...")
    print()
    print("    Machine type        : M (medium)")
    print("    Air temperature     : 298.1 K")
    print("    Process temperature : 308.6 K")
    print("    Rotational speed    : 1551 rpm")
    print("    Torque              : 42.8 Nm")
    print("    Tool wear           : 0 min")
    print()

    try:
        response = httpx.post(f"{API_URL}/predict", json=SAMPLE_READING, timeout=10.0)
        response.raise_for_status()
    except httpx.ConnectError:
        # Most likely cause: this script was run outside the api container, or
        # the system isn't up yet — both produce a connection refusal, not a
        # DNS-style failure, since "localhost" always resolves.
        print(f"ERROR: Cannot connect to the API at {API_URL}.")
        print("  Run this inside the api container, with the system up:")
        print("    docker compose up -d")
        print("    docker compose exec api python scripts/try_prediction.py")
        sys.exit(1)

    data = response.json()

    # ── Friendly verdict ─────────────────────────────────────────────────────
    # machine_failure/failure_probability are the API's own field names, not
    # words a first-time reader would recognise as "good news" or "bad news" —
    # translating to a plain sentence is the entire point of this script.
    failure = data["machine_failure"]
    probability = data["failure_probability"]
    verdict = "FAILURE PREDICTED ⚠" if failure else "Normal — no failure predicted"

    print(f"  Prediction: {verdict}")
    print(f"    Estimated failure risk : {probability:.2%}")
    print(f"    Model                  : {data['model_name']} (v{data['model_version']})")
    print()
    print("  This is the same /predict endpoint the simulator calls for every")
    print("  reading, and the same one shown with raw curl commands further")
    print("  down the README — this just skips the JSON.")
    print()
    print(f"  (Raw response: {data})")


if __name__ == "__main__":
    main()
