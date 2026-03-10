from ingestion import load_all_data
from engine import UberAnalyticsEngine
import os
import joblib


def run():

    data = load_all_data()

    engine = UberAnalyticsEngine()

    flags, summary = engine.generate_outputs(data)

    base_dir = os.path.dirname(__file__)
    project_root = os.path.join(base_dir, "..")

    out_dir = os.path.join(project_root, "processed_outputs")
    model_dir = os.path.join(project_root, "models")

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(model_dir, exist_ok=True)

    # ------------------------------------------------
    # Save processed outputs
    # ------------------------------------------------

    flags.to_csv(
        os.path.join(out_dir, "flagged_moments.csv"),
        index=False
    )

    summary.to_csv(
        os.path.join(out_dir, "trip_summaries.csv"),
        index=False
    )

    features = [
        "hour_sin",
        "hour_cos",
        "duration_hours",
        "distance_km",
        "surge_multiplier",
        "trip_speed",
        "avg_fare_per_trip",
        "trips_last_hour",
        "earnings_last_hour",
        "current_velocity",
        "required_velocity",
        "velocity_delta",
        "earnings_trend",
        "trip_rate_trend"
    ]

    X = summary[features].fillna(0)
    y = summary["goal_on_track"]

    from sklearn.model_selection import train_test_split
    from sklearn.linear_model import LogisticRegression
    from xgboost import XGBClassifier

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )

    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8
    )

    model.fit(X_train, y_train)

    offline_model = LogisticRegression(max_iter=200)
    offline_model.fit(X_train, y_train)

    # ------------------------------------------------
    # Save models
    # ------------------------------------------------

    joblib.dump(model, os.path.join(model_dir, "goal_model.pkl"))
    joblib.dump(offline_model, os.path.join(model_dir, "offline_model.pkl"))
    joblib.dump(features, os.path.join(model_dir, "model_features.pkl"))

    print("DONE: Generated trip summaries and trained ML model.")


if __name__ == "__main__":
    run()