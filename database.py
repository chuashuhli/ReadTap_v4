import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


def get_sheet():

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )

    client = gspread.authorize(creds)

    return client.open("Reading Logs").sheet1



def save_reading_session(
    student_name,
    nfc_id,
    student_class,
    book_title,
    start_time,
    end_time,
    minutes
):

    sheet = get_sheet()

    sheet.append_row([
        start_time.strftime("%Y-%m-%d"),
        str(student_name),
        str(nfc_id),
        str(student_class),
        str(book_title),
        start_time.strftime("%H:%M:%S"),
        end_time.strftime("%H:%M:%S"),
        int(minutes)
    ])


from datetime import datetime, timedelta
import pandas as pd


def calculate_reading_streak(student_name):

    sheet = get_sheet()

    records = sheet.get_all_records()

    if not records:
        return 0

    df = pd.DataFrame(records)

    df = df[df["User"] == student_name]

    if df.empty:
        return 0

    dates = (
        pd.to_datetime(df["Date"])
        .dt.date
        .drop_duplicates()
        .sort_values(ascending=False)
        .tolist()
    )

    today = datetime.now(ZoneInfo("Asia/Singapore")).date()

    streak = 0
    expected = today

    # If the user hasn't read today, allow the streak
    # to continue from yesterday.
    if expected not in dates:
        expected = today - timedelta(days=1)

    while expected in dates:
        streak += 1
        expected -= timedelta(days=1)

    return streak