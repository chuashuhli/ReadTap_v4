import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd


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


def get_active_session(student_name):

    sheet = get_sheet("Active Sessions")

    records = sheet.get_all_records()

    for i, row in enumerate(records, start=2):
        if str(row["User"]) == str(student_name):
            return {
                "row": i,
                "start": row["Start"],
                "book": row["Book"]
            }

    return None

def start_reading(
    student_name,
    nfc_id,
    book_title,
    start_time
):

    sheet = get_sheet("Active Sessions")

    # Remove any previous active session
    session = get_active_session(student_name)

    if session:
        sheet.delete_rows(session["row"])

    sheet.append_row([
        str(student_name),
        str(nfc_id),
        start_time.strftime("%Y-%m-%d %H:%M:%S"),
        str(book_title)
    ])



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

def calculate_reading_streak(student_name):

    sheet = get_sheet("Reading Logs")

    records = sheet.get_all_records()

    if not records:
        return 0

    df = pd.DataFrame(records)

    # Remove blank rows
    df = df.dropna(subset=["Date", "User"])

    # Filter this student
    df = df[df["User"].astype(str) == str(student_name)]

    if df.empty:
        return 0

    dates = set(pd.to_datetime(df["Date"]).dt.date)

    today = datetime.now(ZoneInfo("Asia/Singapore")).date()

    # If the student hasn't read today,
    # continue counting from yesterday.
    current = today if today in dates else today - timedelta(days=1)

    streak = 0

    while current in dates:
        streak += 1
        current -= timedelta(days=1)

    return streak


from datetime import datetime
from zoneinfo import ZoneInfo

start_reading(
    "SL",
    "1001",
    "Harry Potter",
    datetime.now(ZoneInfo("Asia/Singapore"))
)