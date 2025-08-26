import os
import base64
from datetime import timedelta
import time

import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd

# Firebase Admin SDK
import firebase_admin
from firebase_admin import credentials, firestore

# -----------------------------------------------------------------------------
# Page setup
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Raspberry Pi Server", layout="wide")

# -----------------------------------------------------------------------------
# Firebase initialization (exactly once; safe for Streamlit reruns)
# -----------------------------------------------------------------------------
def init_firebase():
    if not firebase_admin._apps:
        try:
            service_account = dict(st.secrets["firebase"])
        except Exception:
            st.error(
                "Firebase credentials not found. "
                "Add your service account JSON under `[firebase]` in Settings → Secrets."
            )
            st.stop()

        try:
            cred = credentials.Certificate(service_account)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(
                "Failed to initialize Firebase. "
                "Please verify your service account fields in Secrets."
            )
            # Show a short, non-sensitive hint
            st.caption("Tip: Ensure `private_key` retains its BEGIN/END lines and newlines.")
            st.stop()

init_firebase()
db = firestore.client()

# -----------------------------------------------------------------------------
# Data access
# -----------------------------------------------------------------------------
@st.cache_data(ttl=60)
def fetch_initial_data(collection_name: str) -> pd.DataFrame:
    latest = list(
        db.collection(collection_name)
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(20)  # Get an initial set of 20 points
        .stream()
    )
    if not latest:
        return pd.DataFrame(columns=["timestamp", "voltage"])

    rows = [d.to_dict() for d in latest]
    # Filter for valid rows and reverse to be in chronological order
    valid_rows = [r for r in rows if r.get("timestamp") and r.get("voltage") is not None]
    return pd.DataFrame(valid_rows)[::-1]

# New function to get only the latest data since the last check
def fetch_new_data(collection_name: str, last_timestamp) -> pd.DataFrame:
    """Pulls new documents from Firestore added after the last known timestamp."""
    if last_timestamp is None:
        return pd.DataFrame()

    docs = (
        db.collection(collection_name)
        .where("timestamp", ">", last_timestamp)
        .order_by("timestamp", direction=firestore.Query.ASCENDING)
        .stream()
    )

    rows = []
    for d in docs:
        doc = d.to_dict()
        ts = doc.get("timestamp")
        v = doc.get("voltage")
        if ts is not None and v is not None:
            rows.append({"timestamp": ts, "voltage": v})
    
    return pd.DataFrame(rows)

# -----------------------------------------------------------------------------
# Helpers (from your original code)
# -----------------------------------------------------------------------------
def apply_background_image_if_exists(path: str = "background.jpg"):
    # ... (your original background image code is unchanged)
    if not os.path.exists(path):
        return
    try:
        with open(path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url("data:image/jpg;base64,{img_b64}");
                background-size: cover;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        st.warning("Background image found but could not be applied.")

# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------
apply_background_image_if_exists()

with st.sidebar:
    st.subheader("Live Streaming Graph from Database")

    # Fetch the initial data to display
    initial_df = fetch_initial_data(COLLECTION)

    if not initial_df.empty:
        # Prepare the DataFrame for st.line_chart (requires a DatetimeIndex)
        initial_df["timestamp"] = pd.to_datetime(initial_df["timestamp"])
        chart_data = initial_df.set_index("timestamp")

        # Create the line chart element
        chart = st.line_chart(chart_data)

        # Store the last timestamp to know where to start the next fetch
        last_ts = initial_df["timestamp"].iloc[-1]
        
        # This loop will run continuously to fetch and display new data
        while True:
            new_df = fetch_new_data(COLLECTION, last_ts)
            if not new_df.empty:
                new_df["timestamp"] = pd.to_datetime(new_df["timestamp"])
                new_chart_data = new_df.set_index("timestamp")
                
                # Append the new data to the chart
                chart.add_rows(new_chart_data)
                
                # Update the last timestamp
                last_ts = new_df["timestamp"].iloc[-1]
            
            # Wait for 2 seconds before checking for new data again
            time.sleep(2)
    else:
        st.warning(f"No data found in the '{COLLECTION}' collection yet. Waiting for data...")
        # Optional: add a refresh button for the initial load
        if st.button("🔄 Check for Data", type="primary"):
            st.rerun()

    # (The rest of your UI for Device Info remains the same)
    st.subheader("Device Information")
    # ... your original device info code ...

'''
elif side_page == "Upload":
    # ... your original upload page code ...
    st.title("📂 Upload Files")

else:  # About
    # ... your original about page code ...
    st.title("About")
'''
