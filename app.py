import streamlit as st
import gspread
import datetime
import geocoder
import json
import requests
import pandas as pd
import pytz
from oauth2client.service_account import ServiceAccountCredentials

# -------------------- CONFIG --------------------
st.set_page_config(page_title="HYBB Attendance System", layout="wide")

# -------------------- STYLING --------------------
st.markdown(
    """
    <style>
        body, .stApp, section.main {background-color: #FFA500 !important;}
        .title {font-size: 32px; color: #006400; font-weight: bold; text-align: center; margin-top: 10px;}
        .company {font-size: 18px; text-align: center; color: white; margin-bottom: 20px; font-weight: bold;}
        .mismatch {background-color:#FFCDD2 !important;}
        .stTextInput > div > input,
        .stSelectbox > div > div,
        .stRadio > div,
        .stCameraInput,
        .stDataFrame,
        .stForm,
        .stButton button {background-color: white !important; color: black !important; border-radius: 10px; padding: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);} 
        button[kind="primary"] {background-color: #006400 !important; color: white !important;} 
        button[kind="primary"]:hover {background-color: #228B22 !important; transition: 0.3s ease;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="title">HYBB Attendance System</div>', unsafe_allow_html=True)
st.markdown('<div class="company">Hygiene Bigbite Pvt Ltd</div>', unsafe_allow_html=True)

# -------------------- GOOGLE AUTH --------------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(st.secrets["GOOGLE_SHEETS_CREDS"]), scope
)
client = gspread.authorize(creds)
worksheet = client.open("Manager Visit Tracker").sheet1

# Load Roaster sheet (create if it doesn't exist) --------------------
try:
    roaster_sheet = client.open("Manager Visit Tracker").worksheet("Roaster")
except gspread.exceptions.WorksheetNotFound:
    roaster_sheet = (
        client.open("Manager Visit Tracker").add_worksheet("Roaster", rows=1000, cols=5)
    )
    roaster_sheet.insert_row(["Date", "Manager", "Kitchen", "Login Time", "Remarks"], 1)
roaster_df = pd.DataFrame(roaster_sheet.get_all_records())
if not roaster_df.empty and "Date" in roaster_df.columns:
    roaster_df["Date"] = pd.to_datetime(roaster_df["Date"], errors="coerce").dt.date

# -------------------- CONSTANTS --------------------
DRIVE_FOLDER_ID = "1i5SnIkpMPqtU1kSVVdYY4jQK1lwHbR9G"
manager_list = [
    "",
    "Ayub Sait",
    "Rakesh Babu",
    "John Joseph",
    "Naveen Kumar M",
    "Sangeetha RM",
    "Joy Matabar",
    "Sonu Kumar",
    "Samsudeen",
    "Tauseef",
    "Bablu C",
    "Umesh M",
    "Selva Kumar",
    "Srividya",
]
kitchens = [
    "ANR01.BLR22",
    "BSK01.BLR19",
    "WFD01.BLR06",
    "MAR01.BLR05",
    "BTM01.BLR03",
    "IND01.BLR01",
    "HSR01.BLR02",
    "VDP01.CHN02",
    "MGP01.CHN01",
    "CMP01.CHN10",
    "KLN01.BLR09",
    "TKR01.BLR29",
    "CRN01.BLR17",
    "SKN01.BLR07",
    "HNR01.BLR16",
    "RTN01.BLR23",
    "YLK01.BLR15",
    "NBR01.BLR21",
    "PGD01.CHN06",
    "PRR01.CHN04",
    "FZT01.BLR20",
    "ECT01.BLR24",
    "SJP01.BLR08",
    "KPR01.BLR41",
    "BSN01.BLR40",
    "VNR01.BLR18",
    "SDP01.BLR34",
    "TCP01.BLR27",
    "BOM01.BLR04",
    "CK-Corp",
    "KOR01.BLR12",
    "SKM01.CHN03",
    "WFD02.BLR13",
    "KDG01.BLR14",
]

# -------------------- LAYOUT --------------------
left_col, right_col = st.columns([2, 1])

# -------- LEFT: Punch Form --------
with left_col:
    st.subheader("Punch In / Punch Out")
    with st.form("punch_form"):
        sel_manager = st.selectbox("Manager", manager_list)
        sel_kitchen = st.selectbox("Kitchen", [""] + kitchens)
        sel_action = st.radio("Action", ["Punch In", "Punch Out"])
        photo = st.camera_input("Selfie (Required)")
        punch_submit = st.form_submit_button("Submit Punch")

    if punch_submit:
        if not sel_manager or not sel_kitchen or photo is None:
            st.warning("All fields & selfie required!")
            st.stop()

        now = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
        today_str, time_str = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
        g = geocoder.ipinfo("me")
        lat, lon = g.latlng if g.latlng else ("N/A", "N/A")
        location_url = (
            f"https://www.google.com/maps?q={lat},{lon}" if lat != "N/A" else "Location N/A"
        )

        # Duplicate check
        if any(
            r.get("Date") == today_str
            and r.get("Manager Name") == sel_manager
            and r.get("Kitchen Name") == sel_kitchen
            and r.get("Action") == sel_action
            for r in worksheet.get_all_records()
        ):
            st.warning("Duplicate punch today.")
            st.stop()

        # Upload selfie to Drive
        resp = requests.post(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true",
            headers={"Authorization": f"Bearer {creds.get_access_token().access_token}"},
            files={
                "data": (
                    "metadata",
                    json.dumps({"name": f"{sel_manager}_{today_str}_{time_str}.jpg", "parents": [DRIVE_FOLDER_ID]}),
                    "application/json",
                ),
                "file": photo.getvalue(),
            },
        )
        selfie_url = (
            f"https://drive.google.com/file/d/{resp.json().get('id')}/view?usp=sharing"
            if resp.status_code == 200
            else "UploadErr"
        )

        worksheet.append_row(
            [
                today_str,
                time_str,
                sel_manager,
                sel_kitchen,
                sel_action,
                lat,
                lon,
                selfie_url,
                location_url,
            ]
        )
        st.success("Punch recorded!")
        st.rerun()

# -------- RIGHT: Dashboard Tabs --------
with right_col:
    tab = st.radio(
        "Dashboard",
        ["Roaster View", "Attendance", "Visit Summary", "Roaster Entry"],
        format_func=lambda x: (
            "📅 Roaster" if x == "Roaster View" else (
                "📋 Attendance" if x == "Attendance" else (
                    "📊 Visit Summary" if x == "Visit Summary" else "📝 Roaster Entry"
                )
            )
        ),
    )

    # -------- Pull attendance data once --------
    records = worksheet.get_all_records()
    full_df = pd.DataFrame(records)
    if not full_df.empty:
        full_df["Date"] = pd.to_datetime(full_df["Date"], errors="coerce").dt.date

    # ---------------- TAB: Roaster View ----------------
    if tab == "Roaster View":
        if roaster_df.empty:
            st.info("No roaster data.")
        else:
            mgr_filter = st.selectbox("Manager", ["All"] + sorted(roaster_df["Manager"].unique()))
            date_filter = st.date_input("Date", value=datetime.date.today())
            temp = roaster_df.copy()
            if mgr_filter != "All":
                temp = temp[temp["Manager"] == mgr_filter]
            temp = temp[temp["Date"] == date_filter]
            st.dataframe(temp, use_container_width=True)

    # ---------------- TAB: Attendance ------------------
    elif tab == "Attendance":
        if full_df.empty:
            st.info("No attendance data.")
        else:
            sel_date = st.date_input("Date", value=datetime.date.today())
            view
