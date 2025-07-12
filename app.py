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
st.set_page_config(page_title="HYBB Attendance System", layout="centered")

# -------------------- STYLING --------------------
st.markdown("""
    <style>
        body {background-color: #FFA500;}
        .title {font-size: 32px; color: #006400; font-weight: bold; text-align: center; margin-top: 10px;}
        .company {font-size: 18px; text-align: center; color: white; margin-bottom: 20px;}
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">HYBB Attendance System</div>', unsafe_allow_html=True)
st.markdown('<div class="company">Hygiene Bigbite Pvt Ltd</div>', unsafe_allow_html=True)

# -------------------- GOOGLE AUTH --------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(st.secrets["GOOGLE_SHEETS_CREDS"]), scope)
client = gspread.authorize(creds)
worksheet = client.open("Manager Visit Tracker").sheet1

# -------------------- CONSTANTS --------------------
DRIVE_FOLDER_ID = "1i5SnIkpMPqtU1kSVVdYY4jQK1lwHbR9G"
SHARED_DRIVE_ID = ""

# -------------------- HEADER CHECK --------------------
expected_headers = ["Date", "Time", "Manager Name", "Kitchen Name", "Action", "Latitude", "Longitude", "Selfie URL", "Location Link"]
current_headers = worksheet.row_values(1)
if current_headers != expected_headers:
    if len(current_headers) == 0:
        worksheet.insert_row(expected_headers, 1)
    else:
        worksheet.update("A1", [expected_headers])

# -------------------- DASHBOARD --------------------
st.subheader("📊 Dashboard Summary")
records = worksheet.get_all_records()
df = pd.DataFrame(records)

if not df.empty:
    df["Date"] = pd.to_datetime(df["Date"], errors='coerce')
    df = df.dropna(subset=["Date"])
    df["Date"] = df["Date"].dt.date

    min_date = df["Date"].min()
    max_date = df["Date"].max()
    selected_date = st.date_input("Select a date", value=max_date, min_value=min_date, max_value=max_date)

    filtered_df = df[df["Date"] == selected_date]
    st.dataframe(filtered_df)

    punch_summary = filtered_df.groupby(["Manager Name", "Kitchen Name", "Action"]).size().reset_index(name='Count')
    st.markdown("### Summary")
    st.dataframe(punch_summary)

# -------------------- PUNCH FORM --------------------
st.subheader("Punch In / Punch Out")
manager_list = ["", "Ayub Sait", "Rakesh Babu", "John Joseph", "Naveen Kumar M", "Sangeetha RM", "Joy Matabar", "Sonu Kumar", "Samsudeen", "Tauseef", "Bablu C", "Umesh M"]
kitchens = ["", "ANR01.BLR22", "BSK01.BLR19", "WFD01.BLR06", "MAR01.BLR05", "BTM01.BLR03", "IND01.BLR01", "HSR01.BLR02", "VDP01.CHN02", "MGP01.CHN01", "CMP01.CHN10", "KLN01.BLR09", "TKR01.BLR29", "CRN01.BLR17", "SKN01.BLR07", "HNR01.BLR16", "RTN01.BLR23", "YLK01.BLR15", "NBR01.BLR21", "PGD01.CHN06", "PRR01.CHN04", "FZT01.BLR20", "ECT01.BLR24", "SJP01.BLR08", "KPR01.BLR41", "BSN01.BLR40", "VNR01.BLR18", "SDP01.BLR34", "TCP01.BLR27", "BOM01.BLR04", "CK-Corp"]

with st.form("punch_form"):
    manager = st.selectbox("Select Manager", manager_list, index=0, key="manager")
    kitchen = st.selectbox("Select Kitchen", kitchens, index=0, key="kitchen")
    action = st.radio("Action", ["Punch In", "Punch Out"], key="action")
    photo = st.camera_input("Take a Selfie (Required)", key="selfie")
    submitted = st.form_submit_button("Submit Punch")

if submitted:
    if not manager or not kitchen:
        st.warning("⚠️ Please select both Manager and Kitchen before submitting.")
        st.stop()
    if not photo:
        st.error("📸 Please take a selfie before submitting.")
        st.stop()

    indian_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
    today_str = indian_time.strftime("%Y-%m-%d")
    time_str = indian_time.strftime("%H:%M:%S")

    g = geocoder.ipinfo('me')
    lat, lon = g.latlng if g.latlng else ("N/A", "N/A")
    location_url = f"https://www.google.com/maps?q={lat},{lon}" if lat != "N/A" else "Location not available"

    if any(r.get("Date") == today_str and r.get("Manager Name") == manager and r.get("Kitchen Name") == kitchen and r.get("Action") == action for r in worksheet.get_all_records()):
        st.warning("⚠️ You've already submitted this punch today.")
        st.stop()

    selfie_url = ""
    upload_url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true"
    headers = {"Authorization": f"Bearer {creds.get_access_token().access_token}"}
    metadata = {
        "name": f"{manager}_{today_str}_{time_str}.jpg",
        "parents": [DRIVE_FOLDER_ID]
    }
    if SHARED_DRIVE_ID:
        metadata["driveId"] = SHARED_DRIVE_ID
    files = {
        'data': ('metadata', json.dumps(metadata), 'application/json'),
        'file': photo.getvalue()
    }
    resp = requests.post(upload_url, headers=headers, files=files)
    if resp.status_code == 200:
        file_id = resp.json()["id"]
        selfie_url = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
    else:
        st.error("❌ Failed to upload selfie to Google Drive – please check folder ID & access.")
        st.text(f"Status code: {resp.status_code}\nResponse: {resp.text}")
        st.stop()

    worksheet.append_row([today_str, time_str, manager, kitchen, action, lat, lon, selfie_url, location_url])
    st.success("✅ Punch recorded successfully!")
    st.markdown(f"[📍 Location Map]({location_url})")
    st.markdown(f"[📸 View Selfie]({selfie_url})")
    st.experimental_rerun()
