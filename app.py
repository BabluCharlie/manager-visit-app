import streamlit as st
import gspread
import datetime
import geocoder
import json
import requests
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image

# -------------------- CONFIG --------------------
st.set_page_config(page_title="HYBB Attendance System", layout="centered")

# -------------------- STYLING --------------------
st.markdown("""
    <style>
        body {
            background-color: #FFA500;
        }
        .title {
            font-size: 32px;
            color: #006400;
            font-weight: bold;
            text-align: center;
            margin-top: 10px;
        }
        .company {
            font-size: 18px;
            text-align: center;
            color: white;
            margin-bottom: 20px;
        }
    </style>
""", unsafe_allow_html=True)

# -------------------- LOGO --------------------
logo = Image.open("WhatsApp Image 2024-10-01 at 11.26.54 AM (1).jpeg")
st.image(logo, width=120)

st.markdown('<div class="title">HYBB Attendance System</div>', unsafe_allow_html=True)
st.markdown('<div class="company">Hygiene Bigbite Pvt Ltd</div>', unsafe_allow_html=True)

# -------------------- GOOGLE AUTH --------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(st.secrets["GOOGLE_SHEETS_CREDS"]), scope)
client = gspread.authorize(creds)
sheet = client.open("Manager Visit Tracker").sheet1

# -------------------- PUNCH FORM --------------------
manager_list = ["Ravi", "Sonia", "Ali", "Preeti", "Vikram", "Aarti", "Rohan", "Neha", "Karan", "Divya"]
kitchens = [
    "ANR01.BLR22", "BSK01.BLR19", "WFD01.BLR06", "MAR01.BLR05", "BTM01.BLR03",
    "IND01.BLR01", "HSR01.BLR02", "VDP01.CHN02", "MGP01.CHN01", "CMP01.CHN10",
    "KLN01.BLR09", "TKR01.BLR29", "CRN01.BLR17", "SKN01.BLR07", "HNR01.BLR16",
    "RTN01.BLR23", "YLK01.BLR15", "NBR01.BLR21", "PGD01.CHN06", "PRR01.CHN04",
    "FZT01.BLR20", "ECT01.BLR24", "SJP01.BLR08", "KPR01.BLR41", "BSN01.BLR40",
    "VNR01.BLR18", "SDP01.BLR34", "TCP01.BLR27"
]

st.subheader("Punch In / Punch Out")
manager = st.selectbox("Select Manager", manager_list)
kitchen = st.selectbox("Select Kitchen", kitchens)
action = st.radio("Action", ["Punch In", "Punch Out"])
photo = st.file_uploader("Upload Selfie (Optional)", type=["jpg", "jpeg", "png"])

if st.button("Submit Punch"):
    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    g = geocoder.ip('me')
    lat, lon = g.latlng if g.latlng else ("N/A", "N/A")

    # Check for duplicate punch
    records = sheet.get_all_records()
    duplicate = any(
        row["Date"] == today_str and
        row["Manager Name"] == manager and
        row["Kitchen Name"] == kitchen and
        row["Action"] == action
        for row in records
    )

    if duplicate:
        st.warning("⚠️ You've already submitted this punch today.")
    else:
        selfie_url = ""
        if photo:
            # Upload photo to Google Drive
            upload_url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
            headers = {"Authorization": f"Bearer {creds.get_access_token().access_token}"}
            metadata = {
                "name": f"{manager}_{today_str}_{time_str}.jpg",
                "parents": ["https://drive.google.com/drive/folders/1geeQPitCovvG5_2MlNOdvTOfupHu2G78"]  # TODO: Replace with actual Drive folder ID
            }
            files = {
                'data': ('metadata', json.dumps(metadata), 'application/json'),
                'file': photo.getvalue()
            }
            response = requests.post(upload_url, headers=headers, files=files)
            if response.status_code == 200:
                file_id = response.json()["id"]
                selfie_url = f"https://drive.google.com/uc?id={file_id}"

        # Append data to Sheet
        data = [today_str, time_str, manager, kitchen, action, lat, lon, selfie_url]
        sheet.append_row(data)
        st.success("✅ Punch recorded successfully!")
