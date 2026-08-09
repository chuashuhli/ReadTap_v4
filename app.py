import streamlit as st
import pandas as pd

from datetime import datetime
from zoneinfo import ZoneInfo

from database import (
    calculate_reading_streak,
    start_reading,
    stop_reading,
    finish_reading,
    get_today_reading_minutes,
    get_active_session
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="ReadTap",
    page_icon="📚",
    layout="centered"
)


# ============================================================
# SESSION STATE
# ============================================================

for k, v in {
    "reading": False,
    "start_time": None,
    "current_book": "",
    "show_summary": False,
    "summary": {},
    "book_confirmation": False,
    "pending_session": None
}.items():

    if k not in st.session_state:
        st.session_state[k] = v


# ============================================================
# USER
# ============================================================

user_df = pd.read_csv("user.csv")

user = user_df.iloc[0]

nickname = str(user["nickname"])
nfc_id = str(user["nfc_id"])

streak = calculate_reading_streak(
    nickname
)

today_total = get_today_reading_minutes(
    nickname
)

goal = int(user["goal"])

remaining = max(
    goal - today_total,
    0
)


# ============================================================
# RECENT BOOKS
# ============================================================

try:

    reading_log = pd.read_csv(
        "reading_log.csv"
    )

    recent_books = (
        reading_log["book_title"]
        .dropna()
        .drop_duplicates()
        .tail(5)
        .tolist()
    )

except Exception:

    recent_books = []


# ============================================================
# NFC TAP DETECTION
# ============================================================

nfc_student = st.query_params.get(
    "student"
)


if (
    nfc_student
    and str(nfc_student) == nfc_id
):

    # --------------------------------------------------------
    # Check whether there is already an active session
    # --------------------------------------------------------

    active = get_active_session(
        nickname
    )

    # ========================================================
    # FIRST TAP → START
    # ========================================================

    if active is None:

        book = str(
            user["current_book"]
        ).strip()

        if book:

            start_time = datetime.now(
                ZoneInfo("Asia/Singapore")
            )

            success = start_reading(
                student_name=nickname,
                nfc_id=nfc_id,
                book_title=book,
                start_time=start_time
            )

            if success:

                st.session_state.current_book = book

                st.session_state.start_time = start_time

                st.session_state.reading = True

                st.session_state.show_summary = False

                st.session_state.book_confirmation = False

                # Remove NFC URL parameter
                st.query_params.clear()

                st.rerun()

    # ========================================================
    # SECOND TAP → STOP
    # ========================================================

    elif active["status"] == "active":

        end_time = datetime.now(
            ZoneInfo("Asia/Singapore")
        )

        stopped = stop_reading(
            nickname,
            end_time
        )

        if stopped:

            book = stopped["book"]
            start_time = stopped["start"]
            end_time = stopped["end"]
            minutes = stopped["minutes"]

            st.session_state.pending_session = stopped

            st.session_state.book_confirmation = True

            st.session_state.reading = False

            st.query_params.clear()

            st.rerun()


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <style>

    .readtap-header {
        text-align: center;
        padding: 20px 0 30px 0;
    }

    .readtap-logo {
        font-size: 52px;
        font-weight: 800;
        color: #24364B;
    }

    .readtap-tagline {
        font-size: 20px;
        color: #667085;
        margin-top: -10px;
    }

    .welcome-card {
        background: #FFF9E8;
        border: 2px solid #E7DFC5;
        border-radius: 28px;
        padding: 40px;
        margin-bottom: 40px;
        color: #24364B;
        text-align: center;
    }

    .welcome-name {
        font-size: 34px;
        font-weight: 700;
        margin-bottom: 20px;
    }

    .badge {
        font-size: 21px;
        margin-bottom: 30px;
    }

    .profile-line {
        font-size: 20px;
        margin: 20px 0;
        color: #5C6675;
    }

    .profile-value {
        font-weight: 700;
        color: #24364B;
    }

    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="readtap-header">
        <div class="readtap-logo">
            📚 ReadTap
        </div>
        <div class="readtap-tagline">
            Small taps. Big reading adventures.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# WELCOME CARD
# ============================================================

current_book = str(
    user["current_book"]
).strip()

st.markdown(
    f"""
    <div class="welcome-card">

        <div class="welcome-name">
            👋 Welcome back, {nickname}!
        </div>

        <div class="badge">
            🏅 📚 ReadTap Explorer
        </div>

        <div class="profile-line">
            📖 Last Book:
            <span class="profile-value">
                {current_book}
            </span>
        </div>

        <div class="profile-line">
            🎯 Daily Goal:
            <span class="profile-value">
                {goal} mins
            </span>
        </div>

        <div class="profile-line">
            🔥 Reading Streak:
            <span class="profile-value">
                {streak} days
            </span>
        </div>

    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# READING SUMMARY
# ============================================================

if st.session_state.show_summary:

    s = st.session_state.summary

    st.success(
        "🎉 Reading Complete!"
    )

    st.write(
        f"## Great job, {nickname}!"
    )

    st.write("### 📚 Book")
    st.write(s["book"])

    st.write("### 🕒 Started")
    st.write(s["start"])

    st.write("### 🕒 Finished")
    st.write(s["end"])

    st.write("### ⏱ Reading Time")
    st.write(
        f"**{s['minutes']} minutes**"
    )

    st.write("### 📖 Today's Total")
    st.write(
        f"**{s['today_total']} / {s['goal']} minutes**"
    )

    if s["today_total"] >= s["goal"]:

        st.success(
            "🎯 Daily Goal Achieved!"
        )

        st.balloons()

    else:

        st.info(
            f"📚 {s['remaining']} more minutes "
            "to reach today's goal."
        )

    if st.button(
        "📚 Start Another Reading Session"
    ):

        st.session_state.show_summary = False

        st.rerun()


# ============================================================
# BOOK CONFIRMATION
# ============================================================

elif st.session_state.book_confirmation:

    session = st.session_state.pending_session

    st.subheader(
        "📖 What were you reading?"
    )

    original_book = session["book"]

    minutes = int(
        session["minutes"]
    )

    st.info(
        f"📚 **{original_book}**\n\n"
        f"⏱ Reading time: **{minutes} minutes**"
    )

    st.write(
        "If this is correct, leave the box empty."
    )

    new_book = st.text_input(
        "Change book title if needed",
        placeholder=original_book
    )

    if st.button(
        "✅ Save Reading"
    ):

        result = finish_reading(
            nickname,
            new_book
        )

        if result:

            today_total = get_today_reading_minutes(
                nickname
            )

            goal = int(
                user["goal"]
            )

            remaining = max(
                goal - today_total,
                0
            )

            st.session_state.summary = {

                "book": result["book"],

                "start": result["start"].strftime(
                    "%I:%M %p"
                ),

                "end": result["end"].strftime(
                    "%I:%M %p"
                ),

                "minutes": result["minutes"],

                "today_total": today_total,

                "goal": goal,

                "remaining": remaining
            }

            st.session_state.book_confirmation = False

            st.session_state.pending_session = None

            st.session_state.show_summary = True

            st.rerun()


# ============================================================
# CURRENTLY READING
# ============================================================

elif st.session_state.reading:

    st.success(
        "📚 Enjoy your reading!"
    )

    st.write(
        f"## 📖 {st.session_state.current_book}"
    )

    st.info(
        "Started at "
        +
        st.session_state.start_time.strftime(
            "%I:%M %p"
        )
    )

    st.write(
        "📱 Tap your ReadTap tag again "
        "when you finish reading."
    )


# ============================================================
# TODAY'S READING
# ============================================================

else:

    st.subheader(
        "📖 Today's Reading"
    )

    st.write(
        f"**🎯 Daily Reading Goal**"
    )

    st.markdown(
        f"## {today_total} / {goal} minutes"
    )

    progress = (
        min(today_total / goal, 1.0)
        if goal > 0
        else 0
    )

    st.progress(progress)

    if today_total >= goal:

        st.success(
            "🎯 Daily Goal Achieved!"
        )

    else:

        st.info(
            f"📚 {remaining} more minutes "
            "to reach today's goal."
        )


# ============================================================
# BOOK CHANGE
# ============================================================

if (
    not st.session_state.reading
    and not st.session_state.book_confirmation
    and not st.session_state.show_summary
):

    st.divider()

    st.subheader(
        "📚 What are you reading?"
    )

    st.write(
        f"Current book: **{current_book}**"
    )

    new_book = st.text_input(
        "Change book title",
        placeholder="Enter a new book title"
    )

    if st.button(
        "💾 Change Book"
    ):

        if new_book.strip():

            user_df.loc[
                0,
                "current_book"
            ] = new_book.strip()

            user_df.to_csv(
                "user.csv",
                index=False
            )

            st.success(
                f"📖 Current book changed to "
                f"**{new_book.strip()}**"
            )

            st.rerun()

        else:

            st.warning(
                "Please enter a book title."
            )