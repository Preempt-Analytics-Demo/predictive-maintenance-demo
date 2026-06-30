# Preempt Analytics — Predictive Maintenance Demo

Capstone project 2 of the AI Engineering bootcamp at neuefische.
Predictive maintenance with a focus on MLOps — by Nate and Ivo.

> **Developers:** looking for the full technical documentation? See [README-DEV.md](README-DEV.md).

---

## What this project does

This system predicts industrial equipment failures before they happen — using live sensor readings from a CNC machine. It demonstrates a complete MLOps pipeline: a prediction API, an automated drift monitor, and a self-triggering retraining workflow.

**You do not need any ML or Python knowledge to run it.** Everything runs inside Docker.

---

## What you need

One thing: **Docker Desktop.**

Docker packages everything this project needs — the ML model, Python, all libraries — into a self-contained box that runs identically on any machine. You do not need to install Python or configure anything; Docker handles it all.

- [Download Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)
- [Download Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)

Install it and make sure it is running (you should see the Docker whale icon in your taskbar or menu bar) before continuing.

---

## Setup — three commands

Open a terminal and run these three commands in order:

```bash
# 1. Download the project
git clone https://github.com/Preempt-Analytics-Demo/predictive-maintenance-demo.git
cd predictive-maintenance-demo

# 2. Start the prediction API and the drift monitor (runs silently in the background)
docker compose up -d

# 3. Smoke test — verify the simulation engine is talking to the prediction API
docker compose run --rm simulator --mode normal --n-readings 500
```

**What just happened:**
- Step 2 started two background services in detached mode — they keep running after you close your terminal. To confirm both are up: `docker compose ps`
- Step 3 confirmed they are connected — 500 sensor readings were routed through the API, predictions were made, and results were stored

If you saw a stream of readings ending with `Done — 500 readings stored`, the system is working correctly.

---

## You're set up — now see the ML pipeline in action

Steps 1–3 confirmed the system is running and the simulation engine is connected to the prediction API. Next: trigger the full retraining loop and watch the model detect data shift, push new training data to the cloud, and retrain itself.

---

## Trigger the full retraining loop

The system can detect when the data starts behaving differently (called *drift*) and retrain itself automatically. To see this in action, run one of the following commands depending on your OS — it generates abnormal sensor readings, checks for drift right in this terminal, then opens the drift report and GitHub Actions page in your browser automatically:

**Mac / Linux**
```bash
docker compose run --rm simulator --mode sudden-spike --n-readings 1000 && ./open_results.sh
```

**Windows (PowerShell)**
```powershell
docker compose run --rm simulator --mode sudden-spike --n-readings 1000; .\open_results.ps1
```

**What happens:**
1. 1,000 abnormal readings are generated and sent to the prediction API
2. Drift detection runs immediately and prints a report in this terminal — you will see which sensor features shifted and whether the threshold was crossed
3. The drift report opens in your browser (`reports/drift_report.html`)
4. The GitHub Actions page opens — if drift was detected, a retraining workflow appears there within ~1 minute and runs automatically

---

## Explore the prediction API

Want to query the API directly? Run these from any terminal while the system is up.

Check the API is healthy and which model version is loaded:

```bash
curl http://localhost:8000/health
```

You should see something like: `{"status": "ok", "model_loaded": true}`

Send a single prediction request:

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"Type": "M", "Air temperature [K]": 298.1, "Process temperature [K]": 308.6, "Rotational speed [rpm]": 1551, "Torque [Nm]": 42.8, "Tool wear [min]": 0}'
```

You should see something like: `{"prediction": "normal", "probability": 0.03}`

---

## Simulation modes

| Command | What it simulates |
|---|---|
| `--mode normal` | Stable conditions — ~3.4% failure rate |
| `--mode gradual-drift` | Equipment slowly ageing — failure rate rises from 3.4% to 25% |
| `--mode sudden-spike` | Abrupt failure spike — fastest way to trigger drift detection |

---

## Stop everything

```bash
docker compose down
```

---

## Architecture overview

```
You run the simulator
        │
        ▼
POST /predict  ──►  API container (port 8000)  ──►  ML model (@production)
                                                            │
                                                     prediction stored
                                                            │
                                                     simulation.db
                                                            │
                                              Monitor checks every ~1 min (demo)
                                                            │
                                              Drift detected?
                                               ├── No  → wait
                                               └── Yes → push data to cloud
                                                               │
                                                       GitHub Actions fires
                                                               │
                                                       Retrain + promote
                                                               │
                                                       New @production model
```

---

## Team

| Name | GitHub |
| ---- | ------ |
| Nate | [@nate](https://github.com/nate) |
| Ivo  | [@envelopingCODE](https://github.com/envelopingCODE) |

neuefische AI Engineering Bootcamp · Cohort 2026
