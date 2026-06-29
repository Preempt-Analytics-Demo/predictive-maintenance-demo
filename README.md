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

# 2. Start the prediction API and the drift monitor
docker compose up -d

# 3. Smoke test — verify the simulation engine is talking to the prediction API
docker compose run --rm simulator --mode normal --n-readings 500
```

**What just happened:**
- Step 2 started two background services: the prediction API (port 8000) and the drift monitor
- Step 3 confirmed they are connected — 500 sensor readings were routed through the API, predictions were made, and results were stored

If you saw a stream of readings ending with `Done — 500 readings stored`, the system is working correctly.

---

## You're set up — now see the ML pipeline in action

Steps 1–3 confirmed the system is running and the simulation engine is connected to the prediction API. Now let's put it through its paces: trigger the full retraining loop and watch the model update itself.

---

## Trigger the full retraining loop

The system can detect when the data starts behaving differently (called *drift*) and retrain itself automatically. To see this in action, generate readings that deliberately look abnormal:

```bash
docker compose run --rm simulator --mode sudden-spike --n-readings 1000
```

Then watch the monitor logs — it checks for drift every 5 minutes:

```bash
docker compose logs -f monitor
```

When drift is detected, the monitor pushes new training data to the cloud and fires a GitHub Actions workflow that retrains the model. You can watch the workflow run live in the **Actions** tab of this GitHub repository.

A drift report is saved to `reports/drift_report.html` — open it in your browser to see which sensor readings shifted.

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
                                              Monitor checks every 5 min
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
| Nate | @x     |
| Ivo  | @y     |

neuefische AI Engineering Bootcamp · Cohort 2026
