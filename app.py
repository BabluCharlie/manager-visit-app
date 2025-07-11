if st.button("Submit Punch"):
    if not manager or not kitchen:
        st.warning("⚠️ Please select both Manager and Kitchen before submitting.")
        st.stop()

    if not photo:
        st.error("📸 Please take a selfie before submitting.")
        st.stop()

    now = datetime.datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")
    g = geocoder.ip('me')
    lat, lon = g.latlng if g.latlng else ("N/A", "N/A")
    location_url = f"https://www.google.com/maps?q={lat},{lon}" if lat != "N/A" else "Location not available"

    # Duplicate punch check
    records = worksheet.get_all_records()
    duplicate = any(
        r.get("Date") == today_str and r.get("Manager Name") == manager and r.get("Kitchen Name") == kitchen and r.get("Action") == action
        for r in records
    )

    if duplicate:
        st.warning("⚠️ You've already submitted this punch today.")
        st.stop()

    selfie_url = ""
    upload_url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
    headers = {"Authorization": f"Bearer {creds.get_access_token().access_token}"}
    metadata = {
        "name": f"{manager}_{today_str}_{time_str}.jpg",
        "parents": ["1geeQPitCovvG5_2MlNOdvTOfupHu2G78"]  # ✅ ONLY folder ID
    }
    files = {
        'data': ('metadata', json.dumps(metadata), 'application/json'),
        'file': photo.getvalue()
    }
    resp = requests.post(upload_url, headers=headers, files=files)
    if resp.status_code == 200:
        file_id = resp.json()["id"]
        selfie_url = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
    else:
        st.error("❌ Failed to upload selfie to Google Drive.")
        st.stop()

    # Append to sheet
    worksheet.append_row([today_str, time_str, manager, kitchen, action, lat, lon, selfie_url, location_url])
    st.success("✅ Punch recorded successfully!")
    st.markdown(f"[📍 Location Map]({location_url})")
    st.markdown(f"[📸 View Selfie]({selfie_url})")
