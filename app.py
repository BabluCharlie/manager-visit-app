# HYBB Attendance System – full Streamlit script (continued)

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
            if resp.status_code == 200 else "UploadErr"
        )

        worksheet.append_row([
            today_str, time_str, sel_manager, sel_kitchen, sel_action,
            lat, lon, selfie_url, location_url
        ])
        punch_success()

# ------- RIGHT COLUMN: Tabs -------
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

    if tab == "Roaster Entry":
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
                roaster_success()

    elif tab == "Roaster View":
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
                    roster_today = roaster_df[roaster_df["Date"] == sel_date][["Manager", "Kitchen"]]
                    view_df["key"] = view_df["Manager Name"] + "|" + view_df["Kitchen Name"]
                    roster_today["key"] = roster_today["Manager"] + "|" + roster_today["Kitchen"]
                    view_df["Mismatch"] = ~view_df["key"].isin(roster_today["key"])
                    view_df = view_df.drop(columns=["key"])
                st.dataframe(view_df, use_container_width=True)

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
            visits = df_f.groupby(["Manager Name", "Kitchen Name"]).size().reset_index(name="Visits")
            st.dataframe(visits, use_container_width=True)
