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
# SESSION STATE
# ============================================================

for k, v in {
    "reading": False,
    "start_time": None,
    "current_book": "",
    "show_summary": False,
    "summary": {},
    "awaiting_confirmation": False,
    "stopped_session": None
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
student_class = str(user["class"])
goal = int(user["goal"])


# ============================================================
# CHECK ACTIVE SESSION FROM GOOGLE SHEETS
# ============================================================

active_session = get_active_session(nickname)


# ============================================================
# RESTORE ACTIVE SESSION
# ============================================================

if active_session:

    status = active_session["status"]

    # --------------------------------------------------------
    # Active reading
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
    # Waiting for book confirmation
    # --------------------------------------------------------

    elif status == "awaiting_confirmation":

        st.session_state.awaiting_confirmation = True

        st.session_state.stopped_session = active_session


# ============================================================
# STREAK
# ============================================================

streak = calculate_reading_streak(
    nickname
)


# ============================================================
# TODAY'S CUMULATIVE READING
# ============================================================

today_total = get_today_reading_minutes(
    nickname
)

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

st.title("📚 ReadTap")

st.write(
    f"Welcome, **{nickname}!**"
)

st.write(
    f"🔥 Reading streak: **{streak} days**"
)

st.divider()


# ============================================================
# TODAY'S PROGRESS
# ============================================================

st.subheader("📖 Today's Reading")

st.write(
    f"**{today_total} / {goal} minutes**"
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


st.divider()


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

    st.write(
        s["book"]
    )

    st.write("### 🕒 Started")

    st.write(
        s["start"]
    )

    st.write("### 🕒 Finished")

    st.write(
        s["end"]
    )

    st.write("### ⏱ Reading Time")

    st.write(
        f"**{s['minutes']} minutes**"
    )

    st.write("### 📖 Today's Total")

    st.write(
        f"**{s['today_total']} / "
        f"{s['goal']} minutes**"
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

    st.success(
        "⏱ Reading session stopped!"
    )

    st.write(
        "### 📚 Confirm your book"
    )

    original_book = str(
        session["book"]
    )

    st.write(
        f"Current book: **{original_book}**"
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

            # ----------------------------------------------
            # Recalculate today's total
            # ----------------------------------------------

            today_total = get_today_reading_minutes(
                nickname
            )

            remaining = max(
                goal - today_total,
                0
            )

            # ----------------------------------------------
            # Save summary
            # ----------------------------------------------

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

    st.success(
        "📚 Enjoy your reading!"
    )

    st.write(
        f"## 📖 {st.session_state.current_book}"
    )

    if st.session_state.start_time:

        st.info(
            "Started at "
            f"{st.session_state.start_time.strftime('%I:%M %p')}"
        )

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

    st.subheader(
        "📚 What are you reading today?"
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

        book = str(
            user["current_book"]
        )

        st.info(
            f"📖 Continuing: **{book}**"
        )


    # --------------------------------------------------------
    # START NEW BOOK
    # --------------------------------------------------------

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

    if st.button(
        "📖 Start Reading"
    ):

        if not book.strip():

            st.warning(
                "Please enter a book title."
            )

        else:

            start_time = datetime.now(
                SGT
            )

            success = start_reading(
                student_name=nickname,
                nfc_id=nfc_id,
                book_title=book.strip(),
                start_time=start_time
            )

            if not success:

                st.warning(
                    "You already have an active "
                    "reading session."
                )

            else:

                st.session_state.current_book = (
                    book.strip()
                )

                st.session_state.start_time = (
                    start_time
                )

                st.session_state.reading = True

                st.rerun()