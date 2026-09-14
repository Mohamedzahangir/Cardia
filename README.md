````markdown
# CARDIA

## Cardiovascular Digital Twin & Interactive Physiology Experiment Platform

> **CARDIA turns cardiovascular physiology into an experiment.**

CARDIA is an interactive cardiovascular digital-twin platform that allows users to observe, infer, perturb, simulate, compare, and explain cardiovascular dynamics through a virtual patient.

Instead of simply displaying predicted values or static medical information, CARDIA creates a living physiological simulation where changes in cardiovascular parameters produce coupled effects across heart chambers, valves, circulation, pressure, volume, cardiac output, and feedback mechanisms.

---

## Core Idea

CARDIA follows the loop:

OBSERVE → INFER → PERTURB → SIMULATE → COMPARE → EXPLAIN

The platform combines:

- Mechanistic cardiovascular simulation
- Interactive 3D heart visualization
- Machine-learning-based physiological parameter inference
- Counterfactual experimentation
- Retrieval-Augmented Generation (RAG)
- Real-time physiological visualization
- Persistent experiment and simulation metadata

The central idea is simple:

> **CARDIA does not merely simulate a heart. It lets a user experiment on a virtual patient, observe coupled cardiovascular consequences in real time, compare alternative trajectories, and understand the underlying physiology.**

---

# Quick Start: How to Run

Running CARDIA is unified into a single command because the **FastAPI backend serves both the API/WebSockets and the frontend**.

### 1. Install Dependencies

From the project root directory:

```bash
pip install -r backend/requirements.txt
```

### 2. Start the Backend & Frontend

From the project root directory:

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

> **Tip**: Add `--reload` during development for automatic reloading when files change.

### 3. Open the Application

Open your web browser and navigate to:

👉 **[http://localhost:8000](http://localhost:8000)** (or `http://127.0.0.1:8000`)

### What Happens Automatically

- **Frontend Cockpit**: Served at `/` (`frontend/index.html`).
- **3D Heart Visualization**: Beating 3D GLB model loads from `/static/assets/heart.glb` with fixed anatomical annotations.
- **Physics Engine & Telemetry**: 0D numerical ODE solver streams real-time telemetry over WebSocket at `/ws/simulation`.
- **AI & Reasoning APIs**: ML inference (`/api/ml/predict`), RAG reasoning (`/api/rag/ask`), and counterfactual experiments (`/api/experiment/run`) are immediately live.
- **Asset Health Check**: Verified at `/api/assets/heart`.

---

# What Makes CARDIA Different?

Most cardiovascular applications focus on one of the following:

- Data visualization
- Prediction
- Medical information
- Static simulation

CARDIA combines these capabilities into an interactive experimental environment.

A user can:

1. Create or select a virtual patient.
2. Observe the baseline cardiovascular state.
3. Change physiological parameters.
4. Run the cardiovascular simulation.
5. Observe the resulting physiological changes.
6. Fork the simulation into counterfactual scenarios.
7. Compare alternative trajectories.
8. Use ML to infer hidden physiological parameters.
9. Ask why a physiological change occurred.
10. Receive a physiology-grounded explanation.

This turns cardiovascular physiology from a static concept into an interactive experiment.

---

# Product Vision

CARDIA aims to make cardiovascular physiology:

- Observable
- Interactive
- Perturbable
- Simulatable
- Comparable
- Explainable

Instead of:

READ → MEMORIZE

CARDIA enables:

OBSERVE → EXPERIMENT → COMPARE → EXPLAIN → UNDERSTAND

---

# System Architecture

```text
                              CARDIA
                                │
                                ▼
                  ┌─────────────────────────┐
                  │     Interactive Web UI  │
                  │                         │
                  │  3D Heart + Vitals HUD │
                  │  Charts + Controls      │
                  │  ML + RAG Panels        │
                  └────────────┬────────────┘
                               │
                         REST / WebSocket
                               │
                  ┌────────────▼────────────┐
                  │         FastAPI         │
                  │     Backend Layer       │
                  │                         │
                  │ Simulation Orchestration│
                  │ State Management        │
                  │ ML / RAG Integration    │
                  └───────┬──────┬──────────┘
                          │      │
              ┌───────────▼─┐ ┌──▼───────────┐
              │ Cardiovascular│ │ AI / Knowledge│
              │ Physics Engine│ │     Layer     │
              └───────┬───────┘ └──────┬───────┘
                      │                │
                      ▼                ▼
               SimulationState     ML + RAG
                      │                │
                      └───────┬────────┘
                              ▼
                     Experiment Engine
                              │
                       ┌──────┴──────┐
                       ▼             ▼
                 Intervention   Counterfactual
                    Runs            Runs
                       │             │
                       └──────┬──────┘
                              ▼
                         Comparison
                              │
                              ▼
                         Explanation
````

---

# Technology Stack

## Frontend

* Next.js
* React
* TypeScript
* Tailwind CSS
* React Three Fiber
* Three.js
* WebSockets
* Interactive charts
* Responsive scientific visualization

## Backend

* Python
* FastAPI
* WebSockets
* Pydantic
* AsyncIO

## Simulation

* Python
* Mechanistic cardiovascular model
* Fixed-timestep numerical simulation
* Four-chamber heart model
* Systemic circulation
* Pulmonary circulation
* Valve dynamics
* Frank-Starling mechanism
* Baroreflex feedback

## Machine Learning

* PyTorch
* Multilayer Perceptron
* Synthetic physiological training data
* Feature extraction
* Hidden-state inference

## RAG

* Curated cardiovascular physiology knowledge
* Text preprocessing
* Chunking
* Embeddings
* Qdrant
* Retrieval-Augmented Generation
* LLM-based explanation

## Database

* Supabase
* PostgreSQL

---

# Cardiovascular Simulation

The simulation engine is the physiological foundation of CARDIA.

It represents four major heart chambers:

```text
Right Atrium
     ↓
Right Ventricle
     ↓
Pulmonary Circulation
     ↓
Left Atrium
     ↓
Left Ventricle
     ↓
Systemic Circulation
     ↺
```

The model contains:

* Right Atrium (RA)
* Right Ventricle (RV)
* Left Atrium (LA)
* Left Ventricle (LV)
* Tricuspid valve
* Pulmonary valve
* Mitral valve
* Aortic valve
* Pulmonary circulation
* Systemic circulation
* Venous return
* Arterial pressure
* Vascular resistance
* Baroreflex feedback
* Cardiac contractility
* Blood volume

---

# Core Physiological Relationships

CARDIA uses mechanistic physiological relationships instead of arbitrary UI values.

## Cardiac Output

```text
CO = HR × SV
```

Where:

* CO = Cardiac Output
* HR = Heart Rate
* SV = Stroke Volume

## Stroke Volume

```text
SV = EDV − ESV
```

Where:

* EDV = End-Diastolic Volume
* ESV = End-Systolic Volume

## Mean Arterial Pressure

The simplified model uses:

```text
MAP ≈ CO × SVR
```

Where:

* MAP = Mean Arterial Pressure
* CO = Cardiac Output
* SVR = Systemic Vascular Resistance

## Blood Flow

```text
Q = ΔP / R
```

Where:

* Q = Flow
* ΔP = Pressure difference
* R = Resistance

These relationships are coupled inside the simulation rather than calculated independently for display.

---

# Simulation Loop

CARDIA operates using a fixed numerical timestep.

```text
SimulationState
      │
      ▼
Advance cardiac phase
      │
      ▼
Calculate chamber elastance
      │
      ▼
Calculate chamber pressures
      │
      ▼
Evaluate valve states
      │
      ▼
Calculate blood flows
      │
      ▼
Update chamber volumes
      │
      ▼
Update systemic circulation
      │
      ▼
Update pulmonary circulation
      │
      ▼
Calculate EDV / ESV / SV / CO
      │
      ▼
Apply physiological feedback
      │
      ▼
Apply disturbances / interventions
      │
      ▼
Emit updated SimulationState
      │
      └──────────────► Repeat
```

The simulation engine remains the single source of truth.

The frontend does not independently calculate physiological values.

---

# Simulation State

The central data contract is `SimulationState`.

Example:

```json
{
  "time": 12.42,
  "hr": 82,
  "bp": {
    "sys": 112,
    "dia": 70,
    "map": 84
  },
  "cardiac": {
    "edv": 118,
    "esv": 55,
    "stroke_volume": 63,
    "cardiac_output": 5.17,
    "contractility": 1.0
  },
  "circulation": {
    "blood_volume": 5.1,
    "svr": 1.1
  },
  "valves": {
    "mitral": false,
    "aortic": true,
    "tricuspid": false,
    "pulmonary": false
  }
}
```

The state is consumed by:

```text
                    SimulationState
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
       Frontend           ML             RAG
          │               │               │
          ▼               ▼               ▼
      3D Heart        Inference      Explanation
          │
          ▼
        Charts
          │
          ▼
     Experiments
```

---

# Real-Time 3D Heart

The 3D heart visualization is directly driven by the cardiovascular simulation.

Important mappings include:

```text
Heart Rate
    ↓
Beat Frequency

Chamber Volume
    ↓
Filling / Expansion

Contractility
    ↓
Contraction Amplitude

Valve State
    ↓
Valve Animation

Blood Flow
    ↓
Flow Visualization
```

The 3D visualization should represent the actual simulation state rather than using random or disconnected animations.

---

# Live Physiological Dashboard

CARDIA exposes real-time physiological measurements such as:

```text
Heart Rate
Systolic Blood Pressure
Diastolic Blood Pressure
Mean Arterial Pressure
EDV
ESV
Stroke Volume
Cardiac Output
Blood Volume
Contractility
SVR
```

The interface also exposes chamber-level information:

```text
Right Atrium
Right Ventricle
Left Atrium
Left Ventricle
```

Relevant chamber information can include:

* Volume
* Pressure
* Filling
* Ejection

---

# Valve Monitoring

CARDIA tracks the state of all four major cardiac valves:

```text
Tricuspid
Pulmonary
Mitral
Aortic
```

Each valve is represented using the actual simulation state:

```text
OPEN
CLOSED
```

Valve visualization is synchronized with the cardiac cycle.

---

# Real-Time Graphs

CARDIA provides live physiological plots including:

* Arterial pressure
* LV pressure
* LV volume
* Cardiac output
* Heart rate

The simulation can run at a higher numerical frequency while the frontend samples the state at a lower visualization frequency.

This maintains smooth visualization without unnecessarily rendering every numerical timestep.

---

# Machine Learning

CARDIA includes a machine-learning layer for hidden physiological parameter inference.

The model receives observable cardiovascular measurements:

```text
HR
SBP
DBP
EDV
ESV
```

and estimates:

```text
Blood Volume
Contractility
SVR
```

The flow is:

```text
Observed Physiological Signals
             │
             ▼
       Feature Extraction
             │
             ▼
          ML Model
             │
             ▼
 ┌───────────┼────────────┐
 ▼           ▼            ▼
Blood      Contractility  SVR
Volume
```

The model is implemented using PyTorch.

The ML component demonstrates physiological inference and is not presented as a clinically validated estimator.

---

# Forward and Inverse Physiology

CARDIA demonstrates two complementary problems.

## Forward Problem

```text
Hidden Physiological Parameters
             ↓
       Cardiovascular Model
             ↓
          Physiology
             ↓
    Observable Measurements
```

## Inverse Problem

```text
Observable Measurements
             ↓
             ML
             ↓
Estimated Hidden Parameters
```

This allows CARDIA to demonstrate both:

* How cardiovascular systems behave
* How hidden physiological parameters can be inferred from observations

---

# Counterfactual Experimentation

A key capability of CARDIA is counterfactual simulation.

A simulation state can be forked into alternative trajectories.

```text
                    Current State
                         │
                   ┌─────┴─────┐
                   │           │
                   ▼           ▼
            No Intervention  Intervention
                   │           │
                   ▼           ▼
             Simulation A  Simulation B
                   │           │
                   └─────┬─────┘
                         ▼
                    Comparison
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
             CO         BP          SV
```

This enables users to explore:

* What happens if a parameter changes?
* Which variables respond first?
* How does the trajectory change?
* What downstream effects occur?
* How does the intervention compare with the baseline?

---

# Experiment Workflow

```text
Create / Select Virtual Patient
            ↓
Observe Baseline
            ↓
Modify Physiological Parameter
            ↓
Run Simulation
            ↓
Observe Response
            ↓
Fork Counterfactual
            ↓
Compare Trajectories
            ↓
Ask "Why?"
            ↓
Receive Physiology-Grounded Explanation
```

---

# Experimental Scenarios

CARDIA supports experimental scenarios such as:

## Hemorrhage

Simulates reduced circulating blood volume and observes the resulting cardiovascular response.

## Hypertension

Simulates increased vascular resistance and observes pressure and cardiovascular consequences.

## Tachycardia

Simulates elevated heart rate and examines effects on filling, stroke volume, and cardiac output.

## Reduced Coronary Flow

Provides an experimental scenario for exploring altered cardiovascular dynamics.

## Free Experiment

Allows users to manipulate supported physiological parameters and observe the resulting system behavior.

---

# RAG and Physiology Explanation

CARDIA includes a Retrieval-Augmented Generation system for answering:

> **Why did this happen?**

The RAG system does not replace the simulation engine.

The simulation determines what happened.

The RAG system explains why it happened.

```text
Current SimulationState
          │
          ▼
      User Question
          │
          ▼
     Knowledge Retrieval
          │
          ▼
Relevant Physiology
          │
          ▼
          LLM
          │
          ▼
Physiology-Grounded Explanation
```

The LLM does not modify the simulation state.

---

# RAG Knowledge Pipeline

```text
Curated Physiology Sources
          │
          ▼
       Extraction
          │
          ▼
        Cleaning
          │
          ▼
       Chunking
          │
          ▼
      Embeddings
          │
          ▼
        Qdrant
          │
          ▼
       Retrieval
          │
          ▼
SimulationState + User Question
          │
          ▼
          LLM
          │
          ▼
Explanation + Sources
```

The knowledge base focuses on cardiovascular physiology.

---

# Explainability

CARDIA connects numerical simulation with natural-language reasoning.

Example:

```text
User:
Why did cardiac output fall?

CARDIA:
Cardiac output decreased because stroke volume decreased.
The reduction in ventricular filling lowered EDV, which
reduced the volume available for ejection.
```

The explanation is grounded using:

* Current simulation state
* Retrieved physiology knowledge
* Changes observed in the simulation trajectory

---

# Frontend

The frontend is designed as a scientific simulation workspace.

The main interface contains:

* Interactive 3D heart
* Live vital signs
* Chamber information
* Valve status
* Real-time physiological graphs
* Simulation controls
* ML inference panel
* RAG explanation panel
* Experiment controls
* Connection status

The frontend is connected to the existing simulation, ML, and RAG systems.

It does not recreate or duplicate the underlying physiological logic.

---

# Frontend Controls

Primary simulation controls include:

```text
START
PAUSE
RESET
```

Additional controls can include:

```text
Simulation Speed
Simulation Time
Scenario Selection
Parameter Controls
```

The interface should communicate system state clearly:

```text
CONNECTING
LIVE
PAUSED
DISCONNECTED
BACKEND ERROR
ML UNAVAILABLE
RAG UNAVAILABLE
```

---

# Backend API

The architecture supports API endpoints such as:

```text
POST /simulation/start
POST /simulation/pause
POST /simulation/reset

POST /experiment/apply

POST /counterfactual/fork

POST /ml/infer

POST /explain

WS /simulation/stream
```

The frontend should use the actual implemented backend routes rather than creating duplicate or fake endpoints.

---

# Database

Supabase/PostgreSQL is used for persistent metadata and experiment results.

Core entities include:

```text
patients
patient_parameters
simulation_sessions
simulation_checkpoints

experiments
experiment_parameters
experiment_results

counterfactual_runs
counterfactual_results

ml_models
ml_predictions

scenarios
knowledge_sources
explanations
```

High-frequency simulation frames should not be persisted individually.

Instead:

```text
High-Frequency Simulation
          ↓
   Memory / WebSocket
          ↓
    Live Frontend
```

Important checkpoints and experiment results can be persisted:

```text
Simulation
    ↓
Checkpoint / Result
    ↓
Supabase
```

---

# Repository Structure

```text
CARDIA/
│
├── simulation/
│   ├── state.py
│   ├── cardiovascular.py
│   ├── chambers.py
│   ├── circulation.py
│   ├── valves.py
│   ├── feedback.py
│   ├── parameters.py
│   ├── adapter.py
│   └── demo.py
│
├── ml/
│   ├── data/
│   │   └── patient_generator.py
│   │
│   ├── features/
│   │   └── extractor.py
│   │
│   ├── models/
│   │   └── mlp.py
│   │
│   ├── inference/
│   │   └── predictor.py
│   │
│   └── training/
│       └── train.py
│
├── rag/
│   ├── data/
│   │   ├── source/
│   │   └── clean/
│   │
│   └── answer/
│       └── answer_engine.py
│
├── frontend/
│
├── backend/
│
└── README.md
```

---

# Architecture Principles

## Single Source of Truth

`SimulationState` is the authoritative physiological state.

The frontend, ML layer, RAG layer, and experiment system consume the simulation state rather than independently generating physiological values.

## Physics Before AI

The simulation determines physiological behavior.

ML estimates hidden physiological parameters.

RAG explains the physiological behavior.

```text
Physics
   ↓
Simulation

ML
   ↓
Inference

RAG
   ↓
Explanation

Frontend
   ↓
Visualization + Interaction
```

## No Fake Physiological Values

The UI must not use random or hardcoded physiological values for live simulation output.

Every displayed live value should originate from the actual simulation or an explicitly identified derived result.

## Separation of Concerns

Each subsystem has a clear responsibility:

```text
Simulation
    ↓
What happened?

ML
    ↓
What hidden parameters could explain the observations?

RAG
    ↓
Why did it happen?

Frontend
    ↓
How can the user observe and interact with it?
```

---

# Validation

The cardiovascular simulation engine has been validated through its automated test suite.

Current simulation milestone:

```text
70 / 70 tests passing
```

The tests cover the core cardiovascular simulation behavior and physiological/numerical consistency.

Future integrations should preserve the existing simulation test suite.

---

# End-to-End Data Flow

```text
                         USER
                          │
                          ▼
                   CARDIA FRONTEND
                          │
             ┌────────────┼────────────┐
             │            │            │
             ▼            ▼            ▼
         Controls         ML          "WHY?"
             │            │            │
             ▼            ▼            ▼
         Backend      Predictor        RAG
             │            │            │
             ▼            │            │
      Simulation Engine   │            │
             │            │            │
             ▼            ▼            ▼
       SimulationState ────────────────┐
             │                         │
       ┌─────┼─────────┐              │
       │     │         │              │
       ▼     ▼         ▼              ▼
      3D   Charts     ML          Explanation
    Heart             Inference
       │
       ▼
  Experiment Engine
       │
   ┌───┴────┐
   ▼        ▼
Baseline  Counterfactual
   │        │
   └───┬────┘
       ▼
   Comparison
       │
       ▼
    Results
```

---

# Example User Journey

A user starts with a virtual patient.

Example baseline:

```text
HR  = 72 bpm
BP  = 120/80 mmHg
EDV = 120 mL
ESV = 50 mL
SV  = 70 mL
CO  = 5.04 L/min
```

The user changes a physiological parameter.

CARDIA then:

1. Applies the intervention.
2. Advances the cardiovascular simulation.
3. Updates chamber dynamics.
4. Updates valve states.
5. Updates systemic circulation.
6. Updates pulmonary circulation.
7. Updates feedback mechanisms.
8. Streams the updated state.
9. Updates the 3D heart.
10. Updates live charts.
11. Allows a counterfactual comparison.
12. Allows ML inference.
13. Allows the user to ask why the change occurred.

The result is an interactive cardiovascular experiment rather than a static dashboard.

---

# Example Concept

```text
BASELINE

HR: 72
CO: 5.04 L/min
BP: 120/80
EDV: 120 mL
ESV: 50 mL

        │
        │ Apply perturbation
        ▼

SIMULATION

Chamber dynamics change
        ↓
Valve timing changes
        ↓
Flow changes
        ↓
Arterial pressure changes
        ↓
Baroreflex responds
        ↓
New equilibrium / trajectory

        │
        ▼

COMPARE

Baseline vs Intervention

        │
        ▼

INFER

ML estimates hidden parameters

        │
        ▼

EXPLAIN

RAG + SimulationState

        │
        ▼

UNDERSTAND
```

---

# Why CARDIA Matters

Cardiovascular physiology is highly coupled.

Changing one variable can influence multiple parts of the cardiovascular system.

For example:

```text
Change in Blood Volume
        ↓
Venous Return
        ↓
Ventricular Filling
        ↓
EDV
        ↓
Stroke Volume
        ↓
Cardiac Output
        ↓
Arterial Pressure
        ↓
Baroreflex
        ↓
Heart Rate / SVR
        ↓
New Cardiovascular State
```

CARDIA makes these interactions visible and experimentally observable.

---

# Future Extensions

Potential future extensions include:

* Additional cardiovascular pathophysiology scenarios
* More detailed ventricular mechanics
* Personalized virtual patients
* Additional physiological signals
* More sophisticated inverse modeling
* Larger cardiovascular knowledge base
* Experiment replay
* Experiment sharing
* Parameter sensitivity analysis
* Multi-variable perturbations
* Long-duration simulations
* Research-oriented experiment notebooks

---

# Disclaimer

CARDIA is an experimental educational and research-oriented cardiovascular simulation platform.

It uses simplified mechanistic models, synthetic virtual patients, machine-learning inference, and retrieved physiology knowledge.

CARDIA is not a medical device.

It should not be used for:

* Diagnosis
* Treatment decisions
* Clinical decision-making
* Emergency medical decisions
* Replacement of professional medical advice

---

# Vision

The long-term vision of CARDIA is to transform cardiovascular physiology from something users simply read about into something they can actively experiment with.

```text
SEE IT
   ↓
CHANGE IT
   ↓
SIMULATE IT
   ↓
COMPARE IT
   ↓
ASK WHY
   ↓
UNDERSTAND IT
```

---

# CARDIA

### Cardiovascular Digital Twin & Interactive Physiology Experiment Platform

> **Turn cardiovascular physiology into an experiment.**

```text
Observe.
Infer.
Perturb.
Simulate.
Compare.
Explain.
```

```
```
