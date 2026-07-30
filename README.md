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

Open your OS's <a id="ref-cli"></a>[command line interface](#glossary-cli) and run these three commands in order:

> <b>On Windows:</b> PowerShell, Terminal, or CMD
>
> <b>On Mac:</b> Terminal

**1. Download the project**

```bash
git clone https://github.com/Preempt-Analytics-Demo/predictive-maintenance-demo.git
cd predictive-maintenance-demo
```

**2. Start the prediction API and the drift monitor** (runs silently in the background)

```bash
docker compose up -d
```

**3. Smoke test** — verify the simulation engine is talking to the prediction API

```bash
docker compose run --rm simulator --mode normal --n-readings 500 --pause
```

**What just happened:**

- Step 2 started two background services in detached mode — they keep running after you close your terminal. To confirm both are up: `docker compose ps`
- Step 3 confirmed they are connected — 500 sensor readings were routed through the API, predictions were made, and results were stored

If you saw a stream of readings ending with `Done — 500 readings stored`, followed by <a id="ref-drift-detection"></a>[drift detection](#glossary-drift-detection) output ending with `PASS — distribution looks stable. No retraining triggered.`, the system is working correctly.

---

## Prefer a menu to typing commands?

Everything below this point — simulating readings, opening the drift report, watching GitHub Actions, restarting services — is also available as a single-keypress control panel. No typing, no memorizing flags:

**Mac / Linux**

```bash
./preempt.sh
```

**Windows**

```powershell
.\preempt.ps1
```

Press a number, watch it run, press `Q` to quit. The sections below walk through the same actions manually — useful if you want to see the exact commands or run a step on its own.

---

## You're set up — now see the <a id="ref-ml-pipeline"></a>[ML pipeline](#glossary-ml-pipeline) in action

Steps 1–3 confirmed the system is running and the <a id="ref-simulation-engine"></a>[simulation engine](#glossary-simulation-engine) is connected to the prediction API. Next, trigger the fully automated retraining loop: watch the model detect data shift, push new training data to the cloud, and retrain itself.

![Diagram of the automated retraining loop](<images/Retraining Loop.png>)

---

## Trigger the full retraining loop

The system can detect when the data starts behaving differently (called <a id="ref-drift"></a>[_drift_](#glossary-drift)) and retrain itself automatically. To see this in action, run one of the following commands depending on your OS — it intentionally generates abnormal sensor readings (e.g. temperature spikes, high toolwear, etc.), checks for drift right in this terminal, then opens the drift report and the <a id="ref-github-actions"></a>[GitHub Actions](#glossary-github-actions) run in your browser automatically:

**Mac / Linux**

```bash
docker compose run --rm simulator --mode sudden-spike --n-readings 1000 --demo && ./open_results.sh
```

**Windows (PowerShell)**

```powershell
docker compose run --rm simulator --mode sudden-spike --n-readings 1000 --demo; .\open_results.ps1
```

`--demo` prints a short walkthrough of what's about to happen (and pauses for Enter) before the run starts — drop it if you just want the readings generated without the explanation.

**What happens:**

1. 1,000 abnormal readings are generated and sent to the prediction API
2. Drift detection runs immediately and prints a report in this terminal — you will see which sensor features shifted and whether the threshold was crossed
3. The <a id="ref-drift-report"></a>[drift report](#glossary-drift-report) opens in your browser (`reports/drift_report.html`)
4. If drift was detected, the retraining run opens directly in your browser within a few minutes (see [While GitHub Actions is running](#while-github-actions-is-running) below for what you're looking at)

---

## While GitHub Actions is running

You don't need to do anything — it's safe to just let it run.

**Where to actually watch it:** `open_results.sh` / `open_results.ps1` open the specific run directly when they can. If instead you land on a _list_ of runs — because you navigated to GitHub Actions yourself, or the script fell back to the list — the list alone won't show you anything happening. Click into the top row (the most recent run) to open it; that's where each step runs live, one by one.

**What it's doing:** Training a new version of the prediction model on the full sensor dataset, now including the readings you just generated.

**How long it takes:** A few minutes. A list of steps runs top to bottom, each one turning green as it finishes.

**What "all green" means:** The new model was trained and tested successfully.

**What a red step means:** Something failed — the current model just keeps running exactly as before. Nothing breaks.

**Does the new model go live automatically?** Only if it's measurably more accurate than the one currently in use. The workflow checks this before switching anything, so a worse model can never take over by accident.

**Is there a limit to how often this can run?** Yes — up to 10 retrainings per hour, shared by everyone using this demo at once (not 10 per person). It's there to stop the shared pipeline from being flooded. If the limit's been reached, your sensor data still uploads normally; only the retraining itself waits until an earlier run in that hour ages out. Your terminal tells you when you're getting close and when you've hit it.

---

## What decides whether the new model actually goes live?

You already read the short answer above: only if it's measurably more accurate. This section explains what "measurably more accurate" actually means, and where that measurement is kept.

**The short version:** every time a new model finishes training, a tool called <a id="ref-mlflow"></a>[MLflow](#glossary-mlflow) writes down exactly how well it performed — automatically, with nothing for you to do. That written record is what gets compared against the model currently running, before anything is ever allowed to switch.

**Why not just eyeball it?** Because eyeballing it means trusting a guess, and a system that predicts equipment failure isn't somewhere you want a guess. MLflow turns "is the new one actually better?" into a real, repeatable measurement — calculated the same way every single time — instead of a judgment call someone has to remember to make.

**What gets measured:** how accurately each version predicts real failures on data it has never seen before. A new version only replaces the current one if **both** of these are true:

- It scores higher than the model currently live.
- It clears a minimum accuracy bar on its own, regardless of the comparison.

A new version that's merely "not worse" is not promoted. Neither is one that beats the old model but still falls short of the safety floor.

**Can I see this for myself?** The full comparison lives on <a id="ref-dagshub"></a>[DagsHub](#glossary-dagshub), the platform this project uses to store every training run behind the scenes. Browsing it yourself needs a DagsHub account with access to this project, so it isn't something every demo visitor can open — but you don't need to see it for any of this to work. The comparison runs automatically, every time, whether or not anyone ever looks at it.

---

## Explore the prediction API

The easiest way to see it working — one command, identical on every platform:

```bash
docker compose exec api python scripts/try_prediction.py
```

This sends one sample sensor reading to the API and explains the result in plain language — no JSON, no curl, no shell-specific syntax to get right.

<details>
<summary><b>For developers — query the API directly with curl</b></summary>

Want to query the API directly? Run these from any terminal while the system is up.

Check the API is healthy and which model version is loaded:

```bash
curl http://localhost:8000/health
```

"You should see something like: `{\"status\": \"ok\", \"model_loaded\": true}`

Send a single <a id="ref-prediction-request"></a>[prediction request](#glossary-prediction-request). The field names below (`machine_type`, `air_temperature_kelvin`, etc.) are what the API actually expects — not the raw sensor CSV's column names (`Type`, `Air temperature [K]`, ...); those get translated internally.

**Mac / Linux**

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"machine_type": "M", "air_temperature_kelvin": 298.1, "process_temperature_kelvin": 308.6, "rotational_speed_rpm": 1551, "torque_nm": 42.8, "tool_wear_minutes": 0}'
```

**Windows (PowerShell)**

The `\` line-continuation above is bash-only — pasted into PowerShell it runs each line as a separate command. Use `Invoke-RestMethod` instead, which sidesteps quoting entirely:

```powershell
$body = @{
    machine_type = "M"
    air_temperature_kelvin = 298.1
    process_temperature_kelvin = 308.6
    rotational_speed_rpm = 1551
    torque_nm = 42.8
    tool_wear_minutes = 0
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:8000/predict -Method Post -ContentType "application/json" -Body $body
```

**Windows (Command Prompt)**

Command Prompt doesn't support `\` continuation or single-quoted strings either — paste this as one line:

```
curl.exe -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d "{\"machine_type\": \"M\", \"air_temperature_kelvin\": 298.1, \"process_temperature_kelvin\": 308.6, \"rotational_speed_rpm\": 1551, \"torque_nm\": 42.8, \"tool_wear_minutes\": 0}"
```

You should see something like: `{"machine_failure": 0, "failure_probability": 0.0001, "failure_type": null, "model_name": "predictive-maintenance-binary", "model_version": "2"}`

</details>

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
                                              Monitor checks every ~30s (demo)
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

| Name | <a id="ref-github"></a>[GitHub](#glossary-github)    |
| ---- | ---------------------------------------------------- |
| Nate | [@envelopingCODE](https://github.com/envelopingCODE) |
| Ivo  | [@undorigo](https://github.com/undorigo)             |

neuefische AI Engineering Bootcamp · Cohort 2026

---

## Glossary

Plain-language explanations of the technical terms used above, for readers without an ML or software background. Click a linked term in the text to jump here; click **Go back** at the end of an explanation below to jump back to where you were reading.

| Term                                                           | Explanation                                                                                                                                                                                                                                                                                                                                      |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| <a id="glossary-api"></a>**API**                               | Application Programming Interface — the address (`http://localhost:8000`) this project's prediction service listens on. Other programs, including the simulation engine, send it data and get predictions back.&nbsp;&nbsp;\|&nbsp;&nbsp;[Go back](#ref-api)                                                                                     |
| <a id="glossary-cnc-machine"></a>**CNC machine**               | Computer Numerical Control machine — factory equipment that shapes or cuts material automatically from programmed instructions. This project simulates sensor readings (temperature, speed, torque, etc.) from a CNC machine to predict when it might fail.&nbsp;&nbsp;\|&nbsp;&nbsp;[Go back](#ref-cnc-machine)                                 |
| <a id="glossary-cli"></a>**Command Line Interface (CLI)**      | A text-based way of interacting with your computer by typing commands instead of clicking buttons — Terminal on Mac, PowerShell or CMD on Windows. All the commands in this README are typed into one of these.&nbsp;&nbsp;\|&nbsp;&nbsp;[Go back](#ref-cli)                                                                                     |
| <a id="glossary-dagshub"></a>**DagsHub**                       | The website that hosts this project's training data and MLflow records behind the scenes — the machine-learning equivalent of GitHub. The automated pipeline reads from and writes to it; you don't need an account to run the demo.&nbsp;&nbsp;\|&nbsp;&nbsp;[Go back](#ref-dagshub)                                                            |
| <a id="glossary-docker"></a>**Docker**                         | Software that packages an application together with everything it needs to run — code, libraries, settings — into a self-contained unit called a container, so it behaves identically on any machine. This project uses Docker so you don't need to install Python or any ML libraries yourself.&nbsp;&nbsp;\|&nbsp;&nbsp;[Go back](#ref-docker) |
| <a id="glossary-drift"></a>**Drift**                           | A change in the statistical patterns of incoming data over time, compared to the data the ML model was trained on. If sensor readings start looking meaningfully different from what the model learned on, its predictions can no longer be trusted.&nbsp;&nbsp;\|&nbsp;&nbsp;[Go back](#ref-drift)                                              |
| <a id="glossary-drift-detection"></a>**Drift detection**       | The automated check that compares recent sensor data to the model's original training data and flags whether drift (see above) has occurred.&nbsp;&nbsp;\|&nbsp;&nbsp;[Go back](#ref-drift-detection)                                                                                                                                            |
| <a id="glossary-drift-report"></a>**Drift report**             | An HTML report generated by the drift detection step, showing which sensor features have shifted and by how much. Saved to `reports/drift_report.html` and opened automatically after a full retraining-loop run.&nbsp;&nbsp;\|&nbsp;&nbsp;[Go back](#ref-drift-report)                                                                          |
| <a id="glossary-github"></a>**GitHub**                         | The website that hosts this project's code and version history, and — via GitHub Actions, below — runs the automated retraining workflow.&nbsp;&nbsp;\|&nbsp;&nbsp;[Go back](#ref-github)                                                                                                                                                        |
| <a id="glossary-github-actions"></a>**GitHub Actions**         | GitHub's built-in automation feature. This project uses it to run the retraining workflow automatically whenever drift is detected and new data is pushed.&nbsp;&nbsp;\|&nbsp;&nbsp;[Go back](#ref-github-actions)                                                                                                                               |
| <a id="glossary-mlflow"></a>**MLflow**                         | The tool that keeps a permanent record of every model version this project has ever trained — its settings, how accurate it was, and the finished model file itself. It's what lets the system compare a brand-new model against the one currently running before deciding whether to switch.&nbsp;&nbsp;\|&nbsp;&nbsp;[Go back](#ref-mlflow)  |
| <a id="glossary-mlops"></a>**ML Ops (MLOps)**                  | Machine Learning Operations — the practice of automating and monitoring a machine learning model's full lifecycle in production (training, deployment, monitoring, retraining), rather than treating it as a one-off experiment.&nbsp;&nbsp;\|&nbsp;&nbsp;[Go back](#ref-mlops)                                                                  |
| <a id="glossary-ml-pipeline"></a>**ML pipeline**               | The end-to-end sequence of automated steps that takes raw data all the way to a working, deployed model — here: generating sensor data, serving predictions, detecting drift, and retraining.&nbsp;&nbsp;\|&nbsp;&nbsp;[Go back](#ref-ml-pipeline)                                                                                               |
| <a id="glossary-prediction-request"></a>**Prediction request** | A single message sent to the API containing one machine's sensor readings, asking "is this machine likely to fail?" The API responds with a prediction and a probability.&nbsp;&nbsp;\|&nbsp;&nbsp;[Go back](#ref-prediction-request)                                                                                                            |
| <a id="glossary-retraining"></a>**Retraining**                 | Training a new version of the model on updated data, so its predictions stay accurate as real-world conditions change. In this project, retraining fires automatically once drift is detected.&nbsp;&nbsp;\|&nbsp;&nbsp;[Go back](#ref-retraining)                                                                                               |
| <a id="glossary-simulation-engine"></a>**Simulation engine**   | The component (`src/sensor_simulator.py`) that generates realistic, fake sensor readings — standing in for a real CNC machine — and sends them to the prediction API.&nbsp;&nbsp;\|&nbsp;&nbsp;[Go back](#ref-simulation-engine)                                                                                                                 |
