import pandas as pd
import numpy as np
import os
import joblib
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from xgboost import XGBClassifier


def train_models():

    trips=pd.read_csv("trips.csv")
    drivers=pd.read_csv("drivers.csv")
    goals=pd.read_csv("driver_goals.csv")

    trips=trips[trips["trip_status"]=="completed"]
    trips["start_time"]=pd.to_datetime(trips["start_time"])
    trips["end_time"]=pd.to_datetime(trips["end_time"])
    trips["trip_hour"]=trips["start_time"].dt.hour
    trips["duration_hours"]=trips["duration_min"]/60

    trips["hour_sin"]=np.sin(2*np.pi*trips["trip_hour"]/24)
    trips["hour_cos"]=np.cos(2*np.pi*trips["trip_hour"]/24)

    trips["trip_speed"]=trips["distance_km"]/trips["duration_hours"]
    trips["fare_per_km"]=trips["fare"]/trips["distance_km"]
    trips["fare_per_min"]=trips["fare"]/trips["duration_min"]

    hourly=trips.groupby(["driver_id","trip_hour"]).agg({
        "fare":"sum",
        "trip_id":"count",
        "distance_km":"sum",
        "duration_hours":"sum",
        "surge_multiplier":"mean",
        "trip_speed":"mean",
        "hour_sin":"mean",
        "hour_cos":"mean"
    }).reset_index()

    hourly.rename(columns={"fare":"earnings_last_hour","trip_id":"trips_last_hour"},inplace=True)
    hourly["avg_fare_per_trip"]=hourly["earnings_last_hour"]/hourly["trips_last_hour"]

    hourly=hourly.merge(drivers,on="driver_id",how="left")
    hourly=hourly.merge(goals,on="driver_id",how="left")

    hourly=hourly.sort_values(["driver_id","trip_hour"])

    hourly["cumulative_earnings"]=hourly.groupby("driver_id")["earnings_last_hour"].cumsum()
    hourly["elapsed_hours"]=hourly.groupby("driver_id")["duration_hours"].cumsum()

    hourly["current_velocity"]=hourly["cumulative_earnings"]/hourly["elapsed_hours"]
    hourly["remaining_hours"]=hourly["target_hours"]-hourly["elapsed_hours"]

    hourly["required_velocity"]=(hourly["target_earnings"]-hourly["cumulative_earnings"])/hourly["remaining_hours"].replace(0,np.nan)

    hourly["velocity_delta"]=hourly["current_velocity"]-hourly["required_velocity"]

    hourly["earnings_last_hour_prev"]=hourly.groupby("driver_id")["earnings_last_hour"].shift(1)
    hourly["earnings_trend"]=hourly["earnings_last_hour"]-hourly["earnings_last_hour_prev"]
    hourly["trip_rate_trend"]=hourly.groupby("driver_id")["trips_last_hour"].diff()

    hourly["goal_on_track"]=(hourly["velocity_delta"]>=-50).astype(int)

    features=[
        "hour_sin","hour_cos","duration_hours","distance_km","surge_multiplier",
        "trip_speed","avg_fare_per_trip","trips_last_hour","earnings_last_hour",
        "current_velocity","required_velocity","velocity_delta",
        "earnings_trend","trip_rate_trend"
    ]

    X=hourly[features].fillna(0)
    y=hourly["goal_on_track"]

    X_train,X_test,y_train,y_test=train_test_split(X,y,test_size=0.2,random_state=42,stratify=y)

    model=XGBClassifier(n_estimators=300,max_depth=6,learning_rate=0.05,subsample=0.8,colsample_bytree=0.8)
    model.fit(X_train,y_train)

    pred=model.predict(X_test)
    print("XGBoost Accuracy:",accuracy_score(y_test,pred))

    offline_model=LogisticRegression(max_iter=200)
    offline_model.fit(X_train,y_train)

    offline_pred=offline_model.predict(X_test)
    print("Offline Model Accuracy:",accuracy_score(y_test,offline_pred))

    def generate_feedback(row):
        delta=row["velocity_delta"]
        if delta>50:return "ð¤© Excellent pace! You're ahead of target."
        elif delta>0:return "ð You're on track."
        elif delta>-100:return "âºï¸ Slightly behind target."
        else:return "ð Consider moving to high-demand zones."

    hourly["driver_feedback"]=hourly.apply(generate_feedback,axis=1)

    base_dir=os.path.dirname(os.path.abspath(__file__))
    project_root=os.path.dirname(base_dir)

    output_dir=os.path.join(project_root,"processed_outputs")
    model_dir=os.path.join(project_root,"models")

    os.makedirs(output_dir,exist_ok=True)
    os.makedirs(model_dir,exist_ok=True)

    hourly.to_csv(os.path.join(output_dir,"trip_summaries.csv"),index=False)

    flags_df=pd.DataFrame({"trip_id":[],"timestamp":[],"reason":[]})
    flags_df.to_csv(os.path.join(output_dir,"flagged_moments.csv"),index=False)

    joblib.dump(model,os.path.join(model_dir,"goal_model.pkl"))
    joblib.dump(offline_model,os.path.join(model_dir,"offline_model.pkl"))
    joblib.dump(features,os.path.join(model_dir,"model_features.pkl"))

    return model,offline_model,features


def predict_goal_status(row,model,features):
    X=row[features].values.reshape(1,-1)
    prob=model.predict_proba(X)[0][1]
    prediction=model.predict(X)[0]
    return prediction,prob