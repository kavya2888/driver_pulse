import streamlit as st
import pandas as pd
import os
import plotly.graph_objects as go

# Page Configuration
st.set_page_config(
    page_title="Driver Pulse | Track Your Goal",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def apply_custom_styles():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    .stApp {
        background: radial-gradient(circle at 50% 50%, #1a1c2c 0%, #050505 100%);
        font-family: 'Inter', sans-serif;
        color: white;
    }

    /* Glassmorphic Elements */
    .metric-card {
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        padding: 24px;
        border-radius: 16px;
        text-align: center;
        transition: all 0.3s ease;
    }
    .metric-title { color: #888; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 2px; }
    .metric-value { color: #ffffff; font-size: 2rem; font-weight: 800; margin-top: 5px; }

    .nav-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 15px 25px;
        background: rgba(255, 255, 255, 0.03);
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        margin-bottom: 30px;
    }

    .section-title {
        font-size: 1.5rem;
        font-weight: 700;
        margin: 2.5rem 0 1rem 0;
        color: #ffffff;
        border-left: 4px solid #4facfe;
        padding-left: 15px;
    }

    .tip-card {
        padding:15px;
        border-radius:10px;
        border:1px solid rgba(120,120,120,0.15);
        background-color:rgba(255,255,255,0.03);
        margin-bottom:10px;
        transition: transform 0.2s;
        cursor: pointer;
    }
    .tip-card:hover { transform: scale(1.02); background-color:rgba(255,255,255,0.06); }

    /* Login Card Styling */
    [data-testid="stVerticalBlock"] > div:has(input) {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(20px);
        border-radius: 20px;
        padding: 40px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    header, footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

apply_custom_styles()

# Session State
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.driver = None

# Login Page
def login_page():
    _, col2, _ = st.columns([1, 1.4, 1])
    with col2:
        # --- Added Welcome Greeting ---
        st.markdown("""
            <div style='text-align:center; margin-bottom: -20px;'>
                <p style='color: #4facfe; font-weight: 800; letter-spacing: 1px; font-size: 0.9rem;'>
                    WELCOME BACK!
                </p>
                <p style='color: #888; font-size: 1rem; margin-top: -10px;'>
                    Please authorize to access your dashboard
                </p>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<h1 style='text-align:center; letter-spacing:-2px; margin-top:0;'>DRIVER PULSE</h1>", unsafe_allow_html=True)
        
        username = st.text_input("Driver ID", placeholder="eg:DRV001")
        password = st.text_input("Password", type="password")
        
        if st.button("Authorize Login", use_container_width=True):
            if username.startswith("DRV") and password == "Uber123":
                st.session_state.logged_in = True
                st.session_state.driver = username
                st.rerun()
            else:
                st.error("Invalid Credentials")

#  Main App Content
if not st.session_state.logged_in:
    login_page()
else:
    # Navigation & Logout Header
    nav_left, nav_right = st.columns([5, 1])
    with nav_left:
        st.markdown(f"""
        <div class='nav-container'>
            <div style='font-weight:900; font-size:1.5rem;'>DRIVER PULSE</div>
            <div style='color:#888;'>Driver ID: <b style='color:white;'>{st.session_state.driver}</b></div>
        </div>
        """, unsafe_allow_html=True)
    with nav_right:
        if st.button("Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

    # Paths and Data Loading
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)
    OUTPUT_DIR = os.path.join(PROJECT_ROOT, "processed_outputs")
    DATA_DIR = os.path.join(PROJECT_ROOT, "data")

    def load_csv(path):
        return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()

    trips = load_csv(os.path.join(DATA_DIR, "trips.csv"))
    summary = load_csv(os.path.join(OUTPUT_DIR, "trip_summaries.csv"))
    flags = load_csv(os.path.join(OUTPUT_DIR, "flagged_moments.csv"))
    goals = load_csv(os.path.join(DATA_DIR, "driver_goals.csv"))

    # Driver-specific Filter
    driver = st.session_state.driver
    driver_trips = trips[trips["driver_id"] == driver]
    driver_summary = summary[summary["driver_id"] == driver]
    driver_trip_ids = driver_trips["trip_id"].tolist()
    driver_flags = flags[flags["trip_id"].isin(driver_trip_ids)]
    driver_goals = goals[goals["driver_id"] == driver]

    # Metrics
    total_earnings = driver_trips["fare"].sum() if not driver_trips.empty else 0
    trips_completed = len(driver_trips)
    earnings_per_trip = total_earnings / trips_completed if trips_completed > 0 else 0
    most_common_quality = driver_summary["trip_quality_rating"].value_counts().idxmax() if not driver_summary.empty else "N/A"

    st.markdown("<div class='section-title'> Driver Overview</div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    
    m_data = [("Total Earnings", f"₹{int(total_earnings):,}"), ("Trips Completed", trips_completed), ("Avg. Trip Quality", most_common_quality), ("Avg Earnings/Trip", f"₹{earnings_per_trip:.0f}")]
    cols = [c1, c2, c3, c4]
    for i, (label, val) in enumerate(m_data):
        cols[i].markdown(f"<div class='metric-card'><div class='metric-title'>{label}</div><div class='metric-value'>{val}</div></div>", unsafe_allow_html=True)
    
    # Goal Progress
    st.markdown("<div class='section-title'> Goal Progress</div>", unsafe_allow_html=True)

    if driver_goals.empty :
       st.info("No active goal found. Set a target in your profile to track your progress!")
       st.markdown("""
        <div style='text-align:center; padding: 50px; background: rgba(255,255,255,0.02); border-radius: 16px; border: 1px dashed rgba(255,255,255,0.1);'>
            <p style='color: #888;'>Goal data currently unavailable for this Driver ID.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
       target = driver_goals.iloc[-1]["target_earnings"]
       progress = min(total_earnings/target, 1)
    
       gauge = go.Figure(go.Indicator(
          mode="gauge+number", value=progress*100,
          number={'suffix': "%", 'font': {'color': 'white', 'size': 50}},
       gauge={
            'axis':{'range':[0, 100], 'tickcolor': "white"},
            'bar':{'color': "#4facfe"},
            'bgcolor': "rgba(255,255,255,0.05)",
            'steps': [{'range': [0, 100], 'color': 'rgba(255,255,255,0.01)'}]
        }
       ))
       gauge.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)',
        height=400, 
        margin=dict(t=50, b=20, l=50, r=50)
        )
       st.plotly_chart(gauge, use_container_width=True)

       g1, g2, g3 = st.columns(3)
       g1.metric("Target Earnings", f"₹{target:,}")
       g2.metric("Current Earnings", f"₹{total_earnings:,}")
       g3.metric("Remaining", f"₹{max(target-total_earnings, 0):,}")

    # Goal Pace Status  
    st.markdown("<div class='section-title'> Goal Pace Status</div>", unsafe_allow_html=True)

    if driver_goals.empty:
       st.write("Please set a goal to see your pace analysis.")
    elif not driver_summary.empty:
       pace = driver_summary.iloc[-1]
       is_on_track = pace.get("is_on_track", pace.get("goal_on_track", False))
    
       if is_on_track:
          if progress >= 1: 
             st.success("🎉 Excellent! You have already exceeded your earnings goal.")
          else: 
            st.success("✅ Good Job! You are on track to meet your earnings goal.")
       else:
          if progress >= 0.6: 
            st.warning("⚠ You are at risk of missing your goal. Very little time remains!")
          else: 
            st.error("🚨 You are falling behind. Consider completing more trips to catch up.")
    else:
        st.write("Not enough trip data yet to calculate pace.")

    # Safety Flags 
    st.markdown("<div class='section-title'> Trip Safety Flags</div>", unsafe_allow_html=True)
    flag_trips = driver_flags["trip_id"].unique()

    st.write(f"{len(flag_trips)} trips have safety flags.")
    if len(flag_trips) > 0:
        trip_selected = st.selectbox("Select a flagged trip", flag_trips)
        st.dataframe(driver_flags[driver_flags["trip_id"]==trip_selected][["timestamp","reason"]], use_container_width=True)
    else:
        st.write("No safety flags recorded.")

    # Driving Tips
    st.markdown("<div class='section-title'> Driving Tips </div>", unsafe_allow_html=True)
    tips_list = ["Avoid sudden braking", "Maintain smooth acceleration", "Reduce loud cabin noise"]
    for tip in tips_list:
        st.markdown(f"<div class='tip-card'>{tip}</div>", unsafe_allow_html=True)
        
    # Full Trip History
    st.markdown("<div class='section-title'>Trips Summary</div>", unsafe_allow_html=True)
    with st.expander("📜 Full Trip History", expanded=True):
        st.dataframe(driver_trips, use_container_width=True)
        st.dataframe(driver_trips, use_container_width=True)

