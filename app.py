"""
HYBB Attendance System – updated Streamlit script
(2025‑07‑14) – Fixes invisible dropdown selected value by refining CSS
"""

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
/* Main background and text */
body, .stApp, section.main {
    background-color: #FFA500 !important;
    color: black !important;
}

/* Selectbox (Streamlit uses baseweb Select) */
div[data-baseweb="select"] {
    background-color: white !important;
    border-radius: 10px !important;
    color: black !important;
    font-weight: 600 !important;
}

div[data-baseweb="select"] * {
    color: black !important;
    background-color: white !important;
}

/* Force visibility of selected value */
div[data-baseweb="select"] div[class*="SingleValue"] {
    color: black !important;
    font-weight: 600 !important;
}

/* Options dropdown items */
div[data-baseweb="select"] [role="option"] {
    background-color: white !important;
    color: black !important;
    font-weight: 500;
}

/* Hovered option */
div[data-baseweb="select"] [role="option"]:hover {
    background-color: #f0f0f0 !important;
    color: black !important;
}

/* Selected item */
div[data-baseweb="select"] [aria-selected="true"] {
    background-color: #d0f0c0 !important;
    color: black !important;
}

/* Error border style (red border you see) */
div[data-baseweb="select"] > div {
    border: 1px solid #ccc !important;
    border-radius: 10px !important;
}
</style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="title">HYBB Attendance System</div>', unsafe_allow_html=True)
st.markdown('<div class="company">Hygiene Bigbite Pvt Ltd</div>', unsafe_allow_html=True)

# Rest of your script remains unchanged from the previously provided version...
# ⚠️ To save space here, the logic blocks for Google Sheets connection,
# punch in/out form, selfie upload, roaster, attendance, and summary
# all remain the same and should follow here.

# If you'd like me to paste the entire rest of the code again with this fix,
# just let me know and I'll include it inline.

# -------------------- SUCCESS FUNCTIONS --------------------

def punch_success():
    st.success("✅ Attendance has been successfully recorded. Thank you for visiting the kitchen!")
    # Removed rerun to prevent crash


def roaster_success():
    st.success("✅ Roaster submitted successfully. Your schedule has been saved. Thank you!")
    st.experimental_rerun()

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

# -------------------- ROASTER SHEET --------------------
try:
    roaster_sheet = client.open("Manager Visit Tracker").worksheet("Roaster")
except gspread.exceptions.WorksheetNotFound:
    roaster_sheet = client.open("Manager Visit Tracker").add_worksheet(
        "Roaster", rows=1000, cols=5
    )
    roaster_sheet.insert_row([
        "Date",
        "Manager",
        "Kitchen",
        "Login Time",
        "Remarks",
    ], 1)

# Load roaster dataframe safely
try:
    roaster_df = pd.DataFrame(roaster_sheet.get_all_records())
    if not roaster_df.empty and "Date" in roaster_df.columns:
        roaster_df["Date"] = pd.to_datetime(
            roaster_df["Date"], errors="coerce"
        ).dt.date
except Exception:
    roaster_df = pd.DataFrame()
    st.warning("⚠️ Could not load roaster data.")

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
    "Week Off",
    "Comp-Off",
    "Leave",
]

# -------------------- LAYOUT --------------------
left_col, right_col = st.columns([2, 1])

# ------- LEFT COLUMN: Punch In/Out -------
with left_col:
    st.subheader("Punch In / Punch Out")

    with st.form("punch_form"):
        sel_manager = st.selectbox("Manager", manager_list)
        sel_kitchen = st.selectbox("Kitchen", [""] + kitchens)
        sel_action = st.radio("Action", ["Punch In", "Punch Out"])
        photo = st.camera_input("Selfie (Required)")

        # --- NEW ► precise GPS via browser ---
        coords = streamlit_js_eval(
            js_expressions="""
                navigator.geolocation.getCurrentPosition(
                  (pos)=>({lat:pos.coords.latitude, lon:pos.coords.longitude}),
                  (err)=>({lat:null, lon:null})
                )
            """,
            key="get_geo"
        )
        # --------------------------------------

        punch_submit = st.form_submit_button("Submit Punch")
    if punch_submit:
        if not sel_manager or not sel_kitchen or photo is None:
            st.warning("All fields & selfie required!")
            st.stop()

        now = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
        today_str, time_str = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

        # Prefer GPS, fall back to IP
        lat = coords["lat"] if coords and coords["lat"] is not None else None
        lon = coords["lon"] if coords and coords["lon"] is not None else None
        if lat is None:  # no GPS (user blocked or desktop w/o sensor)
            g = geocoder.ipinfo("me")
            lat, lon = g.latlng if g.latlng else (None, None)

        lat = lat if lat is not None else "N/A"
        lon = lon if lon is not None else "N/A"
        location_url = (
            f"https://www.google.com/maps?q={lat},{lon}" if lat != "N/A" else "Location N/A"
        )

        # Prevent duplicate punches (same manager/kitchen/action same day)
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
                    json.dumps(
                        {
                            "name": f"{sel_manager}_{today_str}_{time_str}.jpg",
                            "parents": [DRIVE_FOLDER_ID],
                        }
                    ),
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

        # Append punch row
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
        punch_success()

# ------- RIGHT COLUMN: Dashboard & Roaster -------
with right_col:
    tab = st.radio(
        "Dashboard",
        ["Roaster View", "Attendance", "Visit Summary", "Roaster Entry"],
        format_func=lambda x: (
            "📅 Roaster"
            if x == "Roaster View"
            else (
                "📋 Attendance"
                if x == "Attendance"
                else ("📊 Visit Summary" if x == "Visit Summary" else "📝 Roaster Entry")
            )
        ),
    )

    # ---- Roaster Entry ----
    if tab == "Roaster Entry":
        st.subheader("📆 Submit Weekly Roaster")
        with st.form("roaster_form"):
            selected_manager = st.selectbox("Manager Name", manager_list)
            next_monday = datetime.date.today() + datetime.timedelta(
                days=(7 - datetime.date.today().weekday()) % 7
            )
            week_start = st.date_input("Week Starting (Monday)", value=next_monday)
            days = [week_start + datetime.timedelta(days=i) for i in range(7)]
            entries = []
            time_choices = [
                (
                    datetime.datetime.combine(
                        datetime.date.today(), datetime.time(7, 0)
                    )
                    + datetime.timedelta(minutes=30 * i)
                )
                .time()
                .strftime("%H:%M")
                for i in range(34)
            ]
            for day in days:
                st.markdown(f"**{day.strftime('%A %d-%b')}**")
                kitchen = st.selectbox(
                    f"Kitchen for {day.strftime('%A')}", kitchens, key=f"k_{day}"
                )
                login_time = st.selectbox(
                    f"Login Time for {day.strftime('%A')}", time_choices, key=f"t_{day}"
                )
                remark = st.text_input(
                    f"Remarks for {day.strftime('%A')}", key=f"rem_{day}"
                )
                if kitchen:
                    entries.append(
                        [day.strftime("%Y-%m-%d"), selected_manager, kitchen, login_time, remark]
                    )
            submit_roaster = st.form_submit_button("Submit Roaster")
            if submit_roaster:
                for row in entries:
                    roaster_sheet.append_row(row)
                roaster_success()

    # ---- Roaster View ----
    elif tab == "Roaster View":
        if roaster_df.empty:
            st.info("No roaster data.")
        else:
            mgr_filter = st.selectbox(
                "Manager", ["All"] + sorted(roaster_df["Manager"].unique())
            )
            date_filter = st.date_input("Date", value=datetime.date.today())
            temp = roaster_df.copy()
            if mgr_filter != "All":
                temp = temp[temp["Manager"] == mgr_filter]
            temp = temp[temp["Date"] == date_filter]
            st.dataframe(temp, use_container_width=True)

    # ---- Attendance ----
    elif tab == "Attendance":
        records = worksheet.get_all_records()
        full_df = pd.DataFrame(records)
        if not full_df.empty:
            full_df["Date"] = pd.to_datetime(full_df["Date"], errors="coerce").dt.date

        if full_df.empty:
            st.info("No attendance data.")
        else:
            sel_date = st.date_input("Date", value=datetime.date.today())
            view_df = full_df[full_df["Date"] == sel_date]

            if view_df.empty:
                st.info("No attendance records for this date.")
            else:
                if not roaster_df.empty:
                    roster_today = roaster_df[roaster_df["Date"] == sel_date][
                        ["Manager", "Kitchen"]
                    ]
                    view_df["key"] = (
                        view_df["Manager Name"] + "|" + view_df["Kitchen Name"]
                    )
                    roster_today["key"] = roster_today["Manager"] + "|" + roster_today[
                        "Kitchen"
                    ]
                    view_df["Mismatch"] = ~view_df["key"].isin(roster_today["key"])
                    view_df = view_df.drop(columns=["key"])
                st.dataframe(view_df, use_container_width=True)

    # ---- Visit Summary ----
    elif tab == "Visit Summary":
        records = worksheet.get_all_records()
        full_df = pd.DataFrame(records)
        if not full_df.empty:
            full_df["Date"] = pd.to_datetime(full_df["Date"], errors="coerce").dt.date
        if full_df.empty:
            st.info("No visits yet.")
        else:
            freq = st.radio("Frequency", ["Last 7 Days", "Last 30 Days", "All Time"])
            today = datetime.date.today()
            if freq == "Last 7 Days":
                df_f = full_df[full_df["Date"] >= today - datetime.timedelta(days=7)]
            elif freq == "Last 30 Days":
                df_f = full_df[full_df["Date"] >= today - datetime.timedelta(days=30)]
            else:
                df_f = full_df.copy()
            visits = (
                df_f.groupby(["Manager Name", "Kitchen Name"]).size().reset_index(name="Visits")
            )
            st.dataframe(visits, use_container_width=True)
