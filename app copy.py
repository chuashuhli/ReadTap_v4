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
# SESSION STATE
# ============================================================

for k, v in {
    "reading": False,
    "start_time": None,
    "current_book": "",
    "show_summary": False,
    "summary": {}
}.items():

    if k not in st.session_state:
        st.session_state[k] = v


# ============================================================
# USER
# ============================================================

user_df = pd.read_csv("user.csv")
user = user_df.iloc[0]

streak = calculate_reading_streak(user["nickname"])

# Today's cumulative reading
today_total = get_today_reading_minutes(user["nickname"])

goal = int(user["goal"])

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
# HEADER
# ============================================================

st.title("📚 ReadTap")

st.write(f"Welcome, **{user['nickname']}!**")

st.write(f"🔥 Reading streak: **{streak} days**")

st.divider()


# ============================================================
# TODAY'S PROGRESS
# ============================================================

st.subheader("📖 Today's Reading")

st.write(
    f"**{today_total} / {goal} minutes**"
)

progress = min(today_total / goal, 1.0) if goal > 0 else 0

st.progress(progress)

if today_total >= goal:

    st.success("🎯 Daily Goal Achieved!")

else:

    st.info(
        f"📚 {remaining} more minutes to reach today's goal."
    )


st.divider()


# ============================================================
# READING SUMMARY
# ============================================================

if st.session_state.show_summary:

    s = st.session_state.summary

    st.success("🎉 Reading Complete!")

    st.write(f"## Great job, {user['nickname']}!")

    st.write("### 📚 Book")
    st.write(s["book"])

    st.write("### 🕒 Started")
    st.write(s["start"])

    st.write("### 🕒 Finished")
    st.write(s["end"])

    st.write("### ⏱ Reading Time")
    st.write(f"**{s['minutes']} minutes**")

    st.write("### 📖 Today's Total")
    st.write(
        f"**{s['today_total']} / {s['goal']} minutes**"
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

    st.write(
        f"## 📖 {st.session_state.current_book}"
    )

    st.info(
        "Started at "
        f"{st.session_state.start_time.strftime('%I:%M %p')}"
    )

    if st.button("✅ Finish Reading"):

        st.write("Saving reading session...")

        end = datetime.now(
            ZoneInfo("Asia/Singapore")
        )

        minutes = round(
            (
                end - st.session_state.start_time
            ).total_seconds() / 60
        )

        # Save completed session
        save_reading_session(
            student_name=user["nickname"],
            nfc_id=user["nfc_id"],
            student_class=user["class"],
            book_title=st.session_state.current_book,
            start_time=st.session_state.start_time,
            end_time=end,
            minutes=minutes
        )

        # ====================================================
        # V2: CALCULATE CUMULATIVE READING FOR TODAY
        # ====================================================

        today_total = get_today_reading_minutes(
            user["nickname"]
        )

        goal = int(user["goal"])

        remaining = max(
            goal - today_total,
            0
        )

        # ====================================================
        # SAVE SUMMARY
        # ====================================================

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

    st.subheader("📚 What are you reading today?")

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
                "Recent books: "
                + ", ".join(
                    reversed(recent_books)
                )
            )

    if st.button("📖 Start Reading"):

        if not book.strip():

            st.warning(
                "Please enter a book title."
            )

        else:

            st.session_state.current_book = book

            user_df.loc[0, "current_book"] = book

            user_df.to_csv(
                "user.csv",
                index=False
            )

            st.session_state.start_time = datetime.now(
                ZoneInfo("Asia/Singapore")
            )

            st.session_state.reading = True

            st.rerun()
