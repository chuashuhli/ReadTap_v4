import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

from database import (
    save_reading_session,
    calculate_reading_streak,
    get_today_reading_minutes
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
# CUSTOM DESIGN
# ============================================================

st.markdown(
    """
    <style>

    /* ---------- Overall page ---------- */

    .stApp {
        background: #fffdf2;
    }

    .main .block-container {
        max-width: 850px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }


    /* ---------- Main title ---------- */

    .readtap-title {
        text-align: center;
        font-size: 3.8rem;
        font-weight: 800;
        color: #26384a;
        margin-bottom: 0.2rem;
        letter-spacing: -2px;
    }

    .readtap-subtitle {
        text-align: center;
        font-size: 1.25rem;
        color: #59636e;
        margin-bottom: 2rem;
    }


    /* ---------- Welcome card ---------- */

    .welcome-card {
        background: #fff9df;
        border: 2px solid #e7dfc7;
        border-radius: 28px;
        padding: 2rem 2rem 1.7rem 2rem;
        text-align: center;
        box-shadow: 0 8px 20px rgba(0,0,0,0.06);
        margin-bottom: 2rem;
    }

    .welcome-name {
        font-size: 2rem;
        font-weight: 700;
        color: #26384a;
        margin-bottom: 0.8rem;
    }

    .badge {
        font-size: 1.25rem;
        color: #59636e;
        margin-bottom: 1.3rem;
    }

    .profile-line {
        font-size: 1.15rem;
        color: #59636e;
        margin: 0.65rem 0;
    }

    .profile-value {
        font-weight: 700;
        color: #414141;
    }


    /* ---------- Section headings ---------- */

    .section-title {
        font-size: 2rem;
        font-weight: 800;
        color: #26384a;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }


    /* ---------- Goal card ---------- */

    .goal-card {
        background: #fff9df;
        border-radius: 24px;
        border: 2px solid #e7dfc7;
        padding: 1.5rem 1.7rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 5px 15px rgba(0,0,0,0.04);
    }

    .goal-title {
        font-size: 1.4rem;
        font-weight: 700;
        color: #26384a;
        margin-bottom: 0.5rem;
    }

    .goal-number {
        font-size: 2rem;
        font-weight: 800;
        color: #26384a;
    }

    .goal-remaining {
        font-size: 1.1rem;
        margin-top: 0.8rem;
        color: #59636e;
    }


    /* ---------- Book section ---------- */

    .book-card {
        background: white;
        border: 2px solid #e7dfc7;
        border-radius: 24px;
        padding: 1.5rem 1.7rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 5px 15px rgba(0,0,0,0.04);
    }


    /* ---------- Reading card ---------- */

    .reading-card {
        background: #fff9df;
        border: 2px solid #e7dfc7;
        border-radius: 24px;
        padding: 1.7rem;
        margin-top: 1rem;
        margin-bottom: 1.5rem;
    }

    .reading-book {
        font-size: 1.8rem;
        font-weight: 800;
        color: #26384a;
        margin-bottom: 0.8rem;
    }


    /* ---------- Completion card ---------- */

    .complete-card {
        background: #eafff0;
        border: 2px solid #b8e4c7;
        border-radius: 24px;
        padding: 1.8rem;
        text-align: center;
        margin-bottom: 1.5rem;
    }

    .complete-title {
        font-size: 2rem;
        font-weight: 800;
        color: #245c3a;
    }

    .complete-total {
        font-size: 1.4rem;
        font-weight: 700;
        color: #245c3a;
        margin-top: 0.5rem;
    }


    /* ---------- Buttons ---------- */

    .stButton > button {
        width: 100%;
        border-radius: 18px;
        min-height: 3.2rem;
        font-size: 1.1rem;
        font-weight: 700;
    }


    /* ---------- Radio buttons ---------- */

    div[role="radiogroup"] {
        gap: 0.5rem;
    }


    /* ---------- Divider ---------- */

    hr {
        margin-top: 1.5rem;
        margin-bottom: 1.5rem;
        border-color: #e7dfc7;
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

streak = calculate_reading_streak(
    user["nickname"]
)

today_total = get_today_reading_minutes(
    user["nickname"]
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
# HEADER
# ============================================================

st.markdown(
    '<div class="readtap-title">📚 ReadTap</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="readtap-subtitle">'
    'Small taps. Big reading adventures.'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# WELCOME CARD
# ============================================================

st.markdown(
    f"""
    <div class="welcome-card">

        <div class="welcome-name">
            👋 Welcome back, {user['nickname']}!
        </div>

        <div class="badge">
            🏅 📚 ReadTap Explorer
        </div>

        <div class="profile-line">
            📖 Last Book:
            <span class="profile-value">
                {user['current_book']}
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
# TODAY'S PROGRESS
# ============================================================

st.markdown(
    '<div class="section-title">📖 Today\'s Reading</div>',
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div class="goal-card">

        <div class="goal-title">
            🎯 Daily Reading Goal
        </div>

        <div class="goal-number">
            {today_total} / {goal} minutes
        </div>

    </div>
    """,
    unsafe_allow_html=True
)

progress = (
    min(today_total / goal, 1.0)
    if goal > 0
    else 0
)

st.progress(progress)

if today_total >= goal:

    st.success(
        "🎯 Daily Goal Achieved! Amazing reading today!"
    )

else:

    st.info(
        f"📚 {remaining} more minutes "
        "to reach today's goal."
    )


st.divider()


# ============================================================
# READING SUMMARY
# ============================================================

if st.session_state.show_summary:

    summary = st.session_state.summary

    st.markdown(
        """
        <div class="complete-card">

            <div class="complete-title">
                🎉 Reading Complete!
            </div>

            <div class="complete-total">
                Great job!
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        f"## 📚 {summary['book']}"
    )

    st.write(
        f"🕒 **Started:** {summary['start']}"
    )

    st.write(
        f"🕒 **Finished:** {summary['end']}"
    )

    st.write(
        f"⏱️ **This session:** "
        f"{summary['minutes']} minutes"
    )

    st.markdown(
        f"""
        <div class="goal-card">

            <div class="goal-title">
                📖 Today's Reading
            </div>

            <div class="goal-number">
                {summary['today_total']}
                / {summary['goal']} minutes
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    if summary["today_total"] >= summary["goal"]:

        st.success(
            "🎯 You reached today's reading goal!"
        )

        st.balloons()

    else:

        st.info(
            f"📚 {summary['remaining']} more minutes "
            "to reach today's goal."
        )

    if st.button(
        "📚 Start Another Reading Session"
    ):

        st.session_state.show_summary = False

        st.rerun()


# ============================================================
# CURRENTLY READING
# ============================================================

elif st.session_state.reading:

    st.markdown(
        '<div class="section-title">📖 Reading Now</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        f"""
        <div class="reading-card">

            <div class="reading-book">
                📚 {st.session_state.current_book}
            </div>

            <div>
                🕒 Started at
                <strong>
                    {st.session_state.start_time.strftime('%I:%M %p')}
                </strong>
            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button(
        "✅ Finish Reading"
    ):

        end = datetime.now(
            ZoneInfo("Asia/Singapore")
        )

        minutes = round(
            (
                end
                - st.session_state.start_time
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
        # V2 CUMULATIVE DAILY TOTAL
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

            "book":
                st.session_state.current_book,

            "start":
                st.session_state.start_time.strftime(
                    "%I:%M %p"
                ),

            "end":
                end.strftime(
                    "%I:%M %p"
                ),

            "minutes":
                minutes,

            "today_total":
                today_total,

            "goal":
                goal,

            "remaining":
                remaining
        }

        st.session_state.reading = False

        st.session_state.show_summary = True

        st.rerun()


# ============================================================
# START READING
# ============================================================

else:

    st.markdown(
        '<div class="section-title">'
        '📚 What are you reading today?'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="book-card">',
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

        st.info(
            f"📖 Continuing: **{book}**"
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
                "📚 Recent books: "
                + ", ".join(
                    reversed(recent_books)
                )
            )

    st.markdown(
        '</div>',
        unsafe_allow_html=True
    )

    if st.button(
        "📖 Start Reading"
    ):

        if not book.strip():

            st.warning(
                "Please enter a book title."
            )

        else:

            st.session_state.current_book = (
                book.strip()
            )

            user_df.loc[
                0,
                "current_book"
            ] = book.strip()

            user_df.to_csv(
                "user.csv",
                index=False
            )

            st.session_state.start_time = (
                datetime.now(
                    ZoneInfo("Asia/Singapore")
                )
            )

            st.session_state.reading = True

            st.rerun()