import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from database import (
    save_reading_session,
    calculate_reading_streak,
    get_today_reading_minutes,
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
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    /* ======================================================
       OVERALL PAGE
       ====================================================== */

    .stApp {
        background-color: #0e1117;
    }

    .block-container {
        max-width: 900px;
        padding-top: 45px;
        padding-bottom: 60px;
    }


    /* ======================================================
       REMOVE STREAMLIT EXTRA TOP SPACE
       ====================================================== */

    header[data-testid="stHeader"] {
        background: transparent;
    }


    /* ======================================================
       MAIN LOGO / TITLE
       ====================================================== */

    .readtap-title {
        text-align: center;
        font-size: 64px;
        font-weight: 800;
        color: #f5f5f5;
        line-height: 1.1;
        margin-bottom: 8px;
    }

    .readtap-tagline {
        text-align: center;
        font-size: 22px;
        color: #aab2c0;
        margin-bottom: 45px;
    }


    /* ======================================================
       WELCOME CARD
       ====================================================== */

    .welcome-card {
        background: #fff9e8;
        border: 2px solid #e6ddc5;
        border-radius: 28px;
        padding: 42px 45px;
        margin: 0 auto 55px auto;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.25);
        color: #263b52;
    }


    .welcome-name {
        text-align: center;
        font-size: 34px;
        font-weight: 750;
        color: #263b52;
        margin-bottom: 20px;
    }


    .badge {
        text-align: center;
        font-size: 22px;
        color: #596273;
        margin-bottom: 32px;
    }


    .profile-line {
        text-align: center;
        font-size: 21px;
        color: #596273;
        margin: 20px 0;
        line-height: 1.5;
    }


    .profile-value {
        font-weight: 700;
        color: #263b52;
    }


    /* ======================================================
       SECTION HEADINGS
       ====================================================== */

    .section-title {
        font-size: 36px;
        font-weight: 800;
        color: #f5f5f5;
        margin-top: 20px;
        margin-bottom: 30px;
    }


    /* ======================================================
       TODAY'S READING
       ====================================================== */

    .goal-label {
        text-align: center;
        color: #aab2c0;
        font-size: 21px;
        margin-bottom: 5px;
    }


    .goal-number {
        text-align: center;
        color: #f5f5f5;
        font-size: 38px;
        font-weight: 800;
        margin-bottom: 20px;
    }


    .remaining-box {
        background: #19324d;
        border-radius: 12px;
        padding: 18px 22px;
        color: #54a8ff;
        font-size: 18px;
        margin-top: 18px;
        margin-bottom: 50px;
    }


    .achieved-box {
        background: #123d2b;
        border-radius: 12px;
        padding: 18px 22px;
        color: #55d98b;
        font-size: 18px;
        margin-top: 18px;
        margin-bottom: 50px;
    }


    /* ======================================================
       READING AREA
       ====================================================== */

    .reading-info {
        background: #19324d;
        border-radius: 12px;
        padding: 18px 22px;
        color: #54a8ff;
        font-size: 18px;
        margin: 20px 0;
    }


    /* ======================================================
       STREAMLIT TEXT
       ====================================================== */

    .stRadio label,
    .stTextInput label {
        color: #f5f5f5 !important;
    }


    /* ======================================================
       BUTTONS
       ====================================================== */

    .stButton > button {
        border-radius: 12px;
        padding: 10px 22px;
        font-size: 17px;
        font-weight: 600;
        border: 1px solid #3a414d;
    }


    /* ======================================================
       DIVIDERS
       ====================================================== */

    hr {
        border-color: #30343b;
        margin-top: 35px;
        margin-bottom: 35px;
    }


    /* ======================================================
       MOBILE
       ====================================================== */

    @media (max-width: 600px) {

        .block-container {
            padding-left: 20px;
            padding-right: 20px;
            padding-top: 25px;
        }

        .readtap-title {
            font-size: 44px;
        }

        .readtap-tagline {
            font-size: 18px;
            margin-bottom: 30px;
        }

        .welcome-card {
            padding: 30px 20px;
            border-radius: 22px;
        }

        .welcome-name {
            font-size: 27px;
        }

        .profile-line {
            font-size: 18px;
        }

        .section-title {
            font-size: 29px;
        }

        .goal-number {
            font-size: 32px;
        }
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SESSION STATE
# ============================================================

for key, value in {
    "reading": False,
    "start_time": None,
    "current_book": "",
    "show_summary": False,
    "summary": {}
}.items():

    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# USER
# ============================================================

user_df = pd.read_csv("user.csv")
user = user_df.iloc[0]

nickname = user["nickname"]
goal = int(user["goal"])

streak = calculate_reading_streak(nickname)

today_total = get_today_reading_minutes(nickname)

remaining = max(goal - today_total, 0)


# ============================================================
# RECENT BOOKS
# ============================================================

try:

    reading_log = pd.read_csv("reading_log.csv")

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
# READTAP HEADER
# ============================================================

st.markdown(
    """
    <div class="readtap-title">
        📚 ReadTap
    </div>

    <div class="readtap-tagline">
        Small taps. Big reading adventures.
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# WELCOME CARD
# ============================================================

last_book = user["current_book"]

st.markdown(
    f"""
    <div class="welcome-card">

        <div class="welcome-name">
            👋 Welcome back, {nickname}!
        </div>

        <div class="badge">
            🏅 📚 &nbsp; ReadTap Explorer
        </div>

        <div class="profile-line">
            📖 Last Book:
            <span class="profile-value">
                {last_book}
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
# TODAY'S READING
# ============================================================

st.markdown(
    """
    <div class="section-title">
        📖 Today's Reading
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="goal-label">
        🎯 Daily Reading Goal
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="goal-number">
        {today_total} / {goal} minutes
    </div>
    """,
    unsafe_allow_html=True
)

progress = min(today_total / goal, 1.0) if goal > 0 else 0

st.progress(progress)


if today_total >= goal:

    st.markdown(
        """
        <div class="achieved-box">
            🎉 Daily reading goal achieved!
        </div>
        """,
        unsafe_allow_html=True
    )

else:

    st.markdown(
        f"""
        <div class="remaining-box">
            📚 {remaining} more minutes to reach today's goal.
        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# READING SUMMARY
# ============================================================

if st.session_state.show_summary:

    s = st.session_state.summary

    st.success("🎉 Reading Complete!")

    st.markdown(
        f"""
        ## Great job, {nickname}!

        ### 📚 Book
        {s["book"]}

        ### 🕒 Started
        {s["start"]}

        ### 🕒 Finished
        {s["end"]}

        ### ⏱ Reading Time
        **{s["minutes"]} minutes**

        ### 📖 Today's Total
        **{s["today_total"]} / {s["goal"]} minutes**
        """,
        unsafe_allow_html=True
    )

    if s["today_total"] >= s["goal"]:

        st.success("🎯 Daily Goal Achieved!")

        st.balloons()

    else:

        st.info(
            f"📚 {s['remaining']} more minutes "
            "to reach today's goal."
        )

    if st.button("📚 Start Another Reading Session"):

        st.session_state.show_summary = False

        st.rerun()


# ============================================================
# CURRENTLY READING
# ============================================================

elif st.session_state.reading:

    st.success("📚 Enjoy your reading!")

    st.markdown(
        f"""
        ## 📖 {st.session_state.current_book}
        """,
        unsafe_allow_html=True
    )

    st.info(
        "Started at "
        f"{st.session_state.start_time.strftime('%I:%M %p')}"
    )

    if st.button("✅ Finish Reading"):

        end = datetime.now(
            ZoneInfo("Asia/Singapore")
        )

        minutes = round(
            (
                end - st.session_state.start_time
            ).total_seconds() / 60
        )

        # ----------------------------------------------------
        # SAVE SESSION
        # ----------------------------------------------------

        save_reading_session(
            student_name=user["nickname"],
            nfc_id=user["nfc_id"],
            student_class=user["class"],
            book_title=st.session_state.current_book,
            start_time=st.session_state.start_time,
            end_time=end,
            minutes=minutes
        )

        # ----------------------------------------------------
        # RECALCULATE TODAY'S TOTAL
        # ----------------------------------------------------

        today_total = get_today_reading_minutes(
            user["nickname"]
        )

        goal = int(user["goal"])

        remaining = max(
            goal - today_total,
            0
        )

        # ----------------------------------------------------
        # SAVE SUMMARY
        # ----------------------------------------------------

        st.session_state.summary = {

            "book": st.session_state.current_book,

            "start": st.session_state.start_time.strftime(
                "%I:%M %p"
            ),

            "end": end.strftime(
                "%I:%M %p"
            ),

            "minutes": minutes,

            "today_total": today_total,

            "goal": goal,

            "remaining": remaining
        }

        st.session_state.reading = False

        st.session_state.show_summary = True

        st.rerun()


# ============================================================
# START READING
# ============================================================

else:

    st.markdown(
        """
        <div class="section-title">
            📚 What are you reading today?
        </div>
        """,
        unsafe_allow_html=True
    )

    option = st.radio(
        "Choose an option",
        (
            "Continue previous book",
            "Start a new book"
        )
    )

    if option == "Continue previous book":

        book = user["current_book"]

        st.markdown(
            f"""
            <div class="reading-info">
                📖 Continuing:
                <strong>{book}</strong>
            </div>
            """,
            unsafe_allow_html=True
        )

    else:

        default = (
            recent_books[-1]
            if recent_books
            else ""
        )

        book = st.text_input(
            "Book title",
            value=default
        )

        if recent_books:

            st.caption(
                "Recent books: "
                + ", ".join(
                    reversed(recent_books)
                )
            )

    # --------------------------------------------------------
    # START BUTTON
    # --------------------------------------------------------

    if st.button("📖 Start Reading"):

        if not book.strip():

            st.warning(
                "Please enter a book title."
            )

        else:

            st.session_state.current_book = book

            user_df.loc[
                0,
                "current_book"
            ] = book

            user_df.to_csv(
                "user.csv",
                index=False
            )

            st.session_state.start_time = datetime.now(
                ZoneInfo("Asia/Singapore")
            )

            st.session_state.reading = True

            st.rerun()