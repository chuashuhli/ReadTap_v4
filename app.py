

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from database import save_reading_session, calculate_reading_streak

st.set_page_config(page_title="ReadTap", page_icon="📚", layout="centered")

# ---------- Session ----------
for k,v in {
    "reading":False,
    "start_time":None,
    "current_book":"",
    "show_summary":False,
    "summary":{}
}.items():
    if k not in st.session_state:
        st.session_state[k]=v

# ---------- User ----------
user_df = pd.read_csv("user.csv")
user = user_df.iloc[0]
streak = calculate_reading_streak(user["nickname"])

# ---------- Recent books ----------
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
    recent_books=[]

st.markdown("""
<style>

.main-card{
    background: linear-gradient(135deg,#FFF8DC,#FFFDF5);
    padding:30px;
    border-radius:30px;
    border:2px solid #E5E7EB;
    box-shadow:0 6px 18px rgba(0,0,0,0.10);
    text-align:center;
}

/* Main title */
.main-card h1{
    color:#2C3E50 !important;
    font-size:48px;
    font-weight:700;
}

/* Welcome message */
.main-card h2{
    color:#34495E !important;
    font-size:30px;
    font-weight:600;
}

/* All other text */
.main-card p{
    color:#555555 !important;
    font-size:20px;
    line-height:1.8;
}

</style>
""",unsafe_allow_html=True)

st.markdown(f"""
<div class="main-card">
<h1>📚 ReadTap</h1>
<h3 style="color:#2C3E50;">
    {user["avatar"]} Welcome back, {user["nickname"]}!
</h3>
<p>🏅 {user["badge"]}</p>
<p>📖 Last Book: <b>{user["current_book"]}</b></p>
<p>🎯 Daily Goal: {user["goal"]} mins</p>
<p>🔥 Reading Streak: {streak} days</p>
</div>
""",unsafe_allow_html=True)

if st.session_state.show_summary:
    s=st.session_state.summary
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
    if s["minutes"]>=int(user["goal"]):
        st.success("🎯 Daily Goal Achieved!")
    else:
        st.info(f"{int(user['goal'])-s['minutes']} more minutes to reach your goal.")
    if st.button("📚 Start Another Reading Session"):
        st.session_state.show_summary=False
        st.rerun()

elif st.session_state.reading:
    st.success("📚 Enjoy your reading!")
    st.write(f"## 📖 {st.session_state.current_book}")
    st.info(f"Started at {st.session_state.start_time.strftime('%I:%M %p')}")
    if st.button("✅ Finish Reading"):
        st.write("Saving reading session...")
        end=datetime.now(ZoneInfo("Asia/Singapore"))
        minutes=round((end-st.session_state.start_time).total_seconds()/60)
        save_reading_session(
            student_name=user["nickname"],
            nfc_id=user["nfc_id"],
            student_class=user["class"],
            book_title=st.session_state.current_book,
            start_time=st.session_state.start_time,
            end_time=end,
            minutes=minutes
        )
        st.session_state.summary={
            "book":st.session_state.current_book,
            "start":st.session_state.start_time.strftime("%I:%M %p"),
            "end":end.strftime("%I:%M %p"),
            "minutes":minutes
        }
        st.session_state.reading=False
        st.session_state.show_summary=True
        st.rerun()
else:
    st.subheader("📚 What are you reading today?")
    option=st.radio("Choose an option",
                    ("Continue previous book","Start a new book"))
    if option=="Continue previous book":
        book=user["current_book"]
        st.info(f"📖 Continuing: **{book}**")
    else:
        default = recent_books[-1] if recent_books else ""
        book=st.text_input("Book title",value=default)
        if recent_books:
            st.caption("Recent books: " + ", ".join(reversed(recent_books)))

    if st.button("📖 Start Reading"):
        if not book.strip():
            st.warning("Please enter a book title.")
        else:
            st.session_state.current_book=book
            user_df.loc[0,"current_book"]=book
            user_df.to_csv("user.csv",index=False)
            st.session_state.start_time=datetime.now(ZoneInfo("Asia/Singapore"))
            st.session_state.reading=True
            st.rerun()
