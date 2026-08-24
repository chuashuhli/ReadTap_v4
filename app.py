import streamlit as st
import pandas as pd
import numpy as np
import zxingcpp
import requests
from PIL import Image
from PIL import ImageEnhance

from PIL import Image
from datetime import datetime
from zoneinfo import ZoneInfo

from database import (
    calculate_reading_streak,
    get_today_reading_minutes,
    get_active_session,
    start_reading,
    stop_reading,
    finish_reading,
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="ReadTap",
    page_icon="📚",
    layout="centered",
)


# ============================================================
# TIMEZONE
# ============================================================

SGT = ZoneInfo("Asia/Singapore")


# ============================================================
# ISBN / BOOK LOOKUP
# ============================================================

def is_valid_isbn13(isbn):
    """
    Validate an ISBN-13.
    """

    isbn = (
        str(isbn)
        .replace("-", "")
        .replace(" ", "")
        .strip()
    )

    if len(isbn) != 13:
        return False

    if not isbn.isdigit():
        return False

    if not isbn.startswith(("978", "979")):
        return False

    total = 0

    for i, digit in enumerate(isbn):

        value = int(digit)

        if i % 2 == 0:
            total += value
        else:
            total += value * 3

    return total % 10 == 0

def lookup_book_by_isbn(isbn):
    """
    Look up book information using the ISBN.

    Tries Google Books first,
    then Open Library as a fallback.
    """

    isbn = (
        str(isbn)
        .replace("-", "")
        .replace(" ", "")
        .strip()
    )

    # ========================================================
    # GOOGLE BOOKS
    # ========================================================

    try:

        url = (
            "https://www.googleapis.com/books/v1/volumes"
            f"?q=isbn:{isbn}"
        )

        response = requests.get(
            url,
            timeout=10,
        )

        if response.status_code == 200:

            data = response.json()

            items = data.get(
                "items",
                []
            )

            if items:

                volume_info = items[0].get(
                    "volumeInfo",
                    {}
                )

                title = str(
                    volume_info.get(
                        "title",
                        ""
                    )
                ).strip()

                authors = volume_info.get(
                    "authors",
                    []
                )

                author = (
                    ", ".join(authors)
                    if authors
                    else ""
                )

                if title:

                    return {
                        "isbn": isbn,
                        "title": title,
                        "author": author,
                    }

    except Exception:
        pass


    # ========================================================
    # OPEN LIBRARY FALLBACK
    # ========================================================

    try:

        url = (
            "https://openlibrary.org/api/books"
            f"?bibkeys=ISBN:{isbn}"
            "&format=json"
            "&jscmd=data"
        )

        response = requests.get(
            url,
            timeout=10,
        )

        if response.status_code == 200:

            data = response.json()

            book = data.get(
                f"ISBN:{isbn}"
            )

            if book:

                title = str(
                    book.get(
                        "title",
                        ""
                    )
                ).strip()

                authors_data = book.get(
                    "authors",
                    []
                )

                authors = []

                for author_data in authors_data:

                    name = author_data.get(
                        "name",
                        ""
                    ).strip()

                    if name:
                        authors.append(name)

                author = ", ".join(
                    authors
                )

                if title:

                    return {
                        "isbn": isbn,
                        "title": title,
                        "author": author,
                    }

    except Exception:
        pass


    # ========================================================
    # NOTHING FOUND
    # ========================================================

    return None

    # ----------------------------------------------------
    # Create several versions of the image
    # ----------------------------------------------------

    images_to_try = []

    # Original
    images_to_try.append(image)

    # Larger image
    scale = 2

    enlarged = image.resize(
        (
            image.width * scale,
            image.height * scale,
        )
    )

    images_to_try.append(
        enlarged
    )

    # Grayscale
    gray = enlarged.convert(
        "L"
    )

    images_to_try.append(
        gray
    )

    # High contrast
    contrast = ImageEnhance.Contrast(
        gray
    ).enhance(2.0)

    images_to_try.append(
        contrast
    )

    # Sharpen
    sharp = ImageEnhance.Sharpness(
        contrast
    ).enhance(2.0)

    images_to_try.append(
        sharp
    )

    # ----------------------------------------------------
    # Try decoding every version
    # ----------------------------------------------------

    for test_image in images_to_try:

        image_array = np.array(
            test_image
        )

        barcodes = zxingcpp.read_barcodes(
            image_array,
            try_rotate=True,
            try_downscale=False,
            try_invert=True,
        )

        for barcode in barcodes:

            raw = str(
                barcode.text or ""
            ).strip()

            isbn = (
                raw
                .replace("-", "")
                .replace(" ", "")
            )

            # Temporary diagnostic information
            st.write(
                f"🔎 Detected: {isbn} | "
                f"Format: {barcode.format} | "
                f"Length: {len(isbn)} | "
                f"Starts 978/979: "
                f"{isbn.startswith(('978', '979'))} | "
                f"Valid ISBN-13: "
                f"{is_valid_isbn13(isbn)}"
            )

            # ------------------------------------------------
            # Accept valid ISBN-13
            # ------------------------------------------------

            if (
                len(isbn) == 13
                and isbn.isdigit()
                and isbn.startswith(
                    ("978", "979")
                )
                and is_valid_isbn13(
                    isbn
                )
            ):
                 return isbn

        return None

except Exception as e:

    st.error(
        f"Barcode scanner error: {e}"
    )

    return None


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
<style>

.stApp {
    background-color: #0d0f14;
}

.main .block-container {
    max-width: 760px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}

/* Welcome card */

.welcome-card {
    background: #fffbea;
    border: 1px solid #e5dfc9;
    border-radius: 30px;
    padding: 34px 38px 30px 38px;
    margin-bottom: 36px;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.18);
    text-align: center;
}

.brand {
    font-size: 3rem;
    line-height: 1.1;
    font-weight: 800;
    color: #263b52;
    letter-spacing: -1.5px;
    margin-bottom: 18px;
}

.welcome {
    font-size: 1.35rem;
    font-weight: 700;
    color: #30445a;
    margin-bottom: 14px;
}

.badge {
    font-size: 1rem;
    color: #555555;
    margin-bottom: 18px;
}

.last-book {
    font-size: 1rem;
    color: #555555;
    margin: 14px 0 26px 0;
}

.last-book-title {
    font-weight: 700;
    color: #3d3d3d;
}

/* Stats */

.stats-row {
    display: flex;
    justify-content: center;
    gap: 12px;
    margin-top: 8px;
}

.stat-box {
    flex: 1;
    background: #fffdf4;
    border: 1px solid #e9e2cc;
    border-radius: 18px;
    padding: 13px 7px;
    min-width: 0;
}

.stat-icon {
    font-size: 1.3rem;
    margin-bottom: 4px;
}

.stat-label {
    font-size: 0.78rem;
    color: #777777;
    margin-bottom: 3px;
}

.stat-value {
    font-size: 0.98rem;
    font-weight: 750;
    color: #30445a;
}

/* Progress */

.today-progress {
    margin-top: 20px;
    text-align: left;
}

.today-progress-label {
    display: flex;
    justify-content: space-between;
    color: #666666;
    font-size: 0.82rem;
    margin-bottom: 7px;
}

.progress-background {
    width: 100%;
    height: 8px;
    background: #e8e4d7;
    border-radius: 20px;
    overflow: hidden;
}

.progress-fill {
    height: 100%;
    background: #536f8b;
    border-radius: 20px;
}

/* Section heading */

.section-title {
    font-size: 1.6rem;
    font-weight: 750;
    color: #f4f4f4;
    margin-top: 12px;
    margin-bottom: 18px;
}

/* Book information */

.book-info {
    background: #18314a;
    border-radius: 14px;
    padding: 15px 18px;
    color: #f1f4f8;
    margin: 14px 0 20px 0;
    font-size: 1rem;
}

.book-info-title {
    color: #ffffff;
    font-weight: 700;
}

/* Reading card */

.reading-card {
    background: #fffbea;
    border-radius: 24px;
    padding: 28px;
    margin-top: 10px;
    color: #30445a;
    border: 1px solid #e5dfc9;
}

.reading-book {
    font-size: 1.7rem;
    font-weight: 750;
    color: #30445a;
    margin-bottom: 12px;
}

.reading-start {
    color: #666666;
    font-size: 1rem;
}

/* Summary */

.summary-card {
    background: #fffbea;
    border-radius: 26px;
    padding: 28px;
    color: #3d3d3d;
    border: 1px solid #e5dfc9;
    margin-bottom: 20px;
}

.summary-title {
    color: #30445a;
    font-size: 1.75rem;
    font-weight: 800;
    margin-bottom: 16px;
}

.summary-item {
    margin: 11px 0;
    font-size: 1rem;
}

.summary-label {
    color: #777777;
    font-size: 0.84rem;
}

.summary-value {
    color: #30445a;
    font-weight: 700;
}

/* Buttons */

.stButton > button {
    border-radius: 12px;
    padding: 0.55rem 1.1rem;
    font-weight: 600;
}

/* Radio */

div[data-testid="stRadio"] label {
    font-size: 1rem;
}

/* Mobile */

@media (max-width: 600px) {

    .main .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
        padding-top: 1.2rem;
    }

    .welcome-card {
        padding: 27px 18px 24px 18px;
        border-radius: 24px;
    }

    .brand {
        font-size: 2.35rem;
    }

    .welcome {
        font-size: 1.18rem;
    }

    .stats-row {
        gap: 6px;
    }

    .stat-box {
        padding: 11px 4px;
    }

    .stat-value {
        font-size: 0.82rem;
    }

    .stat-label {
        font-size: 0.68rem;
    }

    .section-title {
        font-size: 1.4rem;
    }

}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "reading": False,
    "start_time": None,
    "current_book": "",
    "show_summary": False,
    "summary": {},
    "awaiting_confirmation": False,
    "stopped_session": None,

    # ISBN scanner
    "scanning_isbn": False,
    "scanned_book": None,
}

for key, value in defaults.items():

    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# USER
# ============================================================

user_df = pd.read_csv(
    "user.csv"
)

user = user_df.iloc[0]

nickname = str(
    user["nickname"]
)

nfc_id = str(
    user["nfc_id"]
)

student_class = str(
    user["class"]
)

goal = int(
    user["goal"]
)

last_book = str(
    user.get(
        "current_book",
        ""
    )
).strip()

if (
    not last_book
    or last_book.lower() == "nan"
):

    last_book = "No book yet"


# ============================================================
# USER DISPLAY DETAILS
# ============================================================

badge = str(
    user.get(
        "badge",
        "ReadTap Explorer"
    )
).strip()

if (
    not badge
    or badge.lower() == "nan"
):

    badge = "ReadTap Explorer"


avatar = str(
    user.get(
        "avatar",
        "👩🏻"
    )
).strip()

if (
    not avatar
    or avatar.lower() == "nan"
):

    avatar = "👩🏻"


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
    min(
        today_total / goal,
        1.0
    )
    if goal > 0
    else 0
)

progress_percent = int(
    progress * 100
)


# ============================================================
# ACTIVE SESSION RECOVERY
# ============================================================

active_session = get_active_session(
    nickname
)

if active_session:

    status = active_session.get(
        "status"
    )

    if status == "active":

        st.session_state.reading = True

        st.session_state.current_book = str(
            active_session.get(
                "book",
                ""
            )
        )

        start_value = active_session.get(
            "start"
        )

        if start_value:

            if isinstance(
                start_value,
                datetime
            ):

                st.session_state.start_time = (
                    start_value.astimezone(SGT)
                    if start_value.tzinfo
                    else start_value.replace(
                        tzinfo=SGT
                    )
                )

            else:

                try:

                    parsed = datetime.strptime(
                        str(start_value),
                        "%Y-%m-%d %H:%M:%S",
                    )

                    st.session_state.start_time = (
                        parsed.replace(
                            tzinfo=SGT
                        )
                    )

                except ValueError:

                    st.session_state.start_time = None

    elif status == "awaiting_confirmation":

        st.session_state.awaiting_confirmation = True

        st.session_state.stopped_session = (
            active_session
        )


# ============================================================
# WELCOME CARD
# ============================================================

welcome_html = f"""
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

<div class="stat-icon">
🎯
</div>

<div class="stat-label">
Daily Goal
</div>

<div class="stat-value">
{goal} mins
</div>

</div>

<div class="stat-box">

<div class="stat-icon">
🔥
</div>

<div class="stat-label">
Reading Streak
</div>

<div class="stat-value">
{streak} days
</div>

</div>

<div class="stat-box">

<div class="stat-icon">
📖
</div>

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
<span>
Today's progress
</span>

<span>
{progress_percent}%
</span>

</div>

<div class="progress-background">

<div
class="progress-fill"
style="width:{progress_percent}%;">
</div>

</div>

</div>

</div>
"""

st.markdown(
    welcome_html,
    unsafe_allow_html=True
)


# ============================================================
# SUMMARY
# ============================================================

if st.session_state.show_summary:

    s = st.session_state.summary

    summary_html = f"""
<div class="summary-card">

<div class="summary-title">
🎉 Reading Complete!
</div>

<div class="summary-item">

<div class="summary-label">
📖 Book
</div>

<div class="summary-value">
{s["book"]}
</div>

</div>

<div class="summary-item">

<div class="summary-label">
🕒 Started
</div>

<div class="summary-value">
{s["start"]}
</div>

</div>

<div class="summary-item">

<div class="summary-label">
🕒 Finished
</div>

<div class="summary-value">
{s["end"]}
</div>

</div>

<div class="summary-item">

<div class="summary-label">
⏱ Reading Time
</div>

<div class="summary-value">
{s["minutes"]} minutes
</div>

</div>

<div class="summary-item">

<div class="summary-label">
📖 Today's Total
</div>

<div class="summary-value">
{s["today_total"]} / {s["goal"]} minutes
</div>

</div>

</div>
"""

    st.markdown(
        summary_html,
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

    session = (
        st.session_state.stopped_session
    )

    st.markdown(
        '<div class="section-title">'
        '📚 Almost done!'
        '</div>',
        unsafe_allow_html=True,
    )

    st.write(
        "Let's confirm the book you were reading."
    )


    # ========================================================
    # ISBN SCANNER
    # ========================================================

    if st.session_state.scanning_isbn:

        st.markdown(
            "### 📷 Scan ISBN"
        )

        st.caption(
            "Point your camera at the barcode "
            "on the back of the physical book."
        )

        camera_image = st.camera_input(
            "Take a photo of the ISBN barcode",
            key="isbn_camera",resolution="1080p",
        )

        if camera_image:

            with st.spinner(
                "🔎 Reading barcode..."
            ):

                isbn = scan_isbn_from_image(
                    camera_image
                )

            if isbn:

                st.success(
                    f"ISBN detected: {isbn}"
                )

                with st.spinner(
                    "📚 Finding your book..."
                ):

                    book = lookup_book_by_isbn(
                        isbn
                    )

                if book:

                    st.session_state.scanned_book = (
                        book
                    )

                    st.session_state.scanning_isbn = (
                        False
                    )

                    st.rerun()

                else:

                    st.error(
                        "ISBN detected, but I couldn't "
                        "find this book."
                    )

                    st.info(
                        "You can enter the book title "
                        "manually instead."
                    )

                    if st.button(
                        "✏️ Enter Title Manually",
                        use_container_width=True,
                    ):

                        st.session_state.scanning_isbn = (
                            False
                        )

                        st.rerun()

            else:

                st.warning(
                    "I couldn't detect an ISBN barcode "
                    "in that photo."
                )

                st.caption(
                    "Try again with the barcode clearly "
                    "visible and well lit."
                )

        if st.button(
            "← Back",
            use_container_width=True,
        ):

            st.session_state.scanning_isbn = False

            st.rerun()


    # ========================================================
    # BOOK FOUND
    # ========================================================

    elif st.session_state.scanned_book:

        book = (
            st.session_state.scanned_book
        )

        st.markdown(
            '<div class="book-info">'
            '📚 Book found'
            '</div>',
            unsafe_allow_html=True,
        )

        reading_html = f"""
<div class="reading-card">

<div class="reading-book">
📖 {book["title"]}
</div>

<div class="reading-start">
✍️ {book["author"] or "Author unknown"}
</div>

<div class="reading-start">
🔢 ISBN: {book["isbn"]}
</div>

</div>
"""

        st.markdown(
            reading_html,
            unsafe_allow_html=True
        )

        st.write("")

        if st.button(
            "✅ Use This Book",
            use_container_width=True,
        ):

            result = finish_reading(
                student_name=nickname,
                final_book_title=book["title"],
            )

            if result is None:

                st.error(
                    "Unable to save the reading session."
                )

            else:

                today_total = (
                    get_today_reading_minutes(
                        nickname
                    )
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
                    "remaining": remaining,
                }

                st.session_state.scanned_book = None
                st.session_state.scanning_isbn = False
                st.session_state.awaiting_confirmation = False
                st.session_state.stopped_session = None
                st.session_state.reading = False
                st.session_state.start_time = None
                st.session_state.current_book = ""
                st.session_state.show_summary = True

                st.rerun()


        if st.button(
            "🔄 Scan Again",
            use_container_width=True,
        ):

            st.session_state.scanned_book = None
            st.session_state.scanning_isbn = True

            st.rerun()


        if st.button(
            "✏️ Enter Title Manually",
            use_container_width=True,
        ):

            st.session_state.scanned_book = None
            st.session_state.scanning_isbn = False

            st.rerun()


    # ========================================================
    # NORMAL BOOK CONFIRMATION
    # ========================================================

    else:

        suggested_book = str(
            user.get(
                "current_book",
                ""
            )
        ).strip()

        if (
            not suggested_book
            or suggested_book.lower() == "nan"
        ):

            suggested_book = ""


        if suggested_book:

            book_html = f"""
<div class="book-info">

📖 Current book:

<span class="book-info-title">
{suggested_book}
</span>

</div>
"""

            st.markdown(
                book_html,
                unsafe_allow_html=True
            )

            st.caption(
                "Leave the title unchanged if this "
                "is the book you were reading."
            )

        else:

            st.info(
                "📚 You don't have a current book yet. "
                "Please identify the book below."
            )


        # ====================================================
        # SCAN ISBN
        # ====================================================

        if st.button(
            "📷 Scan ISBN",
            use_container_width=True,
        ):

            st.session_state.scanning_isbn = True

            st.rerun()


        st.write("")


        # ====================================================
        # MANUAL ENTRY
        # ====================================================

        st.markdown(
            "**Or enter the title manually:**"
        )

        final_book = st.text_input(
            "Book title",
            value=suggested_book,
            placeholder=(
                "e.g. Maybe You Should Talk to Someone"
            ),
        )


        if st.button(
            "✅ Confirm Reading",
            use_container_width=True,
        ):

            result = finish_reading(
                student_name=nickname,
                final_book_title=final_book.strip(),
            )

            if result is None:

                st.error(
                    "Unable to save the reading session. "
                    "Please enter a book title."
                )

            else:

                today_total = (
                    get_today_reading_minutes(
                        nickname
                    )
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
                    "remaining": remaining,
                }

                st.session_state.scanned_book = None
                st.session_state.scanning_isbn = False
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
        '<div class="section-title">'
        '📖 You\'re reading!'
        '</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.start_time:

        started_text = (
            st.session_state.start_time.strftime(
                "%I:%M %p"
            )
        )

    else:

        started_text = "—"


    reading_html = f"""
<div class="reading-card">

<div class="reading-book">
📖 Reading in progress
</div>

<div class="reading-start">
🕒 Started at {started_text}
</div>

</div>
"""

    st.markdown(
        reading_html,
        unsafe_allow_html=True,
    )

    st.write("")

    st.info(
        "📚 Keep reading and tap the same NFC tag "
        "when you're done."
    )


    # ========================================================
    # PHYSICAL NFC TAP OR MANUAL BUTTON
    # ========================================================

    tap_from_url = (
        st.query_params.get("tap") == "1"
    )

    stop_from_button = st.button(
        "🛑 Stop Reading",
        use_container_width=True,
    )

    stop_triggered = (
        tap_from_url
        or stop_from_button
    )


    if stop_triggered:

        end_time = datetime.now(
            SGT
        )

        result = stop_reading(
            student_name=nickname,
            end_time=end_time,
        )

        if result is None:

            st.error(
                "Unable to stop the reading session."
            )

        else:

            # Clear NFC trigger only after processing.
            if tap_from_url:

                st.query_params.clear()

            st.session_state.reading = False
            st.session_state.start_time = None

            st.session_state.awaiting_confirmation = True

            st.session_state.stopped_session = {
                "book": result["book"],
                "start": result["start"],
                "end": result["end"],
                "minutes": result["minutes"],
            }

            st.rerun()


# ============================================================
# TAP TO START / STOP
# ============================================================

else:

    st.markdown(
        '<div class="section-title">'
        '📚 Ready to read?'
        '</div>',
        unsafe_allow_html=True,
    )

    st.write(
        "Tap below to start or stop your reading session."
    )

    st.write("")

    tap_from_url = (
        st.query_params.get("tap") == "1"
    )

    tap_from_button = st.button(
        "📡 Tap to Read",
        use_container_width=True,
    )

    tap_triggered = (
        tap_from_url
        or tap_from_button
    )


    if tap_triggered:

        if tap_from_url:

            st.query_params.clear()


        # ====================================================
        # CHECK GOOGLE SHEETS
        # ====================================================

        active_session = get_active_session(
            nickname
        )


        # ====================================================
        # NO ACTIVE SESSION → START
        # ====================================================

        if active_session is None:

            start_time = datetime.now(
                SGT
            )

            success = start_reading(
                student_name=nickname,
                nfc_id=nfc_id,
                start_time=start_time,
            )

            if not success:

                st.warning(
                    "Unable to start the reading session."
                )

            else:

                st.session_state.current_book = ""
                st.session_state.start_time = start_time
                st.session_state.reading = True
                st.session_state.show_summary = False
                st.session_state.awaiting_confirmation = False
                st.session_state.stopped_session = None

                st.session_state.scanned_book = None
                st.session_state.scanning_isbn = False

                st.rerun()


        # ====================================================
        # ACTIVE SESSION → STOP
        # ====================================================

        elif active_session["status"] == "active":

            end_time = datetime.now(
                SGT
            )

            result = stop_reading(
                student_name=nickname,
                end_time=end_time,
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
                    "minutes": result["minutes"],
                }

                st.rerun()


        # ====================================================
        # AWAITING CONFIRMATION
        # ====================================================

        elif (
            active_session["status"]
            == "awaiting_confirmation"
        ):

            st.session_state.reading = False

            st.session_state.awaiting_confirmation = True

            st.session_state.stopped_session = {
                "book": active_session["book"],
                "start": active_session["start"],
                "end": active_session["end"],
                "minutes": active_session["minutes"],
            }

            st.rerun()