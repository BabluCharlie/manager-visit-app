"""
HYBB Attendance System – Streamlit App
Updated: 2025‑07‑16 – fixes invisible dropdown value & captures per‑user geolocation

Features
--------
▪ Punch‑in / punch‑out with selfie upload to Google Drive
▪ Weekly roaster submission
▪ Duplicate‑punch safeguard (same manager + kitchen + action + date)
▪ Dashboards: Roaster View, Attendance, Visit Summary
▪ Accurate client‑side latitude/longitude using streamlit_js_eval
▪ Polished orange theme + white select boxes (selected value always visible)

Prerequisites
-------------
```bash
pip install streamlit streamlit_js_eval gspread oauth2client pandas requests pytz
```
A Google service‑account JSON key is stored in Streamlit secrets as **GOOGLE_SHEETS_CREDS**.
"""

import streamlit as st
from streamlit.components.v1 import html
try:
    # Tiny helper that runs JS in the browser → returns a dict with coords
    from streamlit_js_eval import get_geolocation  # pip install streamlit_js_eval
except ModuleNotFoundError:
    st.warning("⚠️ Missing dependency 'streamlit_js_eval' → `pip install streamlit_js_eval` for per‑user location")
    get_geolocation = None

import gspread
import datetime
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

/* Error border style */
div[data-baseweb="select"] > div {
    border: 1px solid #ccc !important;
    border-radius: 10px !important;
}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="title" style="font-size:2.2rem;font-weight:700;margin-bottom:0.25em;">HYBB Attendance System</div>', unsafe_allow_html=True)
st.markdown('<div class="company" style="font-size:1.3rem;font-weight:600;margin-bottom:1.5em;">Hygiene Bigbite Pvt Ltd</div>', unsafe_allow_html=True)

# -------------------- GEOLOCATION (client‑side) --------------------
#   Uses streamlit_js_eval to run JS -> navigator.geolocation
if "user_lat" not in st.session_state:
    st.session_state["user_lat"] = None
    st.session_state["user_lon"] = None

if get_geolocation and (st.session_state["user_lat"] is None or st.session_state["user_lon"] is None):
    try:
        loc = get_geolocation()  # safe browser context
        if loc and loc.get("coords"):
            st.session_state["user_lat"] = loc["coords"].get("latitude")
            st.session_state["user_lon"] = loc["coords"].get("longitude")
    except Exception as e:
        st.warning(f"⚠️ Unable to get browser location: {e}")


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
    roaster_sheet = client.open("Manager Visit Tracker").add_worksheet("Roaster", rows=1000, cols=5)
    roaster_sheet.insert_row(["Date", "Manager", "Kitchen", "Login Time", "Remarks"], 1)

# Load into DataFrame safely
try:
    roaster_df = pd.DataFrame(roaster_sheet.get_all_records())
    if not roaster_df.empty and "Date" in roaster_df.columns:
        roaster_df["Date"] = pd.to_datetime(roaster_df["Date"], errors="coerce").dt.date
except Exception:
    roaster_df = pd.DataFrame()
    st.warning("⚠️ Could not load roaster data.")

# -------------------- CONSTANTS --------------------
DRIVE_FOLDER_ID = "1i5SnIkpMPqtU1kSVVdYY4jQK1lwHbR9G"  # Shared‑drive folder for selfies
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
    "Test",
    "Test 2",
]

kitchens = [
    "ANR01.BLR22","BSK01.BLR19","WFD01.BLR06","MAR01.BLR05","BTM01.BLR03","IND01.BLR01",
    "HSR01.BLR02","VDP01.CHN02","MGP01.CHN01","CMP01.CHN10","KLN01.BLR09","TKR01.BLR29",
    "CRN01.BLR17","SKN01.BLR07","HNR01.BLR16","RTN01.BLR23","YLK01.BLR15","NBR01.BLR21",
    "PGD01.CHN06","PRR01.CHN04","FZT01.BLR20","ECT01.BLR24","SJP01.BLR08","KPR01.BLR41",
    "BSN01.BLR40","VNR01.BLR18","SDP01.BLR34","TCP01.BLR27","BOM01.BLR04","CK-Corp",
    "KOR01.BLR12","SKM01.CHN03","WFD02.BLR13","KDG01.BLR14","BMS01.BLR26", "BLD01.BLR25","Week Off","Comp-Off","Leave",
]

# -------------------- SUCCESS HELPERS --------------------

def punch_success():
    st.success("✅ Attendance recorded. Thank you!")


def roaster_success():
    if r_submit:
        roaster_sheet.append_row([str(r_date), r_manager, r_kitchen, str(r_login), r_remarks])
        st.success("✅ Roaster submitted successfully")
        reset_form()

# -------------------- LAYOUT --------------------
left_col, right_col = st.columns([2, 1])

# ------- LEFT COLUMN: Punch In/Out -------
with left_col:
    st.subheader("Punch In / Punch Out")

    with st.form("punch_form"):
        sel_manager = st.selectbox("Manager", manager_list)
        sel_kitchen = st.selectbox("Kitchen", [""] + kitchens)
        sel_action = st.radio("Action", ["Punch In", "Punch Out"], horizontal=True)
        photo = st.camera_input("Selfie (Required)")
        punch_submit = st.form_submit_button("Submit Punch")

    if punch_submit:
        # Validate mandatory fields
        if not sel_manager or not sel_kitchen or photo is None:
            st.warning("All fields & selfie required!")
            st.stop()

        now = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
        today_str, time_str = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

        # Location from session (set by browser JS)
        lat = st.session_state.get("user_lat") or "N/A"
        lon = st.session_state.get("user_lon") or "N/A"
        location_url = f"https://www.google.com/maps?q={lat},{lon}" if lat != "N/A" else "Location N/A"

        # Prevent duplicate punches (same manager/kitchen/action same day)
        if any(
            r.get("Date") == today_str and r.get("Manager Name") == sel_manager and r.get("Kitchen Name") == sel_kitchen and r.get("Action") == sel_action
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
            f"https://drive.google.com/file/d/{resp.json().get('id')}/view?usp=sharing" if resp.status_code == 200 else "UploadErr"
        )

        # Append punch row
        try:
            worksheet.append_row([
                today_str,
                time_str,
                sel_manager,
                sel_kitchen,
                sel_action,
                lat,
                lon,
                selfie_url,
                location_url,
            ])
            punch_success()
        except Exception as e:
            st.error("❌ Error submitting attendance. Please try again.")
            st.exception(e)
# ------- RIGHT COLUMN: Dashboards & Roaster -------
with right_col:
    tab = st.radio(
        "Dashboard",
        [
            "Roaster View",
            "Attendance",
            "Visit Summary",
            "Roaster Entry",
            "Daily Review",
            "Leave Request"
        ],
        format_func=lambda x: {
            "Roaster View": "📅 Roaster",
            "Attendance": "📋 Attendance",
            "Visit Summary": "📊 Visit Summary",
            "Roaster Entry": "📝 Roaster Entry",
            "Daily Review": "🧾 Daily Review",
            "Leave Request": "🛌 Leave Request"
        }.get(x, x),
    )

    st.write(f"🔍 Currently selected tab: {tab}")  # Debug line

    if tab == "Roaster Entry":
        st.subheader("📆 Submit Weekly Roaster")
        st.info("Roaster form goes here...")

    elif tab == "Roaster View":
        st.subheader("📅 Roaster View")
        st.info("Roaster view goes here...")

    elif tab == "Attendance":
        st.subheader("📋 Attendance")
        st.info("Attendance view goes here...")

    elif tab == "Visit Summary":
        st.subheader("📊 Visit Summary")
        st.info("Visit summary goes here...")

    elif tab == "Daily Review":
        st.subheader("🧾 Daily Review Submission")
        st.info("Daily review form goes here...")

    elif tab == "Leave Request":
        st.subheader("🛌 Leave Request Form")
        st.info("✅ Leave request tab is working!")  # TEMP: just check if it shows

    # ---- Roaster Entry ----
    if tab == "Roaster Entry":
        st.subheader("📆 Submit Weekly Roaster")
        with st.form("roaster_form"):
            selected_manager = st.selectbox("Manager Name", manager_list)
            next_monday = datetime.date.today() + datetime.timedelta(days=(7 - datetime.date.today().weekday()) % 7)
            week_start = st.date_input("Week Starting (Monday)", value=next_monday)
            days = [week_start + datetime.timedelta(days=i) for i in range(7)]
            entries = []
            time_choices = [(
                                    datetime.datetime.combine(datetime.date.today(),
                                                              datetime.time(7, 0)) + datetime.timedelta(minutes=30 * i)
                            ).time().strftime("%H:%M") for i in range(34)]
            for day in days:
                st.markdown(f"**{day.strftime('%A %d-%b')}**")
                kitchen = st.selectbox(f"Kitchen for {day.strftime('%A')}", kitchens, key=f"k_{day}")
                login_time = st.selectbox(f"Login Time for {day.strftime('%A')}", time_choices, key=f"t_{day}")
                remark = st.text_input(f"Remarks for {day.strftime('%A')}", key=f"rem_{day}")
                if kitchen:
                    entries.append([day.strftime("%Y-%m-%d"), selected_manager, kitchen, login_time, remark])
            submit_roaster = st.form_submit_button("Submit Roaster")
            if submit_roaster and entries:
                for row in entries:
                    roaster_sheet.append_row(row)
                st.success("✅ Roaster submitted successfully")

    # ---- Roaster View ----
    elif tab == "Roaster View":
        if roaster_df.empty:
            st.info("No roaster data.")
        else:
            mgr_filter = st.selectbox("Manager", ["All"] + sorted(roaster_df["Manager"].unique()))

            # Convert 'Date' column to datetime if not already
            roaster_df["Date"] = pd.to_datetime(roaster_df["Date"])

            # Extract week numbers
            week_numbers = sorted(roaster_df["Date"].dt.isocalendar().week.unique())
            week_filter = st.selectbox("Week Number", week_numbers)

            # Filter by manager
            temp = roaster_df.copy()
            if mgr_filter != "All":
                temp = temp[temp["Manager"] == mgr_filter]

            # Filter by week number
            temp["Week"] = temp["Date"].dt.isocalendar().week
            temp = temp[temp["Week"] == week_filter]

            # Optional: Sort by date
            temp = temp.sort_values("Date")

            st.dataframe(temp.drop(columns=["Week"]), use_container_width=True)

    # ---- Attendance ----
    elif tab == "Attendance":
        try:
            records = worksheet.get_all_records()
            full_df = pd.DataFrame(records)
            if not full_df.empty:
                full_df["Date"] = pd.to_datetime(full_df["Date"], errors="coerce").dt.date
        except Exception as e:
            full_df = pd.DataFrame()
            st.error("⚠️ Error loading attendance data. Please check your sheet structure or try again later.")
            st.exception(e)

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

    # ---- Visit Summary ----
    elif tab == "Visit Summary":
        st.subheader("📊 Visit vs Roaster Summary")

        try:
            # Load Visit Records from Sheet1
            visit_sheet = client.open("Manager Visit Tracker").worksheet("Sheet1")
            visit_records = visit_sheet.get_all_records()
            visit_df = pd.DataFrame(visit_records)

            # Load Roaster Records from Roaster
            roaster_sheet = client.open("Manager Visit Tracker").worksheet("Roaster")
            roaster_records = roaster_sheet.get_all_records()
            roaster_df = pd.DataFrame(roaster_records)

            # Convert Date columns
            visit_df["Date"] = pd.to_datetime(visit_df["Date"], errors="coerce").dt.date
            roaster_df["Date"] = pd.to_datetime(roaster_df["Date"], errors="coerce").dt.date

        except Exception as e:
            st.error(f"Error loading sheets: {e}")
            st.stop()

        # Frequency filter
        freq = st.radio("Frequency", ["Last 7 Days", "Last 30 Days", "All Time"])
        today = datetime.date.today()
        if freq == "Last 7 Days":
            visit_df = visit_df[visit_df["Date"] >= today - datetime.timedelta(days=7)]
            roaster_df = roaster_df[roaster_df["Date"] >= today - datetime.timedelta(days=7)]
        elif freq == "Last 30 Days":
            visit_df = visit_df[visit_df["Date"] >= today - datetime.timedelta(days=30)]
            roaster_df = roaster_df[roaster_df["Date"] >= today - datetime.timedelta(days=30)]

        # Rename columns for consistency
        roaster_df.rename(columns={"Manager": "Manager Name", "Kitchen": "Scheduled Kitchen"}, inplace=True)
        visit_df.rename(columns={"Kitchen Name": "Visited Kitchen"}, inplace=True)

        # Merge by Manager + Date + Kitchen
        summary_df = pd.merge(
            roaster_df,
            visit_df[["Date", "Manager Name", "Visited Kitchen"]],
            left_on=["Date", "Manager Name", "Scheduled Kitchen"],
            right_on=["Date", "Manager Name", "Visited Kitchen"],
            how="left"
        )

        # Add match indicator
        summary_df["Visited?"] = summary_df["Visited Kitchen"].apply(lambda x: "Yes" if pd.notna(x) else "No")

        # Drop duplicate "Visited Kitchen" column (optional, can keep it too)
        summary_df = summary_df.drop(columns=["Visited Kitchen"])

        # Sort and show
        # Add Manager Name dropdown filter
        manager_list = ["All"] + sorted(summary_df["Manager Name"].dropna().unique())
        selected_manager = st.selectbox("Select Kitchen Manager", manager_list)

        # Toggle to show only missed visits
        missed_only = st.checkbox("🔍 Show Missed Visits Only")

        # Apply filters
        if selected_manager != "All":
            summary_df = summary_df[summary_df["Manager Name"] == selected_manager]

        if missed_only:
            summary_df = summary_df[summary_df["Visited?"] == "No"]

        # Sort and format date column
        summary_df = summary_df.sort_values(["Date", "Manager Name"])
        summary_df["Date"] = pd.to_datetime(summary_df["Date"], errors="coerce").dt.strftime("%Y-%m-%d")

        # Function to highlight missed visits in red
        def highlight_missed(row):
            return ['background-color: #f8d7da' if row["Visited?"] == "No" else '' for _ in row]


        # Apply styling
        styled_df = summary_df.style.apply(highlight_missed, axis=1)

        # Display styled dataframe
        st.dataframe(styled_df, use_container_width=True)

    # ---- Daily Review ----
    elif tab == "Daily Review":
        st.subheader("🧾 Daily Review Submission")

        with st.form("daily_review_form"):
            review_manager = st.selectbox("Manager Name", ["-- Select --"] + manager_list)
            review_kitchens = st.multiselect("Kitchen(s) Visited", kitchens)
            screenshot = st.file_uploader("Upload Screenshot (mandatory)", type=["jpg", "jpeg", "png"])
            review_submit = st.form_submit_button("Submit Review")

        if review_submit:
            if review_manager == "-- Select --":
                st.warning("⚠️ Please select a manager.")
            elif not review_kitchens:
                st.warning("⚠️ Please select at least one kitchen.")
            elif not screenshot:
                st.warning("⚠️ Screenshot upload is mandatory.")
            else:
                today = datetime.date.today().strftime("%Y-%m-%d")
                now_time = datetime.datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%H:%M:%S")

                upload_resp = requests.post(
                    "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true",
                    headers={"Authorization": f"Bearer {creds.get_access_token().access_token}"},
                    files={
                        "data": (
                            "metadata",
                            json.dumps({
                                "name": f"{review_manager}_{today}_{now_time}_screenshot.jpg",
                                "parents": [DRIVE_FOLDER_ID]
                            }),
                            "application/json",
                        ),
                        "file": screenshot.read(),
                    },
                )

                screenshot_url = (
                    f"https://drive.google.com/file/d/{upload_resp.json().get('id')}/view?usp=sharing"
                    if upload_resp.status_code == 200 else "UploadErr"
                )

                try:
                    review_sheet = client.open("Manager Visit Tracker").worksheet("Daily Review")
                except gspread.exceptions.WorksheetNotFound:
                    review_sheet = client.open("Manager Visit Tracker").add_worksheet("Daily Review", rows=1000, cols=6)
                    review_sheet.insert_row(["Date", "Time", "Manager", "Kitchens", "Screenshot Link"], 1)

                review_sheet.append_row([
                    today,
                    now_time,
                    review_manager,
                    ", ".join(review_kitchens),
                    screenshot_url
                ])

                st.success("✅ Daily review submitted successfully.")

    # ----------------- Leave Request block starts OUTSIDE of Daily Review -------------------
    elif tab == "Leave Request":
        st.subheader("🛌 Leave Request Form")
        st.info("✅ Leave request tab is working!")

        with st.form("leave_form"):
            leave_manager = st.selectbox("Manager Name", ["-- Select --"] + manager_list)
            leave_type = st.selectbox("Leave Type", ["Casual Leave", "Sick Leave", "Week Off", "Comp-Off", "Other"])
            from_date = st.date_input("From Date", value=datetime.date.today())
            to_date = st.date_input("To Date", value=datetime.date.today())
            reason = st.text_area("Reason for Leave")
            doc_upload = st.file_uploader("Optional Document (PDF, JPG, PNG)", type=["pdf", "jpg", "jpeg", "png"])
            submit_leave = st.form_submit_button("Submit Leave Request")

        if submit_leave:
            if leave_manager == "-- Select --":
                st.warning("⚠️ Please select a manager.")
            elif not reason.strip():
                st.warning("⚠️ Reason for leave is required.")
            elif from_date > to_date:
                st.warning("⚠️ From Date cannot be after To Date.")
            else:
                doc_url = "N/A"
                if doc_upload:
                    now = datetime.datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%H:%M:%S")
                    upload_resp = requests.post(
                        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true",
                        headers={"Authorization": f"Bearer {creds.get_access_token().access_token}"},
                        files={
                            "data": (
                                "metadata",
                                json.dumps({
                                    "name": f"{leave_manager}_{from_date}_{now}_leave_doc",
                                    "parents": [DRIVE_FOLDER_ID]
                                }),
                                "application/json",
                            ),
                            "file": doc_upload.read(),
                        },
                    )
                    if upload_resp.status_code == 200:
                        doc_url = f"https://drive.google.com/file/d/{upload_resp.json().get('id')}/view?usp=sharing"

                try:
                    leave_sheet = client.open("Manager Visit Tracker").worksheet("Leave Requests")
                except gspread.exceptions.WorksheetNotFound:
                    leave_sheet = client.open("Manager Visit Tracker").add_worksheet("Leave Requests", rows=1000,
                                                                                     cols=8)
                    leave_sheet.insert_row([
                        "Submitted On", "Manager", "Leave Type", "From Date", "To Date", "Reason", "Document Link"
                    ], 1)

                leave_sheet.append_row([
                    datetime.date.today().strftime("%Y-%m-%d"),
                    leave_manager,
                    leave_type,
                    from_date.strftime("%Y-%m-%d"),
                    to_date.strftime("%Y-%m-%d"),
                    reason,
                    doc_url
                ])

                st.success("✅ Leave request submitted successfully.")
