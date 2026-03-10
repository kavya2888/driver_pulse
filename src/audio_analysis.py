import pandas as pd
import numpy as np

LOUD_DB = 70
VERY_LOUD_DB = 80
ARGUMENT_WEIGHT = 0.6
LOUD_WEIGHT = 0.3
INTENSITY_WEIGHT = 0.1


def detect_audio_events(audio_df):

    df = audio_df.copy()
    df["intensity_score"] = df["audio_level_db"] / 100

    df["is_loud"] = df["audio_level_db"] > LOUD_DB
    df["is_very_loud"] = df["audio_level_db"] > VERY_LOUD_DB

    if "audio_classification" in df.columns:
        df["is_argument"] = df["audio_classification"].str.contains(
            "argument", case=False, na=False
        )
    else:
        df["is_argument"] = False

    df["audio_event_score"] = (
        ARGUMENT_WEIGHT * df["is_argument"].astype(int) +
        LOUD_WEIGHT * df["is_loud"].astype(int) +
        INTENSITY_WEIGHT * df["intensity_score"]
    )

    events = df[df["audio_event_score"] > 0.35].copy()

    events["reason"] = np.where(
        events["is_argument"],
        "Passenger Argument",
        np.where(events["is_very_loud"], "Very Loud Cabin", "High Cabin Noise")
    )

    events["severity"] = events["audio_event_score"].round(3)

    return events[["trip_id", "timestamp", "reason", "severity"]]