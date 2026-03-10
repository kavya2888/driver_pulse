import pandas as pd
import numpy as np

from motion_analysis import detect_motion_events
from audio_analysis import detect_audio_events


class UberAnalyticsEngine:
    def generate_outputs(self, data):

        accel_df = data["accel"]
        audio_df = data["audio"]
        trips = data["trips"]
        goals = data["goals"]
        vel_log = data["vel_log"]

        # ── Motion Analysis ─────────────────────
        motion_flags = detect_motion_events(accel_df)

        # ── Audio Analysis ──────────────────────
        audio_flags = detect_audio_events(audio_df)

        # ── Combine Flags ───────────────────────
        flags = pd.concat([motion_flags, audio_flags], ignore_index=True)

        # ── Trip Summary ────────────────────────
        summaries = trips.copy()

        # Merge goals data
        summaries = pd.merge(
            summaries,
            data["goals"][["driver_id","target_earnings","target_hours"]],
            on="driver_id",
            how="left"
        )

        summaries["target_hours"] = summaries["target_hours"].fillna(8)
        summaries["target_earnings"] = summaries["target_earnings"].fillna(2000)

        flag_counts = (
            flags.groupby("trip_id")
            .size()
            .reset_index(name="flag_count")
        )
        
        summaries = pd.merge(
            summaries,
            flag_counts,
            on="trip_id",
            how="left"
        )

        summaries["flag_count"] = summaries["flag_count"].fillna(0)

        # ── Stress Score ────────────────────────
        summaries["stress_score"] = np.clip(
            summaries["flag_count"] / 10,
            0,
            1
        )

        # ── Trip Quality Rating ─────────────────
        def rate_trip(flags):
            if flags == 0:
                return "Excellent"
            elif flags <= 2:
                return "Good"
            elif flags <= 5:
                return "Risky"
            else:
                return "Poor"

        summaries["trip_quality_rating"] = summaries["flag_count"].apply(rate_trip)

        # ── Feature Engineering for ML ──────────

        summaries["start_time"] = pd.to_datetime(summaries["start_time"])
        summaries["trip_hour"] = summaries["start_time"].dt.hour
        summaries["duration_hours"] = summaries["duration_min"] / 60

        summaries["hour_sin"] = np.sin(2 * np.pi * summaries["trip_hour"] / 24)
        summaries["hour_cos"] = np.cos(2 * np.pi * summaries["trip_hour"] / 24)

        summaries["trip_speed"] = summaries["distance_km"] / summaries["duration_hours"]
        summaries["fare_per_km"] = summaries["fare"] / summaries["distance_km"]
        summaries["fare_per_min"] = summaries["fare"] / summaries["duration_min"]

        # ── Velocity Logic ──────────────────────

        latest_vel = (
            vel_log
            .sort_values("timestamp")
            .groupby("driver_id")
            .tail(1)
        )

        pace_logic = pd.merge(
            goals,
            latest_vel,
            on="driver_id",
            how="left"
        )

        pace_logic["pace_delta"] = (
            pace_logic["current_velocity"]
            - pace_logic["target_velocity"]
        )

        pace_logic["is_on_track"] = pace_logic["pace_delta"] >= 0

        summaries = pd.merge(
            summaries,
            pace_logic[["driver_id","current_velocity","target_velocity","pace_delta","is_on_track"]],
            on="driver_id",
            how="left"
        )

        summaries["is_on_track"] = summaries["is_on_track"].fillna(False)
        summaries["pace_delta"] = summaries["pace_delta"].fillna(0)

        # ── ML Feature Columns ──────────────────

        summaries["remaining_hours"] = summaries["target_hours"] - summaries["duration_hours"]

        summaries["required_velocity"] = (
            (summaries["target_earnings"] - summaries["fare"]) /
            summaries["remaining_hours"].replace(0,np.nan)
        )

        summaries["velocity_delta"] = (
            summaries["current_velocity"] - summaries["required_velocity"]
        )

        summaries["earnings_last_hour"] = summaries["fare"]
        summaries["trips_last_hour"] = 1
        summaries["avg_fare_per_trip"] = summaries["fare"]

        summaries["earnings_trend"] = 0
        summaries["trip_rate_trend"] = 0

        # ── ML Label ────────────────────────────
        summaries["goal_on_track"] = (summaries["velocity_delta"] >= -50).astype(int)

        return flags, summaries