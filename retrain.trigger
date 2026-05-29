# retrain.trigger
#
# This file is the retrain signal. It is updated by export_simulation_to_csv.py
# when drift is detected. Committing a change here triggers the GitHub Actions
# retrain workflow (retrain.yml watches this path, not data/ai4i2020.csv.dvc).
#
# CSV pushes that contain no drift update only ai4i2020.csv.dvc — this file
# stays unchanged, so no retrain fires. That separates data accumulation
# from the retraining decision.
#
# Do not edit manually.
initial
