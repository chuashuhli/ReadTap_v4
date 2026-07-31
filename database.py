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