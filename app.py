import streamlit as st
import pandas as pd

from datetime import datetime
from zoneinfo import ZoneInfo

from database import (
    calculate_reading_streak,
    get_today_reading_minutes,
    get_active_session,
    start_reading,
    stop_reading,
    finish_reading
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
# TIMEZONE
# ============================================================

SGT = ZoneInfo("Asia/Singapore")


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    /* --------------------------------------------------------
       PAGE
    -------------------------------------------------------- */

    .stApp {
        background-color: #0d0f14;
    }

    .main .block-container {
        max-width: 760px;
        padding-top: 2.5rem;
        padding-bottom: 3rem;
    }


    /* --------------------------------------------------------
       REMOVE EXTRA TOP SPACE
    -------------------------------------------------------- */

    header[data-testid="stHeader"] {
        background: transparent;
    }


    /* --------------------------------------------------------
       READTAP WELCOME CARD
    -------------------------------------------------------- */

    .welcome-card {
        background: #fffbea;
        border: 1px solid #e5dfc9;
        border-radius: 30px;
        padding: 38px 42px 34px 42px;
        margin-bottom: 34px;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.18);
        text-align: center;
    }


    .brand {
        font-size: 3.1rem;
        font-weight: 800;
        color: #263b52;
        letter-spacing: -1.5px;
        margin-bottom: 12px;
    }


    .welcome {
        font-size: 1.45rem;
        font-weight: 700;
        color: #30445a;
        margin-bottom: 18px;
    }


    .badge {
        font-size: 1.05rem;
        color: #4c4c4c;
        margin-bottom: 18px;
    }


    .last-book {
        font-size: 1.05rem;
        color: #555555;
        margin: 16px 0 28px 0;
    }


    .last-book-title {
        font-weight: 700;
        color: #3d3d3d;
    }


    /* --------------------------------------------------------
       STATS
    -------------------------------------------------------- */

    .stats-row {
        display: flex;
        justify-content: center;
        gap: 18px;
        margin-top: 10px;
    }


    .stat-box {
        flex: 1;
        background: #fffdf4;
        border-radius: 18px;
        padding: 15px 10px;
        border: 1px solid #e9e2cc;
        min-width: 0;
    }


    .stat-icon {
        font-size: 1.45rem;
        margin-bottom: 5px;
    }


    .stat-label {
        font-size: 0.82rem;
        color: #777;
        margin-bottom: 3px;
    }


    .stat-value {
        font-size: 1.05rem;
        font-weight: 750;
        color: #30445a;
    }


    /* --------------------------------------------------------
       TODAY'S READING PROGRESS
    -------------------------------------------------------- */

    .today-progress {
        margin-top: 20px;
        text-align: left;
    }


    .today-progress-label {
        display: flex;
        justify-content: space-between;
        color: #555;
        font-size: 0.85rem;
        margin-bottom: 7px;
    }


    .progress-background {
        width: 100%;
        height: 9px;
        background: #e8e4d7;
        border-radius: 20px;
        overflow: hidden;
    }


    .progress-fill {
        height: 100%;
        background: #536f8b;
        border-radius: 20px;
    }


    /* --------------------------------------------------------
       SECTION HEADINGS
    -------------------------------------------------------- */

    .section-title {
        font-size: 1.65rem;
        font-weight: 750;
        color: #f4f4f4;
        margin-top: 18px;
        margin-bottom: 18px;
    }


    /* --------------------------------------------------------
       READING BOOK INFO
    -------------------------------------------------------- */

    .book-info {
        background: #18314a;
        border-radius: 14px;
        padding: 16px 20px;
        color: #f1f4f8;
        margin: 14px 0 20px 0;
        font-size: 1rem;
    }


    .book-info-title {
        color: #ffffff;
        font-weight: 700;
    }


    /* --------------------------------------------------------
       READING SCREEN
    -------------------------------------------------------- */

    .reading-card {
        background: #fffbea;
        border-radius: 24px;
        padding: 30px;
        margin-top: 10px;
        color: #30445a;
        border: 1px solid #e5dfc9;
    }


    .reading-book {
        font-size: 1.8rem;
        font-weight: 750;
        color: #30445a;
        margin-bottom: 15px;
    }


    .reading-start {
        color: #666;
        font-size: 1rem;
    }


    /* --------------------------------------------------------
       SUMMARY
    -------------------------------------------------------- */

    .summary-card {
        background: #fffbea;
        border-radius: 26px;
        padding: 30px;
        color: #3d3d3d;
        border: 1px solid #e5dfc9;
        margin-bottom: 20px;
    }


    .summary-title {
        color: #30445a;
        font-size: 1.8rem;
        font-weight: 800;
        margin-bottom: 18px;
    }


    .summary-item {
        margin: 12px 0;
        font-size: 1rem;
    }


    .summary-label {
        color: #777;
        font-size: 0.85rem;
    }


    .summary-value {
        color: #30445a;
        font-weight: 700;
    }


    /* --------------------------------------------------------
       STREAMLIT BUTTONS
    -------------------------------------------------------- */

    .stButton > button {
        border-radius: 12px;
        padding: 0.55rem 1.1rem;
        font-weight: 600;
    }


    /* --------------------------------------------------------
       RADIO BUTTONS
    -------------------------------------------------------- */

    div[data-testid="stRadio"] label {
        font-size: 1rem;
    }


    /* --------------------------------------------------------
       MOBILE
    -------------------------------------------------------- */

    @media (max-width: 600px) {

        .main .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
            padding-top: 1.5rem;
        }

        .welcome-card {
            padding: 28px 20px;
            border-radius: 24px;
        }

        .brand {
            font-size: 2.4rem;
        }

        .welcome {
            font-size: 1.2rem;
        }

        .stats-row {
            gap: 7px;
        }

        .stat-box {
            padding: 12px 5px;
        }

        .stat-value {
            font-size: 0.9rem;
        }

        .stat-label {
            font-size: 0.7rem;
        }

        .section-title {
            font-size: 1.4rem;
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
    "summary": {},
    "awaiting_confirmation": False,
    "stopped_session": None
}.items():

    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# USER
# ============================================================

user_df = pd.read_csv("user.csv")

user = user_df.iloc[0]

nickname = str(user["nickname"])
nfc_id = str(user["nfc_id"])
student_class = str(user["class"])

goal = int(user["goal"])

last_book = str(
    user.get("current_book", "")
).strip()

if not last_book:
    last_book = "No book yet"


# ============================================================
# READING STATS
# ============================================================

streak = calculate_reading_streak(
    nickname
)

today_total = get_today_reading_minutes(
    nickname
)

remaining = max(
    goal - today_total,
    0
)

progress = (
    min(today_total / goal, 1.0)
    if goal > 0
    else 0
)

progress_percent = int(
    progress * 100
)


# ============================================================
# BADGE
# ============================================================

badge = str(
    user.get(
        "badge",
        "ReadTap Explorer"
    )
).strip()

if not badge:
    badge = "ReadTap Explorer"


# ============================================================
# AVATAR
# ============================================================

avatar = str(
    user.get(
        "avatar",
        "👩🏻"
    )
).strip()

if not avatar:
    avatar = "👩🏻"


# ============================================================
# CHECK ACTIVE SESSION
# ============================================================

active_session = get_active_session(
    nickname
)


# ============================================================
# RESTORE ACTIVE SESSION
# ============================================================

if active_session:

    status = active_session["status"]

    # --------------------------------------------------------
    # ACTIVE READING
    # --------------------------------------------------------

    if status == "active":

        st.session_state.reading = True

        st.session_state.current_book = str(
            active_session["book"]
        )

        start_value = active_session["start"]

        try:

            st.session_state.start_time = datetime.strptime(
                str(start_value),
                "%Y-%m-%d %H:%M:%S"
            ).replace(
                tzinfo=SGT
            )

        except Exception:

            st.session_state.start_time = None


    # --------------------------------------------------------
    # WAITING FOR CONFIRMATION
    # --------------------------------------------------------

    elif status == "awaiting_confirmation":

        st.session_state.awaiting_confirmation = True

        st.session_state.stopped_session = active_session


# ============================================================
# WELCOME CARD
# ============================================================

st.markdown(
    f"""
    <div class="welcome-card">

        <div class="brand">
            📚 ReadTap
        </div>

        <div class="welcome">
            {avatar} Welcome back, {nickname}!
        </div>

        <div class="badge">
            🏅 📚 {badge}
        </div>

        <div class="last-book">
            📖 Last Book:
            <span class="last-book-title">
                {last_book}
            </span>
        </div>

        <div class="stats-row">

            <div class="stat-box">
                <div class="stat-icon">🎯</div>
                <div class="stat-label">
                    Daily Goal
                </div>
                <div class="stat-value">
                    {goal} mins
                </div>
            </div>

            <div class="stat-box">
                <div class="stat-icon">🔥</div>
                <div class="stat-label">
                    Reading Streak
                </div>
                <div class="stat-value">
                    {streak} days
                </div>
            </div>

            <div class="stat-box">
                <div class="stat-icon">📖</div>
                <div class="stat-label">
                    Today's Reading
                </div>
                <div class="stat-value">
                    {today_total}/{goal}
                </div>
            </div>

        </div>

        <div class="today-progress">

            <div class="today-progress-label">
                <span>Today's progress</span>
                <span>{progress_percent}%</span>
            </div>

            <div class="progress-background">
                <div
                    class="progress-fill"
                    style="width: {progress_percent}%"
                ></div>
            </div>

        </div>

    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SUMMARY
# ============================================================

if st.session_state.show_summary:

    s = st.session_state.summary

    st.markdown(
        """
        <div class="summary-card">

            <div class="summary-title">
                🎉 Reading Complete!
            </div>

        """,
        unsafe_allow_html=True
    )

    st.write(
        f"### Great job, {nickname}! 📚"
    )

    st.markdown(
        f"""
        <div class="summary-item">
            <div class="summary-label">📖 Book</div>
            <div class="summary-value">
                {s["book"]}
            </div>
        </div>

        <div class="summary-item">
            <div class="summary-label">🕒 Started</div>
            <div class="summary-value">
                {s["start"]}
            </div>
        </div>

        <div class="summary-item">
            <div class="summary-label">🕒 Finished</div>
            <div class="summary-value">
                {s["end"]}
            </div>
        </div>

        <div class="summary-item">
            <div class="summary-label">⏱ Reading Time</div>
            <div class="summary-value">
                {s["minutes"]} minutes
            </div>
        </div>

        <div class="summary-item">
            <div class="summary-label">📖 Today's Total</div>
            <div class="summary-value">
                {s["today_total"]} / {s["goal"]} minutes
            </div>
        </div>

        </div>
        """,
        unsafe_allow_html=True
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

elif st.session_state.awaiting_confirmation:

    session = st.session_state.stopped_session

    st.markdown(
        """
        <div class="section-title">
            📚 Almost done!
        </div>
        """,
        unsafe_allow_html=True
    )

    st.write(
        "Let's confirm the book you were reading."
    )

    original_book = str(
        session["book"]
    )

    st.markdown(
        f"""
        <div class="book-info">
            📖 Current book:
            <span class="book-info-title">
                {original_book}
            </span>
        </div>
        """,
        unsafe_allow_html=True
    )

    final_book = st.text_input(
        "Book title",
        value=original_book
    )

    if st.button(
        "✅ Confirm Reading"
    ):

        result = finish_reading(
            student_name=nickname,
            final_book_title=final_book
        )

        if result is None:

            st.error(
                "Unable to save the reading session."
            )

        else:

            today_total = get_today_reading_minutes(
                nickname
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

            st.session_state.awaiting_confirmation = False

            st.session_state.stopped_session = None

            st.session_state.reading = False

            st.session_state.start_time = None

            st.session_state.current_book = ""

            st.session_state.show_summary = True

            st.rerun()


# ============================================================
# CURRENTLY READING
# ============================================================

elif st.session_state.reading:

    st.markdown(
        """
        <div class="section-title">
            📖 You're reading!
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        f"""
        <div class="reading-card">

            <div class="reading-book">
                📖 {st.session_state.current_book}
            </div>

            <div class="reading-start">
                🕒 Started at
                {(
                    st.session_state.start_time.strftime("%I:%M %p")
                    if st.session_state.start_time
                    else "—"
                )}
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    st.write("")

    if st.button(
        "✅ Finish Reading"
    ):

        end = datetime.now(
            SGT
        )

        result = stop_reading(
            student_name=nickname,
            end_time=end
        )

        if result is None:

            st.error(
                "Unable to stop the reading session."
            )

        else:

            st.session_state.reading = False

            st.session_state.start_time = None

            st.session_state.awaiting_confirmation = True

            st.session_state.stopped_session = {
                "book": result["book"],
                "start": result["start"],
                "end": result["end"],
                "minutes": result["minutes"]
            }

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


    # --------------------------------------------------------
    # CONTINUE PREVIOUS BOOK
    # --------------------------------------------------------

    if option == "Continue previous book":

        book = last_book

        if book == "No book yet":

            st.info(
                "📚 You don't have a previous book yet. "
                "Please start a new book."
            )

        else:

            st.markdown(
                f"""
                <div class="book-info">
                    📖 Continuing:
                    <span class="book-info-title">
                        {book}
                    </span>
                </div>
                """,
                unsafe_allow_html=True
            )


    # --------------------------------------------------------
    # START NEW BOOK
    # --------------------------------------------------------

    else:

        # ----------------------------------------------------
        # RECENT BOOKS
        # ----------------------------------------------------

        try:

            reading_log = pd.read_csv(
                "reading_log.csv"
            )

            if "book_title" in reading_log.columns:

                recent_books = (
                    reading_log["book_title"]
                    .dropna()
                    .astype(str)
                    .drop_duplicates()
                    .tail(5)
                    .tolist()
                )

            else:

                recent_books = []

        except Exception:

            recent_books = []


        default = (
            recent_books[-1]
            if recent_books
            else ""
        )

        book = st.text_input(
            "Book title",
            value=default,
            placeholder="e.g. Harry Potter"
        )

        if recent_books:

            st.caption(
                "📚 Recent books: "
                + ", ".join(
                    reversed(recent_books)
                )
            )


    # --------------------------------------------------------
    # START BUTTON
    # --------------------------------------------------------

    if st.button(
        "📖 Start Reading"
    ):

        if not book.strip():

            st.warning(
                "Please enter a book title."
            )

        elif (
            option == "Continue previous book"
            and book == "No book yet"
        ):

            st.warning(
                "Please choose 'Start a new book'."
            )

        else:

            book = book.strip()

            start_time = datetime.now(
                SGT
            )

            success = start_reading(
                student_name=nickname,
                nfc_id=nfc_id,
                book_title=book,
                start_time=start_time
            )

            if not success:

                st.warning(
                    "You already have an active "
                    "reading session."
                )

            else:

                st.session_state.current_book = book

                st.session_state.start_time = start_time

                st.session_state.reading = True

                st.rerun()