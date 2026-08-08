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
# CUSTOM CSS
# ============================================================

st.markdown(
    """
<style>

/* =========================
   PAGE
   ========================= */

.stApp {
    background-color: #fffdf2;
}

.main .block-container {
    max-width: 850px;
    padding-top: 2rem;
    padding-bottom: 4rem;
}


/* =========================
   TITLE
   ========================= */

.readtap-title {
    text-align: center;
    font-size: 4rem;
    font-weight: 800;
    color: #26384a;
    margin-bottom: 0.2rem;
}

.readtap-subtitle {
    text-align: center;
    font-size: 1.25rem;
    color: #59636e;
    margin-bottom: 2rem;
}


/* =========================
   CARDS
   ========================= */

div[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: #fff9df;
    border: 2px solid #e7dfc7;
    border-radius: 24px;
    padding: 1.2rem;
    box-shadow: 0 6px 16px rgba(0,0,0,0.05);
}


/* =========================
   WELCOME CARD
   ========================= */

.welcome-name {
    text-align: center;
    font-size: 2rem;
    font-weight: 800;
    color: #26384a;
}

.welcome-badge {
    text-align: center;
    font-size: 1.2rem;
    color: #59636e;
    margin-top: 0.5rem;
    margin-bottom: 1.5rem;
}

.profile-line {
    text-align: center;
    font-size: 1.15rem;
    color: #59636e;
    margin: 0.8rem 0;
}

.profile-value {
    font-weight: 700;
    color: #414141;
}


/* =========================
   SECTION HEADINGS
   ========================= */

.section-title {
    font-size: 2rem;
    font-weight: 800;
    color: #26384a;
    margin-top: 1.5rem;
    margin-bottom: 1rem;
}


/* =========================
   GOAL NUMBER
   ========================= */

.goal-number {
    text-align: center;
    font-size: 2rem;
    font-weight: 800;
    color: #26384a;
}

.goal-label {
    text-align: center;
    font-size: 1.1rem;
    color: #59636e;
}


/* =========================
   BUTTONS
   ========================= */

.stButton > button {
    width: 100%;
    min-height: 3.2rem;
    border-radius: 18px;
    font-size: 1.1rem;
    font-weight: 700;
}


/* =========================
   DIVIDER
   ========================= */

hr {
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

with st.container(border=True):

    st.markdown(
        '<div class="welcome-name">'
        f'👋 Welcome back, {user["nickname"]}!'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="welcome-badge">'
        '🏅 📚 ReadTap Explorer'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="profile-line">'
        '📖 Last Book: '
        f'<span class="profile-value">'
        f'{user["current_book"]}'
        '</span>'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="profile-line">'
        '🎯 Daily Goal: '
        f'<span class="profile-value">'
        f'{goal} mins'
        '</span>'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="profile-line">'
        '🔥 Reading Streak: '
        f'<span class="profile-value">'
        f'{streak} days'
        '</span>'
        '</div>',
        unsafe_allow_html=True
    )


# ============================================================
# TODAY'S READING
# ============================================================

st.markdown(
    '<div class="section-title">'
    '📖 Today\'s Reading'
    '</div>',
    unsafe_allow_html=True
)

with st.container(border=True):

    st.markdown(
        '<div class="goal-label">'
        '🎯 Daily Reading Goal'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="goal-number">'
        f'{today_total} / {goal} minutes'
        '</div>',
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

    st.success(
        "🎉 Reading Complete!"
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

    with st.container(border=True):

        st.markdown(
            '<div class="goal-label">'
            '📖 Total Reading Today'
            '</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="goal-number">'
            f'{summary["today_total"]} / '
            f'{summary["goal"]} minutes'
            '</div>',
            unsafe_allow_html=True
        )

        summary_progress = (
            min(
                summary["today_total"]
                / summary["goal"],
                1.0
            )
            if summary["goal"] > 0
            else 0
        )

        st.progress(summary_progress)

    if summary["today_total"] >= summary["goal"]:

        st.success(
            "🎯 You reached today's reading goal!"
        )

        st.balloons()

    else:

        st.info(
            f'📚 {summary["remaining"]} more minutes '
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
        '<div class="section-title">'
        '📖 Reading Now'
        '</div>',
        unsafe_allow_html=True
    )

    with st.container(border=True):

        st.markdown(
            f"## 📚 {st.session_state.current_book}"
        )

        st.write(
            "🕒 Started at "
            f"**{st.session_state.start_time.strftime('%I:%M %p')}**"
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
        # V2 CUMULATIVE TOTAL
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
        # SUMMARY
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

    with st.container(border=True):

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