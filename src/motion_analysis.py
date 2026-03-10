import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt

FS = 1
MIN_SPEED_KMH = 5
ACC_THRESHOLD = 2.5
BRAKE_THRESHOLD = 3.0
TURN_THRESHOLD = 2.8

def lowpass_filter(signal, cutoff=0.3):
    nyq = FS / 2
    if cutoff >= nyq or len(signal) < 10:
        return signal
    b, a = butter(2, cutoff / nyq, btype="low")
    return filtfilt(b, a, signal)

def detect_motion_events(df):

    events = []

    for trip_id, trip in df.groupby("trip_id"):

        ax = lowpass_filter(trip["accel_x"].values)
        ay = lowpass_filter(trip["accel_y"].values)

        for i in range(len(trip)):

            speed = trip.iloc[i]["speed_kmh"]
            if speed < MIN_SPEED_KMH:
                continue

            ax_val = ax[i]
            ay_val = ay[i]

            ts = trip.iloc[i]["timestamp"]
            magnitude = np.sqrt(ax_val**2 + ay_val**2)

            if ax_val > ACC_THRESHOLD:
                events.append({
                    "trip_id": trip_id,
                    "timestamp": ts,
                    "reason": "Sudden Acceleration",
                    "severity": round(magnitude,2)
                })

            if ax_val < -BRAKE_THRESHOLD:
                events.append({
                    "trip_id": trip_id,
                    "timestamp": ts,
                    "reason": "Sudden Brake",
                    "severity": round(magnitude,2)
                })

            if abs(ay_val) > TURN_THRESHOLD:
                events.append({
                    "trip_id": trip_id,
                    "timestamp": ts,
                    "reason": "Sharp Turn",
                    "severity": round(magnitude,2)
                })

    return pd.DataFrame(events)