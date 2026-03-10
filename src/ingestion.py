import pandas as pd
import os

def load_all_data():
    base_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "data"
    )
  
    # ── Loading all files
    files = {
        "trips": "trips.csv",
        "drivers": "drivers.csv",
        "accel": "accelerometer_data.csv",
        "audio": "audio_intensity_data.csv",
        "goals": "driver_goals.csv",
        "vel_log": "earnings_velocity_log.csv"
    }

    data = {}

    for key, name in files.items():

        path = os.path.join(base_path, name)

        if not os.path.exists(path):
            raise FileNotFoundError(f"Missing file: {name}")

        df = pd.read_csv(path)

        data[key] = df

    # ── Parse timestamps early (engine will use them)
    if "start_time" in data["trips"].columns:
        data["trips"]["start_time"] = pd.to_datetime(data["trips"]["start_time"])

    if "end_time" in data["trips"].columns:
        data["trips"]["end_time"] = pd.to_datetime(data["trips"]["end_time"])

    if "timestamp" in data["vel_log"].columns:
        data["vel_log"]["timestamp"] = pd.to_datetime(data["vel_log"]["timestamp"])

    if "timestamp" in data["accel"].columns:
        data["accel"]["timestamp"] = pd.to_datetime(data["accel"]["timestamp"])

    if "timestamp" in data["audio"].columns:
        data["audio"]["timestamp"] = pd.to_datetime(data["audio"]["timestamp"])

    return data
