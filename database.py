import streamlit as st
import gspread
import pandas as pd

from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# GOOGLE SHEETS
# ============================================================

def get_sheet(sheet_name):

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )

    client = gspread.authorize(creds)

    spreadsheet = client.open("Reading Logs")

    return spreadsheet.worksheet(sheet_name)


# ============================================================
# SAVE COMPLETED READING SESSION
# ============================================================

def save_reading_session(
    student_name,
    nfc_id,
    student_class,
    book_title,
    start_time,
    end_time,
    minutes
):

    sheet = get_sheet("Reading Logs")

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


# ============================================================
# V2: GET TODAY'S TOTAL READING TIME
# ============================================================

def get_today_reading_minutes(student_name):

    sheet = get_sheet("Reading Logs")

    records = sheet.get_all_records()

    if not records:
        return 0

    df = pd.DataFrame(records)

    # Make sure required columns exist
    if "Date" not in df.columns or "User" not in df.columns:
        return 0

    # Remove blank rows
    df = df.dropna(
        subset=["Date", "User"]
    )

    # Filter for this student
    df = df[
        df["User"].astype(str) == str(student_name)
    ]

    if df.empty:
        return 0

    # Today's date in Singapore
    today = datetime.now(
        ZoneInfo("Asia/Singapore")
    ).date()

    # Convert Date column
    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce"
    ).dt.date

    # Keep today's sessions only
    df = df[
        df["Date"] == today
    ]

    if df.empty:
        return 0

    # Find minutes column
    if "Minutes" in df.columns:

        total_minutes = pd.to_numeric(
            df["Minutes"],
            errors="coerce"
        ).fillna(0).sum()

    else:

        # Fallback in case your sheet uses
        # a different column name
        return 0

    return int(total_minutes)


# ============================================================
# READING STREAK
# ============================================================

def calculate_reading_streak(student_name):

    sheet = get_sheet("Reading Logs")

    records = sheet.get_all_records()

    if not records:
        return 0

    df = pd.DataFrame(records)

    if "Date" not in df.columns or "User" not in df.columns:
        return 0

    # Remove blank rows
    df = df.dropna(
        subset=["Date", "User"]
    )

    # Filter this student
    df = df[
        df["User"].astype(str) == str(student_name)
    ]

    if df.empty:
        return 0

    dates = set(
        pd.to_datetime(
            df["Date"],
            errors="coerce"
        ).dt.date
    )

    # Remove invalid dates
    dates.discard(pd.NaT)

    today = datetime.now(
        ZoneInfo("Asia/Singapore")
    ).date()

    # If student hasn't read today,
    # start counting from yesterday.
    current = (
        today
        if today in dates
        else today - timedelta(days=1)
    )

    streak = 0

    while current in dates:

        streak += 1

        current -= timedelta(days=1)

    return streak
