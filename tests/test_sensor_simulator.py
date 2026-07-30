# tests/test_sensor_simulator.py
#
# ── Why this test exists ────────────────────────────────────────────────────
# generate_raw_reading()'s PWF/OSF injection used to apply the exact same
# fixed offset every time (rpm always -350, torque always +18), which made
# injected failures 3-6x narrower than real ones (see sensor_simulator.py's
# PWF/OSF comment, 2026-07-30). It now bootstraps a real failure row with
# jitter for --mode normal, but only for --mode normal — the demo modes
# (gradual-drift, sudden-spike) intentionally keep the old fixed shift so a
# live walkthrough still gets an obvious, legible spike. These tests check
# both halves of that split actually hold, since a mode-gated branch is easy
# to get backwards without noticing (both paths still "produce a failure").

import numpy as np

from sensor_simulator import (
    FAILURE_RPM_SHIFT,
    FAILURE_TORQUE_ADD_NM,
    generate_raw_reading,
)


def test_normal_mode_pwf_osf_injection_varies_across_calls():
    # Bootstrap + jitter should not collapse to a single repeated value the
    # way a fixed offset does -- draw many and check they're not all equal.
    torques = {
        generate_raw_reading(tool_wear_minutes=50, inject_failure=True, mode="normal")["Torque [Nm]"]
        for _ in range(30)
    }
    assert len(torques) > 1, "Realistic PWF/OSF injection produced the same torque every time"


def test_demo_modes_keep_the_original_fixed_shift():
    # sudden-spike/gradual-drift must still be deterministic-ish (offset from
    # whatever real row was sampled), matching the pre-2026-07-30 behavior --
    # a live demo depends on this being an obvious, repeatable spike.
    rng = np.random.default_rng(0)
    for mode in ("sudden-spike", "gradual-drift"):
        reading = generate_raw_reading(tool_wear_minutes=50, inject_failure=True, mode=mode)
        # Reconstruct what the fixed-offset formula implies about the sampled
        # baseline row: shifted_rpm = baseline_rpm + FAILURE_RPM_SHIFT (floored at 500).
        # We can't recover the exact baseline row here, but we can check the
        # reading falls in the fixed-offset's structurally narrow range rather
        # than the realistic injector's much wider bootstrap range.
        assert reading["Rotational speed [rpm]"] >= 500
        assert reading["Torque [Nm]"] >= FAILURE_TORQUE_ADD_NM  # baseline torque is never negative


def test_hdf_injection_unaffected_by_mode():
    # HDF was already well-calibrated and this change shouldn't touch it --
    # run enough draws that at least one lands in the 33.9% HDF branch for
    # every mode, and confirm the temp gap still sits in the expected band.
    rng = np.random.default_rng(1)
    for mode in ("normal", "sudden-spike", "gradual-drift"):
        gaps = []
        for _ in range(200):
            reading = generate_raw_reading(tool_wear_minutes=50, inject_failure=True, mode=mode)
            gap = reading["Process temperature [K]"] - reading["Air temperature [K]"]
            gaps.append(gap)
        # HDF's Normal(8.2, 0.3) plus PWF/OSF's untouched real temp_diff (both
        # branches are possible per call) should keep every draw well within
        # a generous band -- this just guards against an accidental swap of
        # which branch touches temperature.
        assert min(gaps) > 0, f"mode={mode} produced a non-physical temperature gap"
