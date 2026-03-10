# Driver Pulse - Group 19

Driver Pulse is an analytics system that surfaces insights about **driver safety signals and earnings progress** using telemetry data and trip records. The system processes motion and audio signals alongside trip metadata to generate interpretable analytics that help drivers understand both **driving stress signals and whether they are on pace to meet their earnings goals**.

This document serves as an **engineering handoff** describing system structure, setup instructions, design tradeoffs, and operational outputs.

---

## 🔗 Quick Links
* **Live Application:** [[https://driverpulse-pggfocbhbiew2oddpf5v7r.streamlit.app/]]
* **Demo Video:** [[https://drive.google.com/drive/folders/14lg6z9vxIwJmvezjNMkgmtvwuycOsRKa]]
* **GitHub Repo Link:** [[https://github.com/kavya2888/driver_pulse]]

### 🔑 Judge Login Credentials
| Field | Value |
| :--- | :--- |
| **Username** | `DRVxxx` (e.g., `DRV144`) |
| **Password** | `Uber123` |

> **Note to Judges:** The Streamlit application is hosted on a free-tier cloud instance. The first load may take **20–40 seconds** as the container wakes up.

---

### Key Features
1. **Driving Safety Monitoring**
   * Detects **Harsh Braking**, **Harsh Acceleration**, and **Sudden Motion Spikes** using accelerometer data.
   * Analyzes **Audio Intensity** to identify abnormal noise spikes (potential passenger conflicts or stressful environments).
   
2. **Earnings Velocity Forecasting**
   * Evaluates the rate of income relative to a daily target.
   * Estimates **Current Earning Speed** vs. **Required Earning Speed**.
   * Uses an ML model to determine **Goal Completion Probability**.

3. **Driver Dashboard**
   * Real-time **Goal Progress Gauges**.
   * Detailed **Safety Event Explainer** (mapping telemetry to specific timestamps).
   * Comprehensive **Trip History** audit logs.

 ---
# System Overview

Driver Pulse converts raw operational signals into structured driver analytics through a modular pipeline.

Core analytics modules include:

* **Earnings Velocity Module** — determines whether drivers are on track to meet earnings goals
* **Stress Score Module** — estimates workload intensity from driving events
* **Flagging System** — detects risky driving events from telemetry signals

Outputs are exposed through a **Streamlit dashboard** and structured logs.

---

# Setup Instructions

## 1. Install Dependencies

```
pip install -r requirements.txt
```

Dependencies include:

* pandas
* numpy
* scikit-learn
* xgboost
* streamlit
* plotly
* joblib

---

## 2. Generate Processed Analytics Data

Run the analytics pipeline:

```
python src/app.py
```

This generates structured outputs in:

```
processed_outputs/
    trip_summaries.csv
    flagged_moments.csv
```

---

## 3. Launch the Dashboard

```
python -m streamlit run src/streamlit_app.py
```

The application will be available at:

```
http://localhost:8501
```

---

# Data Outputs

## Trip Summaries

Contains aggregated analytics per trip including:

* stress score
* trip quality rating
* earnings velocity metrics
* goal progress indicators

## Flagged Moments

Logs detected driving events including:

* timestamp
* trip ID
* event reason

These logs provide **transparent traceability between raw signals and analytics outputs**.

---

# Design Tradeoffs

### Deterministic Metrics vs Predictive Models

The system combines deterministic analytics with machine learning:

* Velocity formulas provide transparent earnings progress indicators.
* An XGBoost classifier predicts the probability of reaching earnings goals.
* Logistic Regression serves as a lightweight fallback model for environments where advanced libraries may not be available.

This hybrid approach balances **interpretability and predictive capability**.

---

### Privacy Considerations

The system processes **audio intensity levels only**, not recorded audio. This avoids capturing or storing potentially sensitive speech data.

Additionally:

* raw telemetry signals are minimized after preprocessing
* only aggregated analytics outputs are exposed to the dashboard

---

# Operational Constraints

### Real-Time Feedback

Driver feedback requires low-latency calculations. The analytics engine therefore prioritizes lightweight feature engineering and fast model inference.

### Resource Efficiency
XGBoost was selected because it performs well on structured tabular data while maintaining fast inference speeds. Logistic regression provides a lightweight fallback option.

---
# Module Breakdown

### 1. Source Code (`src/`)
- **ingestion.py**: Handles data loading and timestamp alignment.
- **motion_analysis.py**: Applies digital signal processing (DSP) to accelerometer data to detect motion events.
- **audio_analysis.py**: Processes audio streams to detect safety-related auditory events.
- **engine.py**: Fuses motion and audio signals to compute driver strain metrics.
- **app.py**: Orchestrates the pipeline and generates processed outputs.
- **streamlit_app.py**: Provides a Streamlit-based dashboard for visualization of driver metrics.

### 2. Data Management
- **data/**: Contains raw CSV files; read-only.
- 
### 3. Generated Outputs
- **processed_outputs/**: Stores results from the analytics engine, including:
  - `trip_summaries.csv`
  - `flagged_moments.csv`

### 4. Documentation 
- **requirements.txt**: Lists all required Python libraries.
- **progress_log.md**: Development milestone log.
- **design_doc.pdf**: Full system design documentation, including algorithms.
- **system_architecture.jpeg**: Full system design architecture diagram
---

This modular design ensures that backend processing, data management, and frontend visualization remain decoupled, making the system maintainable and scalable.
