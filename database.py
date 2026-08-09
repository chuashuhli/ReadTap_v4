import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd


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
# GET ACTIVE SESSION
# ============================================================

def get_active_session(student_name):

    sheet = get_sheet("Active Sessions")

    records = sheet.get_all_records()

    if not records:
        return None

    for i, row in enumerate(records, start=2):

        if str(row.get("User", "")) == str(student_name):

            status = str(row.get("Status", "active")).lower()

            if status in ["active", "awaiting_confirmation"]:

                return {
                    "row": i,
                    "user": row.get("User", ""),
                    "nfc": row.get("NFC", ""),
                    "start": row.get("Start", ""),
                    "book": row.get("Book", ""),
                    "end": row.get("End", ""),
                    "minutes": row.get("Minutes", ""),
                    "status": status
                }

    return None


# ============================================================
# START READING
# ============================================================

def start_reading(
    student_name,
    nfc_id,
    book_title,
    start_time
):

    sheet = get_sheet("Active Sessions")

    # Check for an existing session
    existing = get_active_session(student_name)

    if existing:
        return False

    sheet.append_row([
        str(student_name),
        str(nfc_id),
        start_time.strftime("%Y-%m-%d %H:%M:%S"),
        str(book_title),
        "",
        "",
        "active"
    ])

    return True


# ============================================================
# STOP READING
# ============================================================

def stop_reading(student_name, end_time):
    sheet = get_sheet("Active Sessions")

    records = sheet.get_all_records()

    for i, row in enumerate(records, start=2):

        if str(row["User"]) == str(student_name):

            # Get the stored start time
            start_time = datetime.strptime(
                row["Start"],
                "%Y-%m-%d %H:%M:%S"
            )

            # Make sure the stored time uses Singapore timezone
            start_time = start_time.replace(
                tzinfo=ZoneInfo("Asia/Singapore")
            )

            # Calculate reading duration
            minutes = round(
                (end_time - start_time).total_seconds() / 60
            )

            # Delete active session
            sheet.delete_rows(i)

            return {
                "book": row["Book"],
                "start": start_time,
                "end": end_time,
                "minutes": minutes
            }

    return None


# ============================================================
# FINISH / CONFIRM READING
# ============================================================

def finish_reading(
    student_name,
    final_book_title
):

    active_sheet = get_sheet("Active Sessions")

    reading_sheet = get_sheet("Reading Logs")

    session = get_active_session(student_name)

    if not session:
        return None

    # Only finalize a stopped session
    if session["status"] != "awaiting_confirmation":
        return None

    # Use original book if no replacement was entered
    book = final_book_title.strip()

    if not book:
        book = str(session["book"])

    # Parse start/end
    start_time = datetime.strptime(
        session["start"],
        "%Y-%m-%d %H:%M:%S"
    )

    end_time = datetime.strptime(
        session["end"],
        "%Y-%m-%d %H:%M:%S"
    )

    minutes = int(session["minutes"])

    # --------------------------------------------------------
    # Get student information from user.csv
    # --------------------------------------------------------

    user_df = pd.read_csv("user.csv")

    user = user_df[
        user_df["nickname"].astype(str)
        == str(student_name)
    ]

    if user.empty:
        return None

    user = user.iloc[0]

    # --------------------------------------------------------
    # Save completed reading session
    # --------------------------------------------------------

    reading_sheet.append_row([
        start_time.strftime("%Y-%m-%d"),
        str(student_name),
        str(user["nfc_id"]),
        str(user["class"]),
        str(book),
        start_time.strftime("%H:%M:%S"),
        end_time.strftime("%H:%M:%S"),
        minutes
    ])

    # --------------------------------------------------------
    # Update current book
    # --------------------------------------------------------

    user_df.loc[
        user_df["nickname"].astype(str)
        == str(student_name),
        "current_book"
    ] = book

    user_df.to_csv(
        "user.csv",
        index=False
    )

    # --------------------------------------------------------
    # Delete active session
    # --------------------------------------------------------

    active_sheet.delete_rows(
        session["row"]
    )

    return {
        "book": book,
        "start": start_time,
        "end": end_time,
        "minutes": minutes
    }


# ============================================================
# TODAY'S READING
# ============================================================

def get_today_reading_minutes(student_name):

    sheet = get_sheet("Reading Logs")

    records = sheet.get_all_records()

    if not records:
        return 0

    df = pd.DataFrame(records)

    if "Date" not in df.columns:
        return 0

    if "User" not in df.columns:
        return 0

    df = df.dropna(
        subset=["Date", "User"]
    )

    df = df[
        df["User"].astype(str)
        == str(student_name)
    ]

    if df.empty:
        return 0

    today = datetime.now(
        ZoneInfo("Asia/Singapore")
    ).date()

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce"
    ).dt.date

    df = df[
        df["Date"] == today
    ]

    if df.empty:
        return 0

    total_minutes = pd.to_numeric(
        df["Minutes"],
        errors="coerce"
    ).fillna(0).sum()

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

    df = df.dropna(
        subset=["Date", "User"]
    )

    df = df[
        df["User"].astype(str)
        == str(student_name)
    ]

    if df.empty:
        return 0

    dates = set(
        pd.to_datetime(
            df["Date"],
            errors="coerce"
        ).dt.date
    )

    today = datetime.now(
        ZoneInfo("Asia/Singapore")
    ).date()

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