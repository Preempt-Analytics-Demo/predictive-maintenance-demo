# Preempt Analytics — Predictive Maintenance Demo

Capstone project 2 of the AI Engineering bootcamp at neuefische.
Predictive maintenance with a focus on <a id="ref-mlops"></a>[MLOps](#glossary-mlops) — by Nate and Ivo.

> **Developers:** looking for the full technical documentation? See [README-DEV.md](README-DEV.md).

> **New to some of the terms below?** Linked words jump to a plain-language [Glossary](#glossary) at the bottom of this page.

---

## What this project does

This system predicts industrial equipment failures before they happen — using live sensor readings from a <a id="ref-cnc-machine"></a>[CNC machine](#glossary-cnc-machine). It demonstrates a complete MLOps pipeline: a <a id="ref-api"></a>[prediction API](#glossary-api), an automated drift monitor, and a self-triggering <a id="ref-retraining"></a>[retraining](#glossary-retraining) workflow.

**You do not need any ML or Python knowledge to run it.** Everything runs inside <a id="ref-docker"></a>[Docker](#glossary-docker).

---

## What you need

One thing: **Docker Desktop.**

Docker packages everything this project needs — the ML model, Python, all libraries — into a self-contained box that runs identically on any machine. You do not need to install Python or configure anything; Docker handles it all.

- [Download Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)
- [Download Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)

Install it and make sure it is running (you should see the Docker whale icon in your taskbar or menu bar) before continuing.

---

## Setup — three commands

Open a your OS specific <a id="ref-cli"></a>[command line interface](#glossary-cli) and run these three commands in order:

> <b>On Windows:</b> Powershell / Terminal / CMD

> <b>On Mac:</b>
> Terminal

```bash
# 1. Download the project
git clone https://github.com/Preempt-Analytics-Demo/predictive-maintenance-demo.git
cd predictive-maintenance-demo

# 2. Start the prediction API and the drift monitor (runs silently in the background)
docker compose up -d

# 3. Smoke test — verify the simulation engine is talking to the prediction API
docker compose run --rm simulator --mode normal --n-readings 500 --pause
```

**What just happened:**

- Step 2 started two background services in detached mode — they keep running after you close your terminal. To confirm both are up: `docker compose ps`
- Step 3 confirmed they are connected — 500 sensor readings were routed through the API, predictions were made, and results were stored

If you saw a stream of readings ending with `Done — 500 readings stored`, the <a id="ref-drift-detection"></a>[drift detection](#glossary-drift-detection) running and ending with `PASS — distribution looks stable. No retraining triggered.`, the system is working correctly.

---

## You're set up — now see the <a id="ref-ml-pipeline"></a>[ML pipeline](#glossary-ml-pipeline) in action

Steps 1–3 confirmed the system is running and the <a id="ref-simulation-engine"></a>[simulation engine](#glossary-simulation-engine) is connected to the prediction API. Next, trigger the fully automated retraining loop: watch the model detect data shift, push new training data to the cloud, and retrain itself.

![alt text](<images/Retraining Loop.png>)

---

## Trigger the full retraining loop

The system can detect when the data starts behaving differently (called <a id="ref-drift"></a>[_drift_](#glossary-drift)) and retrain itself automatically. To see this in action, run one of the following commands depending on your OS — it intentionally generates abnormal sensor readings (e.g. temperature spikes, high toolwear, etc.), checks for drift right in this terminal, then opens the drift report and GitHub Actions page in your browser automatically:

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
3. The <a id="ref-drift-report"></a>[drift report](#glossary-drift-report) opens in your browser (`reports/drift_report.html`)
4. The <a id="ref-github-actions"></a>[GitHub Actions](#glossary-github-actions) page opens — if drift was detected, a retraining workflow appears there within ~1 minute and runs automatically

---

## Explore the prediction API

Want to query the API directly? Run these from any terminal while the system is up.

Check the API is healthy and which model version is loaded:

```bash
curl http://localhost:8000/health
```

You should see something like: `{"status": "ok", "model_loaded": true}`

Send a single <a id="ref-prediction-request"></a>[prediction request](#glossary-prediction-request):

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"Type": "M", "Air temperature [K]": 298.1, "Process temperature [K]": 308.6, "Rotational speed [rpm]": 1551, "Torque [Nm]": 42.8, "Tool wear [min]": 0}'
```

You should see something like: `{"prediction": "normal", "probability": 0.03}`

---

## Simulation modes

| Command                | What it simulates                                             |
| ---------------------- | ------------------------------------------------------------- |
| `--mode normal`        | Stable conditions — ~3.4% failure rate                        |
| `--mode gradual-drift` | Equipment slowly ageing — failure rate rises from 3.4% to 25% |
| `--mode sudden-spike`  | Abrupt failure spike — fastest way to trigger drift detection |

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

| Name | <a id="ref-github"></a>[GitHub](#glossary-github)   |
| ---- | ---------------------------------------------------- |
| Nate | [@envelopingCODE](https://github.com/envelopingCODE) |
| Ivo  | [@undorigo](https://github.com/undorigo)             |

neuefische AI Engineering Bootcamp · Cohort 2026

---

## Glossary

Plain-language explanations of the technical terms used above, for readers without an ML or software background. Click a linked term in the text to jump here; click **Go back** at the end of an explanation below to jump back to where you were reading.

| Term | Explanation |
| ---- | ----------- |
| <a id="glossary-api"></a>**API** | Application Programming Interface — the address (`http://localhost:8000`) this project's prediction service listens on. Other programs, including the simulation engine, send it data and get predictions back. \| [Go back](#ref-api) |
| <a id="glossary-cnc-machine"></a>**CNC machine** | Computer Numerical Control machine — factory equipment that shapes or cuts material automatically from programmed instructions. This project simulates sensor readings (temperature, speed, torque, etc.) from a CNC machine to predict when it might fail. \| [Go back](#ref-cnc-machine) |
| <a id="glossary-cli"></a>**Command Line Interface (CLI)** | A text-based way of interacting with your computer by typing commands instead of clicking buttons — Terminal on Mac, PowerShell or CMD on Windows. All the commands in this README are typed into one of these. \| [Go back](#ref-cli) |
| <a id="glossary-docker"></a>**Docker** | Software that packages an application together with everything it needs to run — code, libraries, settings — into a self-contained unit called a container, so it behaves identically on any machine. This project uses Docker so you don't need to install Python or any ML libraries yourself. \| [Go back](#ref-docker) |
| <a id="glossary-drift"></a>**Drift** | A change in the statistical patterns of incoming data over time, compared to the data the ML model was trained on. If sensor readings start looking meaningfully different from what the model learned on, its predictions can no longer be trusted. \| [Go back](#ref-drift) |
| <a id="glossary-drift-detection"></a>**Drift detection** | The automated check that compares recent sensor data to the model's original training data and flags whether drift (see above) has occurred. \| [Go back](#ref-drift-detection) |
| <a id="glossary-drift-report"></a>**Drift report** | An HTML report generated by the drift detection step, showing which sensor features have shifted and by how much. Saved to `reports/drift_report.html` and opened automatically after a full retraining-loop run. \| [Go back](#ref-drift-report) |
| <a id="glossary-github"></a>**GitHub** | The website that hosts this project's code and version history, and — via GitHub Actions, below — runs the automated retraining workflow. \| [Go back](#ref-github) |
| <a id="glossary-github-actions"></a>**GitHub Actions** | GitHub's built-in automation feature. This project uses it to run the retraining workflow automatically whenever drift is detected and new data is pushed. \| [Go back](#ref-github-actions) |
| <a id="glossary-mlops"></a>**ML Ops (MLOps)** | Machine Learning Operations — the practice of automating and monitoring a machine learning model's full lifecycle in production (training, deployment, monitoring, retraining), rather than treating it as a one-off experiment. \| [Go back](#ref-mlops) |
| <a id="glossary-ml-pipeline"></a>**ML pipeline** | The end-to-end sequence of automated steps that takes raw data all the way to a working, deployed model — here: generating sensor data, serving predictions, detecting drift, and retraining. \| [Go back](#ref-ml-pipeline) |
| <a id="glossary-prediction-request"></a>**Prediction request** | A single message sent to the API containing one machine's sensor readings, asking "is this machine likely to fail?" The API responds with a prediction and a probability. \| [Go back](#ref-prediction-request) |
| <a id="glossary-retraining"></a>**Retraining** | Training a new version of the model on updated data, so its predictions stay accurate as real-world conditions change. In this project, retraining fires automatically once drift is detected. \| [Go back](#ref-retraining) |
| <a id="glossary-simulation-engine"></a>**Simulation engine** | The component (`src/sensor_simulator.py`) that generates realistic, fake sensor readings — standing in for a real CNC machine — and sends them to the prediction API. \| [Go back](#ref-simulation-engine) |
