"""
HYBB Attendance System – full updated script
(2025‑07‑16)
"""

# -------------------- IMPORTS --------------------
import streamlit as st
import gspread
import datetime
import json
import requests
import pandas as pd
import pytz
import geocoder
from oauth2client.service_account import ServiceAccountCredentials
from streamlit_js_eval import streamlit_js_eval
import smtplib
from email.message import EmailMessage
from twilio.rest import Client

# -------------------- CONFIG --------------------
st.set_page_config(page_title="HYBB Attendance System", layout="wide")

# -------------------- STYLING --------------------
st.markdown(
    """
<style>
/* Global theme */
body, .stApp, section.main { background-color:#FFA500 !important; }

/* Titles */
.title   { font-size:32px; color:#006400; font-weight:bold; text-align:center; margin-top:10px; }
.company { font-size:18px; color:white; text-align:center; margin-bottom:20px; font-weight:bold; }

/* Inputs */
.stTextInput > div > input,
.stSelectbox  > div > div,
.stRadio > div, .stCameraInput,
.stDataFrame,  .stForm,
.stButton button {
    background:#fff !important; color:#000 !important;
    border-radius:10px; padding:8px;
    box-shadow:0 2px 4px rgba(0,0,0,.1);
}

/* BaseWeb select dropdown fix */
div[data-baseweb="select"]{background:#fff !important;border-radius:10px !important;color:#000 !important;font-weight:600 !important;}
div[data-baseweb="select"] *{background:#fff !important;color:#000 !important;}
div[data-baseweb="select"] [role="option"]:hover{background:#f0f0f0 !important;}
div[data-baseweb="select"] [aria-selected="true"]{background:#d0f0c0 !important;}

/* Primary buttons */
button[kind="primary"]{background:#006400 !important;color:#fff !important;}
button[kind="primary"]:hover{background:#228B22 !important;transition:.3s ease;}

/* Mobile tweaks */
@media(max-width:768px){
    .stApp{padding:10px !important;}
    button,input,select,textarea{font-size:16px !important;}
    .stButton button{width:100% !important;}
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

# -------------------- ROASTER SHEET --------------------
try:
    roaster_sheet = client.open("Manager Visit Tracker").worksheet("Roaster")
except gspread.exceptions.WorksheetNotFound:
    roaster_sheet = client.open("Manager Visit Tracker").add_worksheet(
        "Roaster", rows=1000, cols=5
    )
    roaster_sheet.insert_row(
        ["Date", "Manager", "Kitchen", "Login Time", "Remarks"], 1
    )

try:
    roaster_df = pd.DataFrame(roaster_sheet.get_all_records())
    if not roaster_df.empty and "Date" in roaster_df.columns:
        roaster_df["Date"] = pd.to_datetime(roaster_df["Date"], errors="coerce").dt.date
except Exception:
    roaster_df = pd.DataFrame()
    st.warning("⚠️ Could not load roaster data.")

# -------------------- CONSTANTS --------------------
DRIVE_FOLDER_ID = "1i5SnIkpMPqtU1kSVVdYY4jQK1lwHbR9G"
manager_list = [
    "", "Ayub Sait", "Rakesh Babu", "John Joseph", "Naveen Kumar M",
    "Sangeetha RM", "Joy Matabar", "Sonu Kumar", "Samsudeen",
    "Tauseef", "Bablu C", "Umesh M", "Selva Kumar", "Srividya",
]
kitchens = [
    "ANR01.BLR22","BSK01.BLR19","WFD01.BLR06","MAR01.BLR05","BTM01.BLR03",
    "IND01.BLR01","HSR01.BLR02","VDP01.CHN02","MGP01.CHN01","CMP01.CHN10",
    "KLN01.BLR09","TKR01.BLR29","CRN01.BLR17","SKN01.BLR07","HNR01.BLR16",
    "RTN01.BLR23","YLK01.BLR15","NBR01.BLR21","PGD01.CHN06","PRR01.CHN04",
    "FZT01.BLR20","ECT01.BLR24","SJP01.BLR08","KPR01.BLR41","BSN01.BLR40",
    "VNR01.BLR18","SDP01.BLR34","TCP01.BLR27","BOM01.BLR04","CK-Corp",
    "KOR01.BLR12","SKM01.CHN03","WFD02.BLR13","KDG01.BLR14",
    "Week Off","Comp-Off","Leave",
]

# -------------------- HELPER: Confirmation Email --------------------
def send_confirmation_email(manager, kitchen, action, date, time, selfie_url):
    if "EMAIL_USER" not in st.secrets:  # skip if not configured
        return
    msg = EmailMessage()
    msg["Subject"] = f"[HYBB] {action} confirmation"
    msg["From"] = st.secrets["EMAIL_USER"]
    msg["To"] = st.secrets.get("EMAIL_TO", st.secrets["EMAIL_USER"])
    msg.set_content(
        f"""Hi {manager},

Your {action} has been recorded.

Kitchen : {kitchen}
Date    : {date}
Time    : {time}
Selfie  : {selfie_url}

Regards,
HYBB Attendance System"""
    )
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(st.secrets["EMAIL_USER"], st.secrets["EMAIL_PASS"])
            smtp.send_message(msg)
    except Exception as e:
        st.error(f"Email failed: {e}")

# -------------------- HELPER: WhatsApp --------------------
def send_whatsapp(manager, kitchen, action, selfie_url):
    if "TWILIO_SID" not in st.secrets:
        return
    try:
        tw = Client(st.secrets["TWILIO_SID"], st.secrets["TWILIO_TOKEN"])
        tw.messages.create(
            from_="whatsapp:+14155238886",
            to=f"whatsapp:{st.secrets['WHATSAPP_TO']}",
            body=f"Hi {manager}, your {action} at {kitchen} is recorded. 📸 {selfie_url}",
        )
    except Exception as e:
        st.error(f"WhatsApp failed: {e}")

# -------------------- SUCCESS MESSAGE --------------------
def punch_success():
    st.success("✅ Attendance recorded. Thank you!")
    # no experimental_rerun()

# -------------------- MOBILE‑FIRST LAYOUT --------------------
# Single container (stacks naturally on phones)
st.markdown("## 👤 Punch In / Punch Out")
with st.form("punch_form"):
    sel_manager = st.selectbox("Manager", manager_list)
    sel_kitchen = st.selectbox("Kitchen", [""] + kitchens)
    sel_action  = st.radio("Action", ["Punch In", "Punch Out"], horizontal=True)
    photo       = st.camera_input("Selfie (Required)")

    # ---- Fetch GPS via browser; fallback to IP ----
    coords = streamlit_js_eval(
        js_expressions="""
            navigator.geolocation.getCurrentPosition(
              (pos)=>({lat:pos.coords.latitude, lon:pos.coords.longitude}),
              (err)=>({lat:null, lon:null})
            )
        """,
        key="get_geo"
    )
    lat = coords["lat"] if coords and coords["lat"] is not None else None
    lon = coords["lon"] if coords and coords["lon"] is not None else None
    if lat is None:
        ip_geo = geocoder.ipinfo("me")
        lat, lon = (ip_geo.latlng if ip_geo.latlng else (None, None))

    punch_submit = st.form_submit_button("📍 Submit")

# -------------------- HANDLE SUBMIT --------------------
if punch_submit:
    if not sel_manager or not sel_kitchen or photo is None:
        st.warning("All fields & selfie required!")
        st.stop()

    now          = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
    today_str    = now.strftime("%Y-%m-%d")
    time_str     = now.strftime("%H:%M:%S")
    location_url = f"https://www.google.com/maps?q={lat},{lon}" if lat else "Location N/A"

    # Prevent duplicate punch same day
    if any(
        r.get("Date") == today_str and
        r.get("Manager Name") == sel_manager and
        r.get("Kitchen Name") == sel_kitchen and
        r.get("Action") == sel_action
        for r in worksheet.get_all_records()
    ):
        st.warning("Duplicate punch today.")
        st.stop()

    # ---- Upload selfie to Drive ----
    drive_resp = requests.post(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true",
        headers={"Authorization": f"Bearer {creds.get_access_token().access_token}"},
        files={
            "data": (
                "metadata",
                json.dumps({
                    "name": f"{sel_manager}_{today_str}_{time_str}.jpg",
                    "parents": [DRIVE_FOLDER_ID],
                }),
                "application/json",
            ),
            "file": photo.getvalue(),
        },
    )
    selfie_url = (
        f"https://drive.google.com/file/d/{drive_resp.json().get('id')}/view?usp=sharing"
        if drive_resp.status_code == 200 else "UploadErr"
    )

    # ---- Append row ----
    worksheet.append_row([
        today_str, time_str, sel_manager, sel_kitchen, sel_action,
        lat or "N/A", lon or "N/A", selfie_url, location_url,
    ])

    # ---- Send confirmations (optional) ----
    send_confirmation_email(sel_manager, sel_kitchen, sel_action,
                            today_str, time_str, selfie_url)
    send_whatsapp(sel_manager, sel_kitchen, sel_action, selfie_url)

    punch_success()

# -------------------- DASHBOARD / ROASTER --------------------
st.divider()
tab = st.radio("Dashboard",
    ["Roaster View", "Attendance", "Visit Summary", "Roaster Entry"],
    horizontal=True)

# ---- Roaster Entry ----
if tab == "Roaster Entry":
    st.subheader("📝 Submit Weekly Roaster")
    with st.form("roaster_form"):
        selected_manager = st.selectbox("Manager Name", manager_list, key="ro_mgr")
        next_monday = datetime.date.today() + datetime.timedelta(
            days=(7 - datetime.date.today().weekday()) % 7
        )
        week_start = st.date_input("Week Starting (Monday)", value=next_monday)
        days = [week_start + datetime.timedelta(days=i) for i in range(7)]
        entries = []
        times = [
            (datetime.datetime.combine(datetime.date.today(), datetime.time(7,0))
             + datetime.timedelta(minutes=30*i)).time().strftime("%H:%M")
            for i in range(34)
        ]
        for day in days:
            st.markdown(f"**{day.strftime('%A %d-%b')}**")
            k  = st.selectbox(f"Kitchen", kitchens, key=f"k_{day}")
            lt = st.selectbox(f"Login Time", times, key=f"t_{day}")
            rm = st.text_input(f"Remarks", key=f"r_{day}")
            if k: entries.append([day.strftime("%Y-%m-%d"), selected_manager, k, lt, rm])
        if st.form_submit_button("Submit Roaster"):
            for row in entries:
                roaster_sheet.append_row(row)
            st.success("✅ Roaster saved!")

# ---- Roaster View ----
elif tab == "Roaster View":
    if roaster_df.empty:
        st.info("No roaster data.")
    else:
        mgr = st.selectbox("Manager", ["All"]+sorted(roaster_df["Manager"].unique()))
        dt  = st.date_input("Date", value=datetime.date.today(), key="rv_date")
        temp = roaster_df.copy()
        if mgr != "All": temp = temp[temp["Manager"] == mgr]
        temp = temp[temp["Date"] == dt]
        st.dataframe(temp, use_container_width=True)

# ---- Attendance ----
elif tab == "Attendance":
    df = pd.DataFrame(worksheet.get_all_records())
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
    if df.empty:
        st.info("No attendance data.")
    else:
        d  = st.date_input("Date", value=datetime.date.today(), key="att_date")
        vf = df[df["Date"] == d]
        if vf.empty:
            st.info("No attendance records.")
        else:
            if not roaster_df.empty:
                roster_today = roaster_df[roaster_df["Date"] == d][["Manager", "Kitchen"]]
                vf["key"] = vf["Manager Name"]+"|"+vf["Kitchen Name"]
                roster_today["key"] = roster_today["Manager"]+"|"+roster_today["Kitchen"]
                vf["Mismatch"] = ~vf["key"].isin(roster_today["key"])
                vf.drop(columns=["key"], inplace=True)
            st.dataframe(vf, use_container_width=True)

# ---- Visit Summary ----
elif tab == "Visit Summary":
    df = pd.DataFrame(worksheet.get_all_records())
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.date
    if df.empty:
        st.info("No visits yet.")
    else:
        freq = st.radio("Frequency", ["Last 7 Days", "Last 30 Days", "All Time"],
                        horizontal=True, key="vs_freq")
        today = datetime.date.today()
        if freq == "Last 7 Days":
            df_f = df[df["Date"] >= today - datetime.timedelta(days=7)]
        elif freq == "Last 30 Days":
            df_f = df[df["Date"] >= today - datetime.timedelta(days=30)]
        else:
            df_f = df
        visits = df_f.groupby(["Manager Name","Kitchen Name"]).size().reset_index(name="Visits")
        st.dataframe(visits, use_container_width=True)
