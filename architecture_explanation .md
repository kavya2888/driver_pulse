# Driver Pulse - System Architecture Explanation

---

## Overview

Driver Pulse is an end-to-end driver analytics platform that collects raw sensor data from a driver's device, processes it both on-device and on the cloud, and surfaces actionable insights through a Streamlit dashboard. The system is split into four layers as shown in the architecture diagram.

---

## Layer 1 - Raw Data Sources (On-Device Sensors)

These are the five raw inputs that feed the entire pipeline:

- **Accelerometer** - Captures accel_x, accel_y, accel_z at 1Hz. Used to detect sudden braking, acceleration, sharp turns, and potholes.
- **GPS** - Provides latitude, longitude, and speed_kmh. Used to geo-tag events, cluster pothole locations, and calculate trip speed.
- **Audio Sensor** - Records cabin audio levels in decibels (dB). Used to detect arguments or excessively loud cabin noise.
- **Trip Metadata** - Includes fare, duration, distance, start/end time per trip. Used for goal tracking, feature engineering, and ML model training.
- **Driver Goals** - Stores each driver's target earnings and target hours. Used to compute pace, velocity delta, and on-track status.

---

## Layer 2 - On-Device / Edge Processing

Edge computing refers to processing data as close to the source as possible - directly on the driver's smartphone or in-vehicle device - rather than sending everything to a remote server first. This is a core architectural decision in Driver Pulse for several reasons:

- **Latency:** A dangerous driving event (sudden brake, sharp turn) needs to be detected and logged immediately. Sending raw sensor data to the cloud and waiting for a response would introduce unacceptable delays. Edge processing detects events in the same sampling cycle they occur.
- **Bandwidth efficiency:** Raw accelerometer data at 1Hz across an 8-hour shift produces thousands of data points. Processing on-device means only meaningful events and aggregated scores are transmitted to the cloud, not the entire raw signal.
- **Offline resilience:** The edge layer continues to function with no internet connection. All signal filtering, threshold comparisons, and local flag generation work independently of server availability.
- **Battery conservation:** Edge logic is limited to simple arithmetic operations - filter coefficients and threshold comparisons. No model inference, no network calls, and no large memory allocations happen during active trip recording, keeping CPU load minimal.
- **Privacy at the source:** Sensitive data like raw audio is reduced to a scalar dB value on-device before anything is stored or transmitted. The raw signal never leaves the device.

### Signal Pre-processing
Raw accelerometer signals are cleaned before any event detection:
- `lowpass_filter()` - Applies a Butterworth low-pass filter (cutoff 0.3 Hz) to remove high-frequency vibration noise from accel_x and accel_y.
- `remove_gravity()` - Subtracts the gravity baseline from accel_z by averaging readings when the vehicle is stationary (speed < 2 km/h), giving a clean vertical acceleration signal for pothole detection.
- `adaptive_threshold()` - Dynamically computes detection thresholds based on signal mean and standard deviation (k=2.5), so the system adapts to each driver's baseline driving style rather than using fixed global values.

### Offline Fallback Model
A LogisticRegression model is trained alongside the main XGBoost model and saved to disk. If the device loses connectivity, this lightweight model can still run goal-on-track inference locally using the same 14 features, ensuring the driver continues to receive pace feedback without needing a server connection.

---

## Layer 3 - Off-Device / Cloud Processing

This layer handles all compute-heavy tasks after the trip data is uploaded.

### Data Ingestion (ingestion.py)
Loads all six CSV files from the data directory: trips, drivers, accelerometer data, audio intensity data, driver goals, and earnings velocity log. Timestamps are parsed to datetime objects at this stage so downstream components receive clean, typed data.

### Analytics Engine (engine.py)
The central orchestrator. It:
- Calls `detect_motion_events()` and `detect_audio_events()` and concatenates their outputs into a unified flags DataFrame.
- Merges trip data with goals and velocity log to produce a per-trip summary.
- Computes stress_score (flag_count / 10, clipped to 1) and trip_quality_rating (Excellent / Good / Risky / Poor based on flag count).
- Engineers 14 ML features including hour_sin/hour_cos (cyclical time encoding), trip_speed, fare_per_km, current_velocity, required_velocity, and velocity_delta.

### accln_flagging.py (flagging_system.py)
Runs the full motion analysis pipeline on the cloud using the uploaded accelerometer CSV. Groups data by trip_id, runs `process_trip()` for each trip, and runs `deduplicate_potholes()` across all trips to cluster repeated pothole sightings at the same GPS location. A pothole reported across N trips gets a combined confidence score of: 1 - (1 - mean_confidence)^N.

### audio_analysis.py
Runs the audio event detection pipeline on the uploaded audio intensity CSV and returns a DataFrame of flagged moments with trip_id, timestamp, reason, and severity.

### XGBoost Model (app.py)
Trains an XGBClassifier (300 estimators, max_depth 6, learning_rate 0.05) on the trip_summaries data. The binary label goal_on_track is 1 if velocity_delta >= -50 (driver is within 50 units of the required earning velocity). The trained model is saved as goal_model.pkl.

### Outputs
- **flagged_moments.csv** - All motion and audio flags with trip_id, timestamp, and reason.
- **trip_summaries.csv** - Per-trip summary with all engineered features, stress score, quality rating, and ML label.
- **goal_model.pkl** - Trained XGBoost classifier for goal-on-track prediction.
- **offline_model.pkl** - Trained LogisticRegression classifier for offline fallback.

---

## Layer 4 - Driver Feedback Loop (Streamlit Dashboard)

The dashboard (streamlit_app.py) is the interface through which drivers consume all processed insights.

- **Login / Auth** - Driver authenticates using their Driver ID (format: DRV001) and a shared password. Session state persists the driver_id for all downstream filtering.
- **Driver Overview** - Displays total earnings, trips completed, average earnings per trip, and most common trip quality rating. All metrics are filtered to the logged-in driver only.
- **Goal Progress** - A Plotly gauge chart shows percentage progress toward the driver's target earnings. Backed by driver_goals.csv and computed from the trips fare sum.
- **On-Track / At-Risk Alerts** - Uses the is_on_track flag from the velocity log merge. Displays a success, warning, or error banner depending on pace and progress percentage.
- **Safety Flags** - Lets the driver select any flagged trip from a dropdown and view the timestamped list of flags (reason column from flagged_moments.csv).
- **ML Prediction** - The goal_on_track score from the XGBoost model is surfaced in the trip summary, giving a data-driven probability estimate of whether the driver will meet their goal.
- **Driving Tips** - Static context-aware tips shown at the bottom (avoid sudden braking, smooth acceleration, reduce cabin noise) aligned to the most common flag types.
- **Trip History Table** - Full expandable table of all the driver's trips for self-review.

The driver acts on these insights in their next trip, closing the feedback loop.

---

## Key Engineering Trade-offs

### 1. Real-Time vs. Post-Trip Processing

**Decision:** Edge layer runs lightweight flagging in near real-time during the trip; cloud layer runs full ML training and feature engineering post-trip.

**What happens in real-time (on-device):**
- Signal filtering and gravity removal run on every accelerometer sample as it arrives.
- Threshold comparisons for braking, acceleration, turns, and potholes are evaluated instantly.
- Audio dB level is checked against thresholds and a local severity score is computed per interval.
- All detected events are buffered locally on the device with their timestamps.

**What happens post-trip (cloud):**
- The full accelerometer and audio CSVs are uploaded and reprocessed by the Analytics Engine.
- Cross-trip pothole deduplication runs across all historical trips - this requires the full dataset and cannot be done in real-time on a single device.
- XGBoost model training uses the complete trip_summaries table, which only exists after all trips are ingested and features are engineered.
- The goal_on_track ML score, stress_score, and trip_quality_rating are all computed post-trip and surfaced on the dashboard.

**Trade-off accepted:** The driver does not see their ML-derived goal score during a live trip, only after processing completes. The offline LogisticRegression model partially bridges this gap for goal pacing in low-connectivity conditions.

---

### 2. Connectivity & Resilience

**Decision:** Train and save both an XGBoost model (goal_model.pkl) and a LogisticRegression model (offline_model.pkl) using the same 14 features.

**Justification:** The XGBoost model is more accurate but requires cloud access to run inference via the dashboard. The LogisticRegression model is small enough to ship with the app and run entirely offline. If connectivity is lost mid-shift, the driver still receives a goal-on-track prediction. Motion and audio flags are computed locally and buffered, so no flag data is lost during an outage. When connectivity is restored, buffered data is uploaded and the cloud pipeline reprocesses it.

**Trade-off accepted:** The offline model is less accurate than XGBoost (logistic regression cannot capture non-linear interactions between features like velocity_delta and earnings_trend). This is acceptable because the offline model is only a fallback, not the primary inference path.

---

### 3. Battery & Resource Management

**Decision:** Keep edge processing limited to signal filtering and threshold comparisons. No neural networks, no heavy model inference on-device during active trips.

**Justification:** The accelerometer sampling is set at 1Hz (FS = 1), which is low enough to be power-efficient while still capturing meaningful driving events (sudden brakes typically last 1-3 seconds). The lowpass filter uses a simple 2nd-order Butterworth IIR filter, which is computationally trivial. Audio is sampled as a single dB scalar per interval, not as raw waveform data, which dramatically reduces the compute and storage burden. The minimum speed threshold (MIN_SPEED_KMH = 5.0) ensures the flagging system does not waste cycles processing stationary or near-stationary readings.

**Trade-off accepted:** The 1Hz sampling rate may miss very brief transient events (sub-second spikes). The merge_nearby_events logic with a 3-second gap compensates by grouping closely spaced events rather than trying to capture every individual sample.

---

### 4. Privacy & Data Minimisation

**Decision:** Collect and retain the minimum data necessary to generate insights. Raw sensitive signals are reduced to derived scores at the point of capture and never stored or transmitted.

**How this is applied across the system:**
- **Audio:** Raw audio waveforms are never recorded. The sensor captures only a single dB scalar per interval. Only the computed severity score and reason label (e.g. "Passenger Argument") are written to flagged_moments.csv. Passenger conversations are never stored in any form.
- **GPS aggregation:** Pothole locations are rounded to a 0.0005-degree grid cell (approximately 50 metres) before storage. This means individual trip routes cannot be reconstructed from the pothole map - only approximate road segments are retained.
- **Trip data scoping:** The dashboard filters all data strictly by driver_id at query time. A driver can only see their own trips, flags, and goal data - no cross-driver data is ever exposed through the UI.
- **Minimal retention:** Only two output files are persisted (flagged_moments.csv and trip_summaries.csv). Raw accelerometer and audio CSVs are inputs only and are not modified or re-stored by the pipeline.

**Trade-off accepted:** By discarding raw audio, it is impossible to review or appeal an audio flag after the fact. A driver flagged for a "Passenger Argument" cannot provide evidence that the classification was incorrect. This is a deliberate trade-off in favour of passenger privacy.
