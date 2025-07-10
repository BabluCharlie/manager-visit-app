import streamlit as st
import geocoder
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Google Sheets Auth
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("your_credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open("Manager Visit Tracker").sheet1

# Custom CSS for orange & green theme
st.markdown("""
    <style>
        .main {
            background-color: #FFA500;
            padding: 20px;
            border-radius: 10px;
        }
        .stButton button {
            background-color: #228B22;
            color: white;
            border-radius: 8px;
            padding: 0.5em 2em;
            font-size: 1.1em;
        }
        .title-text {
            color: white;
            font-weight: bold;
            font-size: 32px;
        }
    </style>
""", unsafe_allow_html=True)

# Login Interface
st.markdown('<div class="main">', unsafe_allow_html=True)
st.markdown('<p class="title-text">🟢 Manager Punch System</p>', unsafe_allow_html=True)

manager_list = ["Bablu C", "Cletus Antony", "Manjunath M", "Santhosh P"]
manager = st.selectbox("Select Your Name", manager_list)
if st.button("Login"):
    st.session_state.logged_in = True
    st.session_state.manager = manager
st.markdown('</div>', unsafe_allow_html=True)

# Check Login
if st.session_state.get("logged_in", False):
    st.success(f"Welcome {st.session_state.manager}! Please Punch In/Out.")

    kitchen = st.selectbox("Select Kitchen", [
        "ANR01.BLR22", "BSK01.BLR19", "WFD01.BLR06", "MAR01.BLR05", "BTM01.BLR03",
        "IND01.BLR01", "HSR01.BLR02", "VDP01.CHN02", "MGP01.CHN01", "CMP01.CHN10",
        "KLN01.BLR09", "TKR01.BLR29", "CRN01.BLR17", "SKN01.BLR07", "HNR01.BLR16",
        "RTN01.BLR23", "YLK01.BLR15", "NBR01.BLR21", "PGD01.CHN06", "PRR01.CHN04",
        "FZT01.BLR20", "ECT01.BLR24", "SJP01.BLR08", "KPR01.BLR41", "BSN01.BLR40",
        "VNR01.BLR18", "SDP01.BLR34", "TCP01.BLR27"
    ])
    action = st.radio("Select Action", ["Punch In", "Punch Out"])

    if st.button("Submit Punch"):
        try:
            g = geocoder.ip('me')
            lat, lon = g.latlng if g.latlng else ("N/A", "N/A")
            now = datetime.datetime.now()
            data = [
                now.strftime("%Y-%m-%d"),
                now.strftime("%H:%M:%S"),
                st.session_state.manager,
                kitchen,
                action,
                lat,
                lon,
                f"https://www.google.com/maps?q={lat},{lon}"
            ]
            sheet.append_row(data)
            st.success("✅ Punch recorded successfully!")
        except Exception as e:
            st.error(f"Error: {e}")
