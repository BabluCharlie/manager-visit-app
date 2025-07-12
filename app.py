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
st.markdown("""
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
        button[kind="primary"] {
            background-color: #006400 !important;
            color: white !important;
        }
        button[kind="primary"]:hover {
            background-color: #228B22 !important;
            transition: 0.3s ease;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">HYBB Attendance System</div>', unsafe_allow_html=True)
st.markdown('<div class="company">Hygiene Bigbite Pvt Ltd</div>', unsafe_allow_html=True)

# -------------------- GOOGLE AUTH --------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(st.secrets["GOOGLE_SHEETS_CREDS"]), scope)
client = gspread.authorize(creds)
worksheet = client.open("Manager Visit Tracker").sheet1

# Load Roaster Sheet
try:
    roaster_sheet = client.open("Manager Visit Tracker").worksheet("Roaster")
    roaster_df = pd.DataFrame(roaster_sheet.get_all_records())
    if "Date" in roaster_df.columns:
        roaster_df["Date"] = pd.to_datetime(roaster_df["Date"], errors='coerce').dt.date
except:
    roaster_df = pd.DataFrame()
    roaster_sheet = client.open("Manager Visit Tracker").add_worksheet("Roaster", rows=1000, cols=5)
    roaster_sheet.insert_row(["Date", "Manager", "Kitchen", "Remarks"], 1)

# -------------------- CONSTANTS --------------------
DRIVE_FOLDER_ID = "1i5SnIkpMPqtU1kSVVdYY4jQK1lwHbR9G"
SHARED_DRIVE_ID = ""
manager_list = ["", "Ayub Sait", "Rakesh Babu", "John Joseph", "Naveen Kumar M", "Sangeetha RM", "Joy Matabar", "Sonu Kumar", "Samsudeen", "Tauseef", "Bablu C", "Umesh M"]
kitchens = ["ANR01.BLR22", "BSK01.BLR19", "WFD01.BLR06", "MAR01.BLR05", "BTM01.BLR03", "IND01.BLR01", "HSR01.BLR02", "VDP01.CHN02", "MGP01.CHN01", "CMP01.CHN10", "KLN01.BLR09", "TKR01.BLR29", "CRN01.BLR17", "SKN01.BLR07", "HNR01.BLR16", "RTN01.BLR23", "YLK01.BLR15", "NBR01.BLR21", "PGD01.CHN06", "PRR01.CHN04", "FZT01.BLR20", "ECT01.BLR24", "SJP01.BLR08", "KPR01.BLR41", "BSN01.BLR40", "VNR01.BLR18", "SDP01.BLR34", "TCP01.BLR27", "BOM01.BLR04", "CK-Corp"]

# -------------------- SIDEBAR NAVIGATION --------------------
section = st.sidebar.radio("Navigation", ["Punch In/Out", "Dashboard", "Roaster Entry"])

# -------------------- SECTION: Punch In/Out --------------------
if section == "Punch In/Out":
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Punch In / Punch Out")
        with st.form("punch_form"):
            manager = st.selectbox("Select Manager", manager_list, key="manager")
            kitchen = st.selectbox("Select Kitchen", [""] + kitchens, key="kitchen")
            action = st.radio("Action", ["Punch In", "Punch Out"], key="action")
            photo = st.camera_input("Take a Selfie (Required)", key="selfie")
            submitted = st.form_submit_button("Submit Punch")
        if submitted:
            if not manager or not kitchen or not photo:
                st.warning("All fields and selfie are required!")
                st.stop()
            now = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
            today_str = now.strftime("%Y-%m-%d")
            time_str = now.strftime("%H:%M:%S")
            g = geocoder.ipinfo('me')
            lat, lon = g.latlng if g.latlng else ("N/A", "N/A")
            location_url = f"https://www.google.com/maps?q={lat},{lon}" if lat != "N/A" else "Location not available"
            if any(r.get("Date") == today_str and r.get("Manager Name") == manager and r.get("Kitchen Name") == kitchen and r.get("Action") == action for r in worksheet.get_all_records()):
                st.warning("Duplicate punch detected for today.")
                st.stop()
            upload_url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true"
            headers = {"Authorization": f"Bearer {creds.get_access_token().access_token}"}
            metadata = {"name": f"{manager}_{today_str}_{time_str}.jpg", "parents": [DRIVE_FOLDER_ID]}
            if SHARED_DRIVE_ID:
                metadata["driveId"] = SHARED_DRIVE_ID
            resp = requests.post(upload_url, headers=headers, files={'data': ('metadata', json.dumps(metadata), 'application/json'), 'file': photo.getvalue()})
            selfie_url = f"https://drive.google.com/file/d/{resp.json().get('id')}/view?usp=sharing" if resp.status_code==200 else "UploadError"
            worksheet.append_row([today_str, time_str, manager, kitchen, action, lat, lon, selfie_url, location_url])
            st.success("Punch recorded!")
            st.experimental_rerun()

    with col2:
        tab = st.radio("📊 Dashboard", ["Roaster", "Attendance", "Visit Summary"])
        records = worksheet.get_all_records()
        full_df = pd.DataFrame(records)
        full_df["Date"] = pd.to_datetime(full_df["Date"], errors='coerce').dt.date
        if tab == "Roaster" and not roaster_df.empty:
            mgr_filter = st.selectbox("Manager", ["All"]+sorted(roaster_df["Manager"].unique().tolist()))
            date_filter = st.date_input("Date", value=datetime.date.today())
            temp_roaster = roaster_df.copy()
            if mgr_filter != "All":
                temp_roaster = temp_roaster[temp_roaster["Manager"] == mgr_filter]
            if date_filter:
                temp_roaster = temp_roaster[temp_roaster["Date"] == date_filter]
            st.dataframe(temp_roaster)
        elif tab == "Attendance" and not full_df.empty:
            dash_date = st.date_input("Attendance Date", value=datetime.date.today())
            view_df = full_df[full_df["Date"] == dash_date]
            if not roaster_df.empty:
                roster_today = roaster_df[(roaster_df["Date"] == dash_date)][["Manager", "Kitchen"]]
                view_df["key"] = view_df["Manager Name"] + "|" + view_df["Kitchen Name"]
                roster_today["key"] = roster_today["Manager"] + "|" + roster_today["Kitchen"]
                view_df["Mismatch"] = ~view_df["key"].isin(roster_today["key"])
                view_df_style = view_df.style.apply(lambda x: ['background-color:#FFCDD2' if v else '' for v in x], subset=["Mismatch"])
                st.dataframe(view_df_style.hide(columns=["key"]))
            else:
                st.dataframe(view_df)
        elif tab == "Visit Summary" and not full_df.empty:
            freq = st.radio("Frequency", ["Last 7 Days", "Last 30 Days", "All Time"])
            today = datetime.date.today()
            if freq == "Last 7 Days":
                count_df = full_df[full_df["Date"] >= today - datetime.timedelta(days=7)]
            elif freq == "Last 30 Days":
                count_df = full_df[full_df["Date"] >= today - datetime.timedelta(days=30)]
            else:
                count_df = full_df.copy()
            visits = count_df.groupby(["Manager Name", "Kitchen Name"]).size().reset_index(name="Visits")
            st.dataframe(visits, use_container_width=True)

# -------------------- SECTION: Roaster Entry --------------------
elif section == "Roaster Entry":
    st.subheader("📆 Submit Your Weekly Roaster")
    with st.form("roaster_form"):
        selected_manager = st.selectbox("Manager Name", manager_list)
        week_start = st.date_input("Week Starting (Monday)", value=datetime.date.today())
        days = [week_start + datetime.timedelta(days=i) for i in range(7)]
        entries = []
        for day in days:
            st.markdown(f"**{day.strftime('%A %d-%b')}**")
            kitchen = st.selectbox(f"Select Kitchen for {day.strftime('%A')}", [""] + kitchens, key=str(day))
            remark = st.text_input(f"Remarks for {day.strftime('%A')}", key=f"remark_{day}")
            if kitchen:
                entries.append([day.strftime('%Y-%m-%d'), selected_manager, kitchen, remark])
        submit_roaster = st.form_submit_button("Submit Roaster")
        if submit_roaster:
            for row in entries:
                roaster_sheet.append_row(row)
            st.success("✅ Roaster submitted successfully!")
