import streamlit as st
import gspread
import datetime
import json
import pandas as pd
import pytz
from oauth2client.service_account import ServiceAccountCredentials

try:
    from streamlit_js_eval import get_geolocation
except:
    get_geolocation = None

# -------------------- CONFIG --------------------
st.set_page_config(page_title="HYBB Attendance System", layout="wide")

# -------------------- STYLING --------------------
st.markdown("""
<style>
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
div[data-baseweb="select"] div[class*="SingleValue"] {
    color: black !important;
    font-weight: 600 !important;
}
div[data-baseweb="select"] [role="option"] {
    background-color: white !important;
    color: black !important;
    font-weight: 500;
}
div[data-baseweb="select"] [role="option"]:hover {
    background-color: #f0f0f0 !important;
}
div[data-baseweb="select"] [aria-selected="true"] {
    background-color: #d0f0c0 !important;
}
</style>
""", unsafe_allow_html=True)

# -------------------- GOOGLE SHEET AUTH --------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(st.secrets["GOOGLE_SHEETS_CREDS"]), scope)
client = gspread.authorize(creds)

worksheet = client.open("Manager Visit Tracker").sheet1
try:
    roaster_sheet = client.open("Manager Visit Tracker").worksheet("Roaster")
except:
    roaster_sheet = client.open("Manager Visit Tracker").add_worksheet("Roaster", rows=1000, cols=5)
    roaster_sheet.insert_row(["Date", "Manager", "Kitchen", "Login Time", "Remarks"], 1)

# -------------------- SESSION STATE INIT --------------------
if "form_submitted" not in st.session_state:
    st.session_state.form_submitted = False

def reset_form():
    for key in list(st.session_state.keys()):
        if key not in ["user_lat", "user_lon", "page"]:
            del st.session_state[key]

# -------------------- PAGE ROUTING --------------------
query_params = st.experimental_get_query_params()
current_page = query_params.get("page", ["main"])[0]

col1, col2 = st.columns(2)
with col1:
    if st.button("🏠 Go to Punch In/Out"):
        st.experimental_set_query_params(page="main")
        st.rerun()
with col2:
    if st.button("📅 Go to Roaster Entry"):
        st.experimental_set_query_params(page="roaster")
        st.rerun()

# -------------------- MANAGER / KITCHEN LIST --------------------
manager_list = ["", "Ayub Sait", "Rakesh Babu", "John Joseph", "Naveen Kumar M", "Sangeetha RM", "Joy Matabar", "Sonu Kumar", "Samsudeen", "Tauseef", "Bablu C", "Umesh M", "Selva Kumar", "Srividya", "Test", "Test 2"]
kitchens = ["ANR01.BLR22", "BSK01.BLR19", "WFD01.BLR06", "MAR01.BLR05", "BTM01.BLR03", "IND01.BLR01", "HSR01.BLR02", "VDP01.CHN02", "MGP01.CHN01", "CMP01.CHN10", "KLN01.BLR09", "TKR01.BLR29", "CRN01.BLR17", "SKN01.BLR07", "HNR01.BLR16", "RTN01.BLR23", "YLK01.BLR15", "NBR01.BLR21", "PGD01.CHN06", "PRR01.CHN04", "FZT01.BLR20", "ECT01.BLR24", "SJP01.BLR08", "KPR01.BLR41", "BSN01.BLR40", "VNR01.BLR18", "SDP01.BLR34", "TCP01.BLR27", "BOM01.BLR04", "CK-Corp", "KOR01.BLR12", "SKM01.CHN03", "WFD02.BLR13", "KDG01.BLR14", "Week Off", "Comp-Off", "Leave"]

# -------------------- PAGE: Punch In/Out --------------------
if current_page == "main":
    st.subheader("Punch In / Out")
    with st.form("punch_form", clear_on_submit=True):
        manager = st.selectbox("Select Manager", manager_list, key="manager")
        kitchen = st.selectbox("Select Kitchen", kitchens, key="kitchen")
        action = st.selectbox("Action", ["", "Punch In", "Punch Out"], key="action")
        selfie = st.file_uploader("Upload Selfie (Optional)", type=["jpg", "jpeg", "png"], key="selfie")
        remarks = st.text_area("Remarks", key="remarks")
        submit = st.form_submit_button("Submit Punch")

        if submit:
            worksheet.append_row([str(datetime.datetime.now()), manager, kitchen, action, remarks])
            st.success("✅ Punch submitted successfully")
            reset_form()

# -------------------- PAGE: Roaster Entry --------------------
elif current_page == "roaster":
    st.subheader("Weekly Roaster Entry")
    with st.form("roaster_form", clear_on_submit=True):
        r_date = st.date_input("Date", key="r_date")
        r_manager = st.selectbox("Manager", manager_list, key="r_manager")
        r_kitchen = st.selectbox("Kitchen", kitchens, key="r_kitchen")
        r_login = st.time_input("Login Time", key="r_login")
        r_remarks = st.text_area("Remarks", key="r_remarks")
        r_submit = st.form_submit_button("Submit Roaster")

        if r_submit:
            roaster_sheet.append_row([str(r_date), r_manager, r_kitchen, str(r_login), r_remarks])
            st.success("✅ Roaster submitted successfully")
            reset_form()
