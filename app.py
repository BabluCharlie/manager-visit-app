# =============================
# HYBB Attendance System – Streamlit App
# Last updated: 2025-07-30
# -----------------------------
# Features:
# ▪ Punch-in / punch-out with selfie upload to Google Drive
# ▪ Weekly roaster submission
# ▪ Duplicate-punch safeguard (same manager + kitchen + action + date)
# ▪ Dashboards: Roaster View, Attendance, Visit Summary
# ▪ Accurate client-side latitude/longitude using streamlit_js_eval
# ▪ Polished orange theme + white select boxes (selected value always visible)
#
# Prerequisites (install before running):
# pip install streamlit streamlit_js_eval gspread google-auth google-auth-httplib2 google-auth-oauthlib pandas requests pytz
# =============================

import streamlit as st

# Show a status label at the top of the app
st.caption("🟢 Last updated: 2025-07-30")


import streamlit as st
from streamlit.components.v1 import html
try:
    # Tiny helper that runs JS in the browser → returns a dict with coords
    from streamlit_js_eval import get_geolocation  # pip install streamlit_js_eval
except ModuleNotFoundError:
    st.warning("⚠️ Missing dependency 'streamlit_js_eval' → `pip install streamlit_js_eval` for per-user location")
    get_geolocation = None

import gspread
import datetime
import json
import requests
import pandas as pd
import pytz
import time
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession
from google.auth.exceptions import RefreshError

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
st.markdown('<div class="company" style="font-size:1.3rem;font-weight:600;margin-bottom:1.5em;">Hygiene Bigbite Pvt Ltd</div>', unsafe_allow_html=True)

# -------------------- GEOLOCATION (client-side) --------------------
# Uses streamlit_js_eval to run JS -> navigator.geolocation
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


# -------------------- GOOGLE AUTH (google-auth + AuthorizedSession) --------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_google_creds():
    """Load credentials from st.secrets and return a google Credentials object."""
    key_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDS"])
    creds = Credentials.from_service_account_info(key_dict, scopes=SCOPES)
    return creds

# Create creds, gspread client and authorized session (with retries on refresh errors)
try:
    creds = get_google_creds()
    client = gspread.authorize(creds)
    authed_session = AuthorizedSession(creds)
except Exception as e:
    st.error("❌ Google auth failed. Please check GOOGLE_SHEETS_CREDS in Streamlit secrets.")
    st.exception(e)
    st.stop()

# -------------------- RETRY HELPERS --------------------
def retry(func, *args, retries=3, delay=2, backoff=1.5, **kwargs):
    """Generic retry wrapper for API calls."""
    attempt = 0
    while attempt < retries:
        try:
            return func(*args, **kwargs)
        except RefreshError as re:
            # Credentials refresh problems — try to re-create creds once
            attempt += 1
            st.warning(f"Auth refresh error (attempt {attempt}/{retries}): {re}")
            try:
                # try to refresh credentials object
                new_creds = get_google_creds()
                # re-authorize client and session
                global client, authed_session, creds
                creds = new_creds
                client = gspread.authorize(creds)
                authed_session = AuthorizedSession(creds)
            except Exception as e2:
                st.warning(f"Re-create creds failed: {e2}")
            time.sleep(delay * (backoff ** attempt))
        except Exception as e:
            attempt += 1
            if attempt < retries:
                st.warning(f"API call failed (attempt {attempt}/{retries}): {e}. Retrying in {delay} seconds...")
                time.sleep(delay * (backoff ** attempt))
            else:
                st.error(f"API call failed after {retries} attempts: {e}")
                raise

# -------------------- SHEET UTILITIES (safe wrappers) --------------------
def safe_open(spreadsheet_name):
    return retry(client.open, spreadsheet_name)

def safe_worksheet(spreadsheet_name, worksheet_name, rows=1000, cols=20):
    """Open or create worksheet safely."""
    sh = safe_open(spreadsheet_name)
    try:
        ws = retry(sh.worksheet, worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        ws = retry(sh.add_worksheet, worksheet_name, rows=rows, cols=cols)
        # No header insert here to avoid overwriting existing workflows (do it where needed)
    return ws

def safe_get_all_records(ws):
    return retry(ws.get_all_records)

def safe_append_row(ws, row):
    return retry(ws.append_row, row)

# -------------------- INITIAL SHEET OBJECTS --------------------
try:
    worksheet = safe_open("Manager Visit Tracker").sheet1
except Exception as e:
    st.error("❌ Unable to open 'Manager Visit Tracker' spreadsheet.")
    st.exception(e)
    st.stop()

# -------------------- ROASTER SHEET --------------------
try:
    roaster_sheet = safe_open("Manager Visit Tracker").worksheet("Roaster")
except gspread.exceptions.WorksheetNotFound:
    roaster_sheet = safe_open("Manager Visit Tracker").add_worksheet("Roaster", rows=1000, cols=5)
    # safe_insert header
    try:
        retry(roaster_sheet.insert_row, ["Date", "Manager", "Kitchen", "Login Time", "Remarks"], 1)
    except Exception:
        pass

# Load into DataFrame safely
try:
    roaster_records = safe_get_all_records(roaster_sheet)
    roaster_df = pd.DataFrame(roaster_records)
    if not roaster_df.empty and "Date" in roaster_df.columns:
        roaster_df["Date"] = pd.to_datetime(roaster_df["Date"], errors="coerce").dt.date
except Exception:
    roaster_df = pd.DataFrame()
    st.warning("⚠️ Could not load roaster data.")

# -------------------- CONSTANTS --------------------
DRIVE_FOLDER_ID = "1i5SnIkpMPqtU1kSVVdYY4jQK1lwHbR9G"  # Shared-drive folder for selfies
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
    "Mohammed Azhar",
    "Test",
    "Test 2",
]

kitchens = [
    "ANR01.BLR22","BSK01.BLR19","WFD01.BLR06","MAR01.BLR05","BTM01.BLR03","IND01.BLR01",
    "HSR01.BLR02","VDP01.CHN02","MGP01.CHN01","CMP01.CHN10","KLN01.BLR09","TKR01.BLR29",
    "CRN01.BLR17","SKN01.BLR07","HNR01.BLR16","RTN01.BLR23","YLK01.BLR15","NBR01.BLR21",
    "PGD01.CHN06","PRR01.CHN04","FZT01.BLR20","ECT01.BLR24","SJP01.BLR08","KPR01.BLR41",
    "BSN01.BLR40","VNR01.BLR18","SDP01.BLR34","TCP01.BLR27","BOM01.BLR04","CK-Corp",
    "KOR01.BLR12","SKM01.CHN03","WFD02.BLR13","KDG01.BLR14","BMS01.BLR26", "BLD01.BLR25","Week Off","Comp-Off","Leave","Holiday",
]

# -------------------- DRIVE UPLOAD (safe, with retries) --------------------
def upload_file_to_drive_bytes(file_bytes, filename, folder_id=None, mime_type=None, retries=3):
    """
    Uploads bytes to Google Drive using AuthorizedSession and multipart upload.
    Returns drive file view URL on success or None on failure.
    """
    url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true"
    metadata = {"name": filename}
    if folder_id:
        metadata["parents"] = [folder_id]

    for attempt in range(retries):
        try:
            # files param: two parts - metadata (as tuple), file (as tuple)
            files = {
                "metadata": ("metadata", json.dumps(metadata), "application/json; charset=UTF-8"),
                "file": (filename, file_bytes, mime_type or "application/octet-stream")
            }
            resp = authed_session.post(url, files=files, timeout=60)
            resp.raise_for_status()
            file_id = resp.json().get("id")
            if file_id:
                # Return view link similar to original format
                return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
            return None
        except Exception as e:
            if attempt < retries - 1:
                st.warning(f"Drive upload attempt {attempt+1} failed: {e}. Retrying...")
                time.sleep(2 ** attempt)
            else:
                st.error(f"Drive upload failed after {retries} attempts: {e}")
                return None

# -------------------- SUCCESS HELPERS --------------------
def punch_success():
    st.success("✅ Attendance recorded. Thank you!")

def roaster_success():
    if r_submit:
        safe_append_row(roaster_sheet, [str(r_date), r_manager, r_kitchen, str(r_login), r_remarks])
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
        # Validate mandatory fields
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
        skip_duplicate_check = False
        try:
            existing_records = safe_get_all_records(worksheet)
        except Exception as e:
            existing_records = []
            skip_duplicate_check = True
            st.warning(f"⚠️ Unable to read attendance sheet for duplicate check: {e}")

        if not skip_duplicate_check:
            if any(
                    str(r.get("Date")) == today_str
                    and r.get("Manager Name") == sel_manager
                    and r.get("Kitchen Name") == sel_kitchen
                    and r.get("Action") == sel_action
                    for r in existing_records
            ):
                st.warning("Duplicate punch today.")
                st.stop()

        # Upload selfie to Drive (use safe upload helper)
        try:
            selfie_bytes = photo.getvalue()
            # optional: check size
            if len(selfie_bytes) > 6 * 1024 * 1024:
                st.warning("Image is large; it may fail to upload. Please use a smaller image.")
            selfie_filename = f"{sel_manager}_{today_str}_{time_str}.jpg"
            selfie_url = upload_file_to_drive_bytes(selfie_bytes, selfie_filename, folder_id=DRIVE_FOLDER_ID, mime_type="image/jpeg")
            if selfie_url is None:
                selfie_url = "UploadErr"
        except Exception as e:
            selfie_url = "UploadErr"
            st.warning(f"Selfie upload error: {e}")

        # Append punch row
        try:
            safe_append_row(worksheet, [
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
    tab = st.selectbox(
        "Select View",
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
        st.subheader("📆 Submit Weekly Roaster")
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
                    safe_append_row(roaster_sheet, row)
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
            records = safe_get_all_records(worksheet)
            if not records:
                st.warning("No data found in the sheet.")
            else:
                for r in records:
                    # process rows
                    pass
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
            visit_sheet = safe_open("Manager Visit Tracker").worksheet("Sheet1")
            visit_records = safe_get_all_records(visit_sheet)
            visit_df = pd.DataFrame(visit_records)

            # Load Roaster Records from Roaster
            roaster_sheet = safe_open("Manager Visit Tracker").worksheet("Roaster")
            roaster_records = safe_get_all_records(roaster_sheet)
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

                try:
                    upload_bytes = screenshot.read()
                    filename = f"{review_manager}_{today}_{now_time}_screenshot.jpg"
                    upload_url = upload_file_to_drive_bytes(upload_bytes, filename, folder_id=DRIVE_FOLDER_ID, mime_type="image/jpeg")
                    screenshot_url = upload_url if upload_url else "UploadErr"
                except Exception as e:
                    screenshot_url = "UploadErr"
                    st.warning(f"Screenshot upload error: {e}")

                try:
                    review_sheet = safe_open("Manager Visit Tracker").worksheet("Daily Review")
                except gspread.exceptions.WorksheetNotFound:
                    review_sheet = safe_open("Manager Visit Tracker").add_worksheet("Daily Review", rows=1000, cols=6)
                    try:
                        retry(review_sheet.insert_row, ["Date", "Time", "Manager", "Kitchens", "Screenshot Link"], 1)
                    except Exception:
                        pass

                safe_append_row(review_sheet, [
                    today,
                    now_time,
                    review_manager,
                    ", ".join(review_kitchens),
                    screenshot_url
                ])

                st.success("✅ Daily review submitted successfully.")

    # ----------------- Leave Request block starts OUTSIDE of Daily Review -------------------
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText


    def send_leave_email(to_email, leave_manager, leave_type, from_date, to_date, reason, doc_url):
        from_email = "bablu.c@hybb.in"
        password = "ehbevbyjcwydvwwi"  # Gmail App Password

        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = f"Leave Request Submitted by {leave_manager}"

        body = f"""
Hi Team,

A leave request has been submitted:

🧑 Manager: {leave_manager}
📅 Leave Type: {leave_type}
🗓️ From: {from_date}
🗓️ To: {to_date}
📝 Reason: {reason}
📎 Document: {doc_url if doc_url != 'N/A' else 'No Document Attached'}

Please review this request in the Google Sheet.

Thanks,
HYBB Attendance System
"""
        msg.attach(MIMEText(body, 'plain'))

        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(from_email, password)
            server.send_message(msg)
            server.quit()
            print("Email sent successfully.")
        except Exception as e:
            print(f"Email sending failed: {e}")


    # Main app logic
    if tab == "Leave Request":
        st.subheader("🛌 Leave Request Form")

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
                # Upload document (if any)
                doc_url = "N/A"
                if doc_upload:
                    now = datetime.datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%H:%M:%S")
                    try:
                        doc_bytes = doc_upload.read()
                        doc_name = f"{leave_manager}_{from_date}_{now}_leave_doc"
                        upload_resp_url = upload_file_to_drive_bytes(doc_bytes, doc_name, folder_id=DRIVE_FOLDER_ID)
                        if upload_resp_url:
                            doc_url = upload_resp_url
                    except Exception as e:
                        st.warning(f"Leave doc upload failed: {e}")
                        doc_url = "UploadErr"

                # Add or open "Leave Requests" sheet
                try:
                    leave_sheet = safe_open("Manager Visit Tracker").worksheet("Leave Requests")
                except gspread.exceptions.WorksheetNotFound:
                    leave_sheet = safe_open("Manager Visit Tracker").add_worksheet("Leave Requests", rows=1000, cols=8)
                    try:
                        retry(leave_sheet.insert_row, ["Submitted On", "Manager", "Leave Type", "From Date", "To Date", "Reason", "Document Link"], 1)
                    except Exception:
                        pass

                # Append leave record
                safe_append_row(leave_sheet, [
                    datetime.date.today().strftime("%Y-%m-%d"),
                    leave_manager,
                    leave_type,
                    from_date.strftime("%Y-%m-%d"),
                    to_date.strftime("%Y-%m-%d"),
                    reason,
                    doc_url
                ])

                # Send email notification
                send_leave_email(
                    to_email="cletus@hybb.in,santhosh.p@hybb.in",  # multiple recipients allowed
                    leave_manager=leave_manager,
                    leave_type=leave_type,
                    from_date=from_date,
                    to_date=to_date,
                    reason=reason,
                    doc_url=doc_url
                )

                st.success("✅ Leave request submitted and email sent to HR.")
