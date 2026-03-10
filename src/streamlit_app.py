import streamlit as st
import pandas as pd
import os
import plotly.graph_objects as go

st.set_page_config(page_title="Driver Performance Portal", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

OUTPUT_DIR = os.path.join(PROJECT_ROOT,"processed_outputs")
DATA_DIR = os.path.join(PROJECT_ROOT,"data")


def load_csv(path):
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame()


trips = load_csv(os.path.join(DATA_DIR,"trips.csv"))
summary = load_csv(os.path.join(OUTPUT_DIR,"trip_summaries.csv"))
flags = load_csv(os.path.join(OUTPUT_DIR,"flagged_moments.csv"))
goals = load_csv(os.path.join(DATA_DIR,"driver_goals.csv"))

st.title("🚖 Driver Performance Portal")

# Driver Selection

drivers = sorted(trips["driver_id"].unique())
driver = st.selectbox("Select Driver", drivers)

driver_trips = trips[trips["driver_id"] == driver]
driver_summary = summary[summary["driver_id"] == driver]

# Safety Flags

driver_trip_ids = driver_trips["trip_id"].tolist()

driver_flags = flags[
    flags["trip_id"].isin(driver_trip_ids)
]

# Metrics

total_earnings = driver_trips["fare"].sum()
trips_completed = len(driver_trips)

earnings_per_trip = (
    total_earnings / trips_completed
    if trips_completed > 0 else 0
)

if not driver_summary.empty and "trip_quality_rating" in driver_summary.columns:
    quality_counts = driver_summary["trip_quality_rating"].value_counts()
    most_common_quality = quality_counts.idxmax()
else:
    most_common_quality = "No data"

c1,c2,c3,c4 = st.columns(4)

c1.metric("Total Earnings", f"₹{int(total_earnings)}")
c2.metric("Trips Completed", trips_completed)
c3.metric("Trip Quality", most_common_quality)
c4.metric("Avg. Earnings Per Trip", f"₹{earnings_per_trip:.0f}")

# Goal Progress

st.subheader("🎯 Goal Progress")

driver_goals = goals[goals["driver_id"] == driver]

target = 0
current = total_earnings

if not driver_goals.empty:

    goal = driver_goals.iloc[-1]

    target = goal["target_earnings"]

    progress = min(current/target,1) if target > 0 else 0
    percent = progress * 100

    remaining = max(target-current,0)

    status_color = "green"

    if not driver_summary.empty:

        pace = driver_summary.iloc[-1]

        is_on_track = (
            pace["is_on_track"]
            if "is_on_track" in pace
            else pace.get("goal_on_track", False)
        )

        if not is_on_track:
            status_color = "yellow" if progress >= 0.6 else "red"

    gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=percent,
        number={'suffix': "%"},
        title={'text': "Goal Completion"},
        gauge={
            'axis': {'range': [0,100]},
            'bar': {'color': status_color}
        }
    ))

    st.plotly_chart(gauge,use_container_width=True)

    g1,g2,g3 = st.columns(3)

    g1.metric("Target Earnings",f"₹{target}")
    g2.metric("Current Earnings",f"₹{current}")
    g3.metric("Remaining",f"₹{remaining}")

else:
    st.info("No goal data available")

# Goal Pace Status

if not driver_summary.empty:

    st.subheader("🚀 Goal Pace Status")

    pace = driver_summary.iloc[-1]

    is_on_track = (
        pace["is_on_track"]
        if "is_on_track" in pace
        else pace.get("goal_on_track", False)
    )

    progress = current / target if target > 0 else 0

    if is_on_track:

        if progress >= 1:
            st.success("🎉 Good Job! You are ahead of your goal. You still have sufficient time left.")
        else:
            st.success("✅ Good Job! You are on track to meet your goal. You still have sufficient time left.")

    else:

        if progress >= 0.6:
            st.warning("⚠ Hurry up! You are at risk. There is not much time left to meet your goal.")
        else:
            st.error("🚨 Hurry up! You are falling behind your target. Try completing more trips quickly.")

# Trip Safety Flags

st.subheader("🚨 Trip Safety Flags")

flag_trips = driver_flags["trip_id"].unique()

st.write(f"{len(flag_trips)} trips have safety flags.")

if len(flag_trips) > 0:

    trip_selected = st.selectbox(
        "Select a flagged trip",
        flag_trips
    )

    trip_flags = driver_flags[
        driver_flags["trip_id"] == trip_selected
    ]

    st.dataframe(
        trip_flags[["timestamp","reason"]]
    )

else:
    st.write("No safety flags recorded.")

# Tips

st.subheader("💡 Driving Tips")

tips = [
    "Avoid sudden braking",
    "Maintain smooth acceleration",
    "Reduce loud cabin noise"
]

tips_text = "\n".join([f"- {tip}" for tip in tips])

st.info(tips_text)

# Full Trip History

with st.expander(f"📜 Full Trip History ({len(driver_trips)} trips)", expanded=True):

    st.dataframe(driver_trips)