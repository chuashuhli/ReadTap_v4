import streamlit as st
import gspread

from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd


# ============================================================
# TIMEZONE
# ============================================================

SGT = ZoneInfo("Asia/Singapore")


# ============================================================
# DATETIME HELPERS
# ============================================================

def make_sgt(dt):
    """
    Make sure a datetime is timezone-aware and in Singapore time.

    Handles both:
    - timezone-aware datetime
    - timezone-naive datetime
    """

    if dt is None:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=SGT)

    return dt.astimezone(SGT)


def parse_sgt(value):
    """
    Convert a stored Google Sheets datetime string
    into a Singapore timezone-aware datetime.
    """

    if not value:
        return None

    if isinstance(value, datetime):
        return make_sgt(value)

    try:
        dt = datetime.strptime(
            str(value),
            "%Y-%m-%d %H:%M:%S"
        )

        return dt.replace(tzinfo=SGT)

    except (ValueError, TypeError):
        return None


# ============================================================
# GOOGLE SHEETS CONNECTION
# ============================================================

@st.cache_resource
def get_client():
    """
    Create and cache the Google Sheets client.
    """

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )

    client = gspread.authorize(creds)

    return client


@st.cache_resource
def get_spreadsheet():
    """
    Open and cache the Reading Logs spreadsheet.
    """

    client = get_client()

    spreadsheet = client.open(
        "Reading Logs"
    )

    return spreadsheet


@st.cache_resource
def get_sheet(sheet_name):
    """
    Return and cache a specific worksheet.
    """

    spreadsheet = get_spreadsheet()

    return spreadsheet.worksheet(
        sheet_name
    )


# ============================================================
# CACHED SHEET READ
# ============================================================

@st.cache_data(ttl=5)
def get_sheet_records(sheet_name):
    """
    Read worksheet records and cache them briefly.

    The 5-second cache helps prevent repeated Google Sheets
    reads during Streamlit reruns.
    """

    sheet = get_sheet(
        sheet_name
    )

    values = sheet.get_all_values()

    st.write("DEBUG Active Sessions values:", values[:5])

    records = sheet.get_all_records()

    return records


# ============================================================
# GET ACTIVE SESSION
# ============================================================

def get_active_session(student_name):
    """
    Find the student's current session.

    Possible statuses:
    - active
    - awaiting_confirmation

    Returns None if there is no active session.
    """

    records = get_sheet_records(
        "Active Sessions"
    )

    if not records:
        return None

    for i, row in enumerate(
        records,
        start=2
    ):

        if str(
            row.get("User", "")
        ) != str(student_name):
            continue

        status = str(
            row.get("Status", "")
        ).lower().strip()

        if status in [
            "active",
            "awaiting_confirmation",
        ]:

            return {
                "row": i,
                "user": row.get(
                    "User",
                    ""
                ),
                "nfc": row.get(
                    "NFC",
                    ""
                ),
                "start": row.get(
                    "Start",
                    ""
                ),
                "book": row.get(
                    "Book",
                    ""
                ),
                "end": row.get(
                    "End",
                    ""
                ),
                "minutes": row.get(
                    "Minutes",
                    ""
                ),
                "status": status,
            }

    return None


# ============================================================
# START READING
# ============================================================

def start_reading(
    student_name,
    nfc_id,
    start_time,
    book_title="",
):
    """
    Start a new reading session.

    V3 CHANGE:
    The book is now optional.

    The intended V3 flow is:

        TAP
        ↓
        START READING
        ↓
        Book is blank
        ↓
        Read
        ↓
        TAP
        ↓
        STOP
        ↓
        Confirm/change book

    book_title is kept as an optional argument so that the
    current V2/V3 app does not immediately break while we
    update app.py in the next step.
    """

    sheet = get_sheet(
        "Active Sessions"
    )

    # --------------------------------------------------------
    # Check whether this student already has a session.
    # --------------------------------------------------------

    existing = get_active_session(
        student_name
    )

    if existing:
        return False

    # --------------------------------------------------------
    # Make sure start time is Singapore time.
    # --------------------------------------------------------

    start_time = make_sgt(
        start_time
    )

    # --------------------------------------------------------
    # Book is intentionally allowed to be blank.
    # --------------------------------------------------------

    book_title = str(
        book_title or ""
    ).strip()

    # --------------------------------------------------------
    # Save active session.
    # --------------------------------------------------------

    sheet.append_row(
        [
            str(student_name),
            str(nfc_id),
            start_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            book_title,
            "",
            "",
            "active",
        ]
    )

    # Active Sessions changed.
    st.cache_data.clear()

    return True


# ============================================================
# STOP READING
# ============================================================

def stop_reading(
    student_name,
    end_time,
):
    """
    Stop the student's active reading session.

    The session is NOT deleted.

    It becomes:

        awaiting_confirmation

    so that the student can confirm or change the book.
    """

    sheet = get_sheet(
        "Active Sessions"
    )

    records = get_sheet_records(
        "Active Sessions"
    )

    if not records:
        return None

    # --------------------------------------------------------
    # Make sure end time is Singapore time.
    # --------------------------------------------------------

    end_time = make_sgt(
        end_time
    )

    for i, row in enumerate(
        records,
        start=2
    ):

        if str(
            row.get("User", "")
        ) != str(student_name):
            continue

        status = str(
            row.get("Status", "")
        ).lower().strip()

        # Only stop an active session.
        if status != "active":
            continue

        # ----------------------------------------------------
        # Get stored start time
        # ----------------------------------------------------

        start_time = parse_sgt(
            row.get("Start", "")
        )

        if start_time is None:
            return None

        # ----------------------------------------------------
        # Calculate duration
        # ----------------------------------------------------

        seconds = (
            end_time - start_time
        ).total_seconds()

        minutes = round(
            seconds / 60
        )

        # Prevent negative values.
        if minutes < 0:
            minutes = 0

        # ----------------------------------------------------
        # Store end time
        # ----------------------------------------------------

        sheet.update_acell(
            f"E{i}",
            end_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        )

        # ----------------------------------------------------
        # Store duration
        # ----------------------------------------------------

        sheet.update_acell(
            f"F{i}",
            minutes,
        )

        # ----------------------------------------------------
        # Keep the session for book confirmation.
        # ----------------------------------------------------

        sheet.update_acell(
            f"G{i}",
            "awaiting_confirmation",
        )

        # Active Sessions changed.
        st.cache_data.clear()

        return {
            "book": row.get(
                "Book",
                ""
            ),
            "start": start_time,
            "end": end_time,
            "minutes": minutes,
        }

    return None


# ============================================================
# FINISH / CONFIRM READING
# ============================================================

def finish_reading(
    student_name,
    final_book_title,
):

    active_sheet = get_sheet(
        "Active Sessions"
    )

    reading_sheet = get_sheet(
        "Reading Logs"
    )

    session = get_active_session(
        student_name
    )

    if not session:
        return None

    # --------------------------------------------------------
    # Only finalize a stopped session.
    # --------------------------------------------------------

    if session["status"] != "awaiting_confirmation":
        return None

    # --------------------------------------------------------
    # Determine final book.
    #
    # Priority:
    #
    # 1. Book typed/confirmed by the user
    # 2. Book already stored in Active Sessions
    # 3. current_book from user.csv
    #
    # In V3, #3 is normally what happens when the user
    # leaves the book unchanged.
    # --------------------------------------------------------

    book = str(
        final_book_title or ""
    ).strip()

    if not book:
        book = str(
            session.get(
                "book",
                ""
            ) or ""
        ).strip()

    # --------------------------------------------------------
    # Get student information.
    # --------------------------------------------------------

    user_df = pd.read_csv(
        "user.csv"
    )

    user_match = user_df[
        user_df["nickname"].astype(str)
        == str(student_name)
    ]

    if user_match.empty:
        return None

    user = user_match.iloc[0]

    # --------------------------------------------------------
    # If no book was entered and Active Sessions has no book,
    # use the student's current_book.
    # --------------------------------------------------------

    if not book:

        fallback_book = user.get(
            "current_book",
            ""
        )

        if pd.notna(fallback_book):
            book = str(
                fallback_book
            ).strip()

    # --------------------------------------------------------
    # We cannot save a reading log without a book.
    # --------------------------------------------------------

    if not book:
        return None

    # --------------------------------------------------------
    # Parse start/end times.
    # --------------------------------------------------------

    start_time = parse_sgt(
        session.get(
            "start",
            ""
        )
    )

    end_time = parse_sgt(
        session.get(
            "end",
            ""
        )
    )

    if (
        start_time is None
        or end_time is None
    ):
        return None

    # --------------------------------------------------------
    # Get minutes.
    # --------------------------------------------------------

    try:
        minutes = int(
            float(
                session.get(
                    "minutes",
                    0
                ) or 0
            )
        )

    except (
        ValueError,
        TypeError,
    ):
        minutes = 0

    # --------------------------------------------------------
    # Save completed reading session
    # to Reading Logs.
    # --------------------------------------------------------

    reading_sheet.append_row(
        [
            start_time.strftime(
                "%Y-%m-%d"
            ),
            str(student_name),
            str(user["nfc_id"]),
            str(user["class"]),
            str(book),
            start_time.strftime(
                "%H:%M:%S"
            ),
            end_time.strftime(
                "%H:%M:%S"
            ),
            minutes,
        ]
    )

    # --------------------------------------------------------
    # Update current book in user.csv.
    # --------------------------------------------------------

    user_df.loc[
        user_df["nickname"].astype(str)
        == str(student_name),
        "current_book",
    ] = book

    user_df.to_csv(
        "user.csv",
        index=False,
    )

    # --------------------------------------------------------
    # Reading is now completely finished.
    #
    # Remove the temporary Active Sessions row.
    # --------------------------------------------------------

    active_sheet.delete_rows(
        session["row"]
    )

    # --------------------------------------------------------
    # Clear cached Google Sheet data.
    # --------------------------------------------------------

    st.cache_data.clear()

    # --------------------------------------------------------
    # Return completed session details to app.py.
    # --------------------------------------------------------

    return {
        "book": book,
        "start": start_time,
        "end": end_time,
        "minutes": minutes,
    }
    
# ============================================================
# TODAY'S READING
# ============================================================

def get_today_reading_minutes(
    student_name,
):
    """
    Calculate today's completed reading minutes.
    """

    records = get_sheet_records(
        "Reading Logs"
    )

    if not records:
        return 0

    df = pd.DataFrame(
        records
    )

    if "Date" not in df.columns:
        return 0

    if "User" not in df.columns:
        return 0

    df = df.dropna(
        subset=[
            "Date",
            "User",
        ]
    )

    df = df[
        df["User"].astype(str)
        == str(student_name)
    ]

    if df.empty:
        return 0

    today = datetime.now(
        SGT
    ).date()

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce",
    ).dt.date

    df = df[
        df["Date"] == today
    ]

    if df.empty:
        return 0

    total_minutes = pd.to_numeric(
        df["Minutes"],
        errors="coerce",
    ).fillna(0).sum()

    return int(
        total_minutes
    )


# ============================================================
# READING STREAK
# ============================================================

def calculate_reading_streak(
    student_name,
):
    """
    Calculate the current reading streak
    from completed Reading Logs.
    """

    records = get_sheet_records(
        "Reading Logs"
    )

    if not records:
        return 0

    df = pd.DataFrame(
        records
    )

    if "Date" not in df.columns:
        return 0

    if "User" not in df.columns:
        return 0

    df = df.dropna(
        subset=[
            "Date",
            "User",
        ]
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
            errors="coerce",
        )
        .dt.date
        .dropna()
    )

    today = datetime.now(
        SGT
    ).date()

    current = (
        today
        if today in dates
        else today - timedelta(
            days=1
        )
    )

    streak = 0

    while current in dates:

        streak += 1

        current -= timedelta(
            days=1
        )

    return streak