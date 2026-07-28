# tests/test_promote_model.py
#
# ── Why this test exists ────────────────────────────────────────────────────
# evaluate_gates() decides whether a newly retrained model replaces the one
# serving real traffic. A bug here either blocks every future promotion or
# — worse — promotes a model that is quietly worse than what's running today.
# These cases run in milliseconds with no MLflow connection, because
# evaluate_gates() takes plain numbers, not live registry objects.

from promote_model import evaluate_gates


def test_first_ever_promotion_always_passes_the_improvement_gate():
    # prod_f1=None means no version has ever been promoted — there is
    # nothing to compare against, so improvement is trivially satisfied.
    improvement, floor = evaluate_gates(new_f1=0.70, prod_f1=None, min_f1=0.60)
    assert improvement is True
    assert floor is True


def test_better_model_passes_improvement_gate():
    improvement, _ = evaluate_gates(new_f1=0.90, prod_f1=0.85, min_f1=0.85)
    assert improvement is True


def test_worse_model_fails_improvement_gate():
    improvement, _ = evaluate_gates(new_f1=0.80, prod_f1=0.85, min_f1=0.60)
    assert improvement is False


def test_tied_f1_fails_improvement_gate():
    # Strictly greater than is required — a tie is not an improvement and
    # should not cause unnecessary model churn.
    improvement, _ = evaluate_gates(new_f1=0.85, prod_f1=0.85, min_f1=0.60)
    assert improvement is False


def test_improved_model_can_still_fail_the_floor_gate():
    # Proves the two gates are independent: beating a bad @production model
    # is not enough if the new model is still below the absolute floor.
    improvement, floor = evaluate_gates(new_f1=0.50, prod_f1=0.40, min_f1=0.60)
    assert improvement is True
    assert floor is False


def test_suspect_production_score_skips_the_improvement_gate():
    # A perfect (or near-perfect) @production f1_test almost always means
    # leaked/corrupted training data, not a genuinely unbeatable model —
    # requiring new_f1 > 1.0 would permanently block every future retrain.
    # This is exactly what happened in production: see promote_model.py's
    # "GATE 1 SUSPECT-SCORE ESCAPE HATCH" comment.
    improvement, floor = evaluate_gates(new_f1=0.75, prod_f1=1.0, min_f1=0.60)
    assert improvement is True
    assert floor is True


def test_suspect_production_score_does_not_waive_the_floor_gate():
    # The escape hatch only removes the comparison — a genuinely weak
    # candidate must still clear the absolute floor.
    improvement, floor = evaluate_gates(new_f1=0.50, prod_f1=1.0, min_f1=0.60)
    assert improvement is True
    assert floor is False
