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
        .stButton button {
            background-color: white !important;
            color: black !important;
            border-radius: 10px;
            padding: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        } 
        .stSelectbox div[data-baseweb="select"] > div {
            background-color: white !important;
            color: black !important;
        }
        .stSelectbox div[data-baseweb="select"] input {
            color: black !important;
        }
        button[kind="primary"] {
            background-color: #006400 !important; 
            color: white !important;
        } 
        button[kind="primary"]:hover {
            background-color: #228B22 !important; 
            transition: 0.3s ease;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="title">HYBB Attendance System</div>', unsafe_allow_html=True)
st.markdown('<div class="company">Hygiene Bigbite Pvt Ltd</div>', unsafe_allow_html=True)

# -------------------- GOOGLE AUTH --------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(st.secrets["GOOGLE_SHEETS_CREDS"]), scope
)
client = gspread.authorize(creds)
worksheet = client.open("Manager Visit Tracker").sheet1

# Load or create Roaster sheet
try:
    roaster_sheet = client.open("Manager Visit Tracker").worksheet("Roaster")
except gspread.exceptions.WorksheetNotFound:
    roaster_sheet = client.open("Manager Visit Tracker").add_worksheet("Roaster", rows=1000, cols=5)
    roaster_sheet.insert_row(["Date", "Manager", "Kitchen", "Login Time", "Remarks"], 1)
roaster_df = pd.DataFrame(roaster_sheet.get_all_records())
if not roaster_df.empty and "Date" in roaster_df.columns:
    roaster_df["Date"] = pd.to_datetime(roaster_df["Date"], errors="coerce").dt.date

# -------------------- CONSTANTS --------------------
DRIVE_FOLDER_ID = "1i5SnIkpMPqtU1kSVVdYY4jQK1lwHbR9G"
manager_list = ["", "Ayub Sait", "Rakesh Babu", "John Joseph", "Naveen Kumar M", "Sangeetha RM", "Joy Matabar", "Sonu Kumar", "Samsudeen", "Tauseef", "Bablu C", "Umesh M", "Selva Kumar", "Srividya"]
kitchens = ["ANR01.BLR22", "BSK01.BLR19", "WFD01.BLR06", "MAR01.BLR05", "BTM01.BLR03", "IND01.BLR01", "HSR01.BLR02", "VDP01.CHN02", "MGP01.CHN01", "CMP01.CHN10", "KLN01.BLR09", "TKR01.BLR29", "CRN01.BLR17", "SKN01.BLR07", "HNR01.BLR16", "RTN01.BLR23", "YLK01.BLR15", "NBR01.BLR21", "PGD01.CHN06", "PRR01.CHN04", "FZT01.BLR20", "ECT01.BLR24", "SJP01.BLR08", "KPR01.BLR41", "BSN01.BLR40", "VNR01.BLR18", "SDP01.BLR34", "TCP01.BLR27", "BOM01.BLR04", "CK-Corp","KOR01.BLR12", "SKM01.CHN03", "WFD02.BLR13", "KDG01.BLR14"]
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
        st.success("✅ Punch recorded!")
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

    records = worksheet.get_all_records()
    full_df = pd.DataFrame(records)
    if not full_df.empty:
        full_df["Date"] = pd.to_datetime(full_df["Date"], errors="coerce").dt.date

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

    elif tab == "Attendance":
        if full_df.empty:
            st.info("No attendance data.")
        else:
            sel_date = st.date_input("Date", value=datetime.date.today())
            view_df = full_df[full_df["Date"] == sel_date]

            if view_df.empty:
                st.info("No attendance records for this date.")
            else:
                if not roaster_df.empty:
                    roster_today = roaster_df[roaster_df["Date"] == sel_date][["Manager", "Kitchen"]]
                    view_df["key"] = view_df["Manager Name"] + "|" + view_df["Kitchen Name"]
                    roster_today["key"] = roster_today["Manager"] + "|" + roster_today["Kitchen"]
                    view_df["Mismatch"] = ~view_df["key"].isin(roster_today["key"])
                    view_df = view_df.drop(columns=["key"])

                st.dataframe(view_df, use_container_width=True)

    elif tab == "Visit Summary":
        if full_df.empty:
            st.info("No visit data.")
        else:
            freq = st.radio("Frequency", ["Last 7 Days", "Last 30 Days", "All Time"])
            today = datetime.date.today()
            if freq == "Last 7 Days":
                df_f = full_df[full_df["Date"] >= today - datetime.timedelta(days=7)]
            elif freq == "Last 30 Days":
                df_f = full_df[full_df["Date"] >= today - datetime.timedelta(days=30)]
            else:
                df_f = full_df.copy()
            visits = df_f.groupby(["Manager Name", "Kitchen Name"]).size().reset_index(name="Visits")
            st.dataframe(visits, use_container_width=True)

    elif tab == "Roaster Entry":
        st.subheader("📆 Submit Weekly Roaster")
        with st.form("roaster_form"):
            selected_manager = st.selectbox("Manager Name", manager_list)
            next_monday = datetime.date.today() + datetime.timedelta(days=(7 - datetime.date.today().weekday()) % 7)
            week_start = st.date_input("Week Starting (Monday)", value=next_monday)
            days = [week_start + datetime.timedelta(days=i) for i in range(7)]
            entries = []
            time_choices = [
                (datetime.datetime.combine(datetime.date.today(), datetime.time(7, 0)) + datetime.timedelta(minutes=30 * i)).time().strftime("%H:%M")
                for i in range(34)
            ]
            for day in days:
                st.markdown(f"**{day.strftime('%A %d-%b')}**")
                kitchen = st.selectbox(f"Kitchen for {day.strftime('%A')}", kitchens, key=f"k_{day}")
                login_time = st.selectbox(f"Login Time for {day.strftime('%A')}", time_choices, key=f"t_{day}")
                remark = st.text_input(f"Remarks for {day.strftime('%A')}", key=f"rem_{day}")
                if kitchen:
                    entries.append([day.strftime('%Y-%m-%d'), selected_manager, kitchen, login_time, remark])
            submit_roaster = st.form_submit_button("Submit Roaster")
            if submit_roaster:
                for row in entries:
                    roaster_sheet.append_row(row)
                st.success("✅ Roaster submitted successfully!")
