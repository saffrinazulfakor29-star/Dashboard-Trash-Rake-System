import streamlit as st
import pandas as pd
import time

CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQd963Q6VuLwBc2ZY5Ll_37AbrH0dbemKBEH4SNWtR1jHkWYARbf9jPvGuBzjtwT8kbJZUEk5TPWZBh/pub?output=csv"

st.set_page_config(
    page_title="IoT Trash Rake Monitoring System",
    layout="wide"
)

st.title("🌊 IoT Trash Rake Monitoring Dashboard")
st.caption("Majlis Bandaraya Seberang Perai (MBSP)")

@st.cache_data(ttl=30)
def load_data():
    df = pd.read_csv(CSV_URL)
    df.columns = ["Timestamp", "WiFi", "ToF", "WaterLevel", "Status"]
    df["ToF"] = pd.to_numeric(df["ToF"], errors="coerce").fillna(0)
    df["TrashStatus"] = df["ToF"].apply(lambda x: "DETECTED" if x >= 1120 else "CLEAR")
    return df

df = load_data()
latest = df.iloc[-1]

# ================= KPI =================
col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "📡 WiFi Status",
    "CONNECTED" if "CONNECTED" in str(latest["WiFi"]).upper() else "DISCONNECTED"
)

col2.metric(
    "🗑 Trash Detection",
    latest["TrashStatus"],
    f"ToF: {int(latest['ToF'])} µs"
)

col3.metric(
    "💧 Water Level",
    latest["WaterLevel"]
)

col4.metric(
    "⚙ System Status",
    latest["Status"]
)

st.divider()

# ================= CHARTS =================
colL, colR = st.columns(2)

with colL:
    st.subheader("📈 Water Level Trend")
    level_map = {"LOW": 1, "NORMAL": 2, "HIGH": 3}
    df["LevelNum"] = df["WaterLevel"].map(level_map)
    st.line_chart(df["LevelNum"].tail(50))

with colR:
    st.subheader("📊 Trash Detection Events")
    bar = df.copy()
    bar["Detected"] = bar["TrashStatus"].apply(lambda x: 1 if x == "DETECTED" else 0)
    st.bar_chart(bar["Detected"].tail(20))

st.divider()

# ================= DATA TABLE =================
st.subheader("📋 Sensor Log Database")

with st.expander("Show raw data"):
    st.dataframe(
        df.tail(200),
        use_container_width=True
    )

# ================= AUTO REFRESH =================
st.caption("🔄 Auto refresh every 30 seconds")
time.sleep(1)
