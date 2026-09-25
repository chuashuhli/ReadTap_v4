import streamlit as st
import pandas as pd
import numpy as np
import zxingcpp
import requests

from openai import OpenAI
from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image, ImageEnhance

from database import (
    calculate_reading_streak,
    get_today_reading_minutes,
    get_active_session,
    start_reading,
    stop_reading,
    finish_reading,
)

# ============================================================
# OPENAI CLIENT
# ============================================================

openai_client = None

try:
    if "OPENAI_API_KEY" not in st.secrets:
        st.error("OPENAI ERROR: OPENAI_API_KEY was not found in Streamlit Secrets.")
    else:
        openai_client = OpenAI(
            api_key=st.secrets["OPENAI_API_KEY"]
        )
        st.success("OpenAI client initialised successfully.")

except Exception as e:
    openai_client = None
    st.error(f"OPENAI INIT ERROR: {repr(e)}")

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


# ============================================================
# LOOK UP BOOK USING ISBN
# ============================================================

def lookup_book_by_isbn(isbn):
    """
    Look up a book using its ISBN.

    First tries Google Books.
    If that fails, tries Open Library.
    """

    isbn = (
        str(isbn)
        .replace("-", "")
        .replace(" ", "")
        .strip()
    )

    # --------------------------------------------------------
    # GOOGLE BOOKS
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # OPEN LIBRARY FALLBACK
    # --------------------------------------------------------

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
                    name = str(
                        author_data.get(
                            "name",
                            ""
                        )
                    ).strip()

                    if name:
                        authors.append(name)

                author = ", ".join(authors)

                if title:
                    return {
                        "isbn": isbn,
                        "title": title,
                        "author": author,
                    }

    except Exception:
        pass


    return None


# ============================================================
# SCAN ISBN BARCODE FROM IMAGE
# ============================================================

def scan_isbn_from_image(image_file):
    """
    Scan an image for an EAN-13 / ISBN-13 barcode.

    Tries several versions of the image to improve
    detection reliability.
    """

    try:
        # ----------------------------------------------------
        # OPEN IMAGE
        # ----------------------------------------------------

        image = Image.open(
            image_file
        ).convert("RGB")


        # ----------------------------------------------------
        # CREATE IMAGE VERSIONS
        # ----------------------------------------------------

        images_to_try = []

        # Original
        images_to_try.append(image)


        # Enlarged
        scale = 2

        enlarged = image.resize(
            (
                image.width * scale,
                image.height * scale,
            )
        )

        images_to_try.append(enlarged)


        # Grayscale
        gray = enlarged.convert("L")

        images_to_try.append(gray)


        # High contrast
        contrast = ImageEnhance.Contrast(
            gray
        ).enhance(2.0)

        images_to_try.append(contrast)


        # Sharpen
        sharp = ImageEnhance.Sharpness(
            contrast
        ).enhance(2.0)

        images_to_try.append(sharp)


        # ----------------------------------------------------
        # TRY EACH IMAGE VERSION
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


            # ------------------------------------------------
            # CHECK DETECTED BARCODES
            # ------------------------------------------------

            for barcode in barcodes:

                raw = str(
                    barcode.text or ""
                ).strip()

                isbn = (
                    raw
                    .replace("-", "")
                    .replace(" ", "")
                )

                if (
                    len(isbn) == 13
                    and isbn.isdigit()
                    and isbn.startswith(
                        ("978", "979")
                    )
                    and is_valid_isbn13(isbn)
                ):
                    return isbn


        return None


    except Exception as e:

        st.error(
            f"Barcode scanner error: {e}"
        )

        return None


# ============================================================
# GOOGLE CLOUD VISION OCR
# ============================================================

def extract_text_from_image(image_file):
    """
    Extract text from an image using Google Cloud Vision.

    Uses the Google Vision service account stored
    in Streamlit Secrets under:

        gcp_vision_service_account
    """

    try:

        from google.cloud import vision
        from google.oauth2 import service_account

        # ----------------------------------------------------
        # GET GOOGLE VISION SERVICE ACCOUNT
        # ----------------------------------------------------

        credentials_info = dict(
            st.secrets["gcp_vision_service_account"]
        )

        credentials = (
            service_account.Credentials.from_service_account_info(
                credentials_info
            )
        )

        # ----------------------------------------------------
        # CREATE VISION CLIENT
        # ----------------------------------------------------

        client = vision.ImageAnnotatorClient(
            credentials=credentials
        )

        # ----------------------------------------------------
        # READ IMAGE
        # ----------------------------------------------------

        image_bytes = image_file.getvalue()

        image = vision.Image(
            content=image_bytes
        )

        # ----------------------------------------------------
        # RUN TEXT DETECTION
        # ----------------------------------------------------

        response = client.text_detection(
            image=image
        )

        # ----------------------------------------------------
        # CHECK VISION API ERROR
        # ----------------------------------------------------

        if response.error.message:

            st.error(
                "Google Vision error: "
                + response.error.message
            )

            return ""

        # ----------------------------------------------------
        # GET DETECTED TEXT
        # ----------------------------------------------------

        texts = response.text_annotations

        if not texts:

            return ""

        # The first annotation contains the
        # complete detected text.
        detected_text = texts[0].description

        return detected_text.strip()


    except Exception as e:

        st.error(
            f"OCR error: {e}"
        )

        return ""


def identify_book_from_image(image_file, ocr_text=""):
    """Use the image layout as well as OCR to read title-page/cover clues.

    Returns a conservative title/author guess. This is especially useful when
    OCR returns the title and author in separate lines among lots of cover text.
    """
    if openai_client is None:
        return {"title": "", "author": ""}

    try:
        import base64
        import json

        image_file.seek(0)
        image_bytes = image_file.getvalue()
        mime_type = getattr(image_file, "type", None) or "image/jpeg"
        image_data = base64.b64encode(image_bytes).decode("ascii")

        response = openai_client.responses.create(
            model="gpt-4.1-mini",
            input=[{
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Identify the most likely book from this photo. "
                            "Read the visual hierarchy and layout: distinguish a book title "
                            "and author from chapter headings, running text, publisher text, "
                            "series labels, and page numbers. OCR text, if provided, may be "
                            "noisy. Never invent a title. If no title or author is visible, "
                            "return empty strings. Return only valid JSON with keys title "
                            "and author.\nOCR text:\n" + str(ocr_text or "")[:5000]
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{image_data}",
                    },
                ],
            }],
        )

        raw = (response.output_text or "").strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return {"title": "", "author": ""}
        parsed = json.loads(raw[start:end + 1])
        return {
            "title": str(parsed.get("title") or "").strip(),
            "author": str(parsed.get("author") or "").strip(),
        }
    except Exception as e:
        st.warning(f"Visual book-title reading failed; using OCR search instead. ({e})")
        return {"title": "", "author": ""}


def search_books_by_title(title, author="", limit=5):
    """Search catalog APIs using the compact title/author clues from the photo."""
    import re

    title = re.sub(r"\s+", " ", str(title or "")).strip()
    author = re.sub(r"\s+", " ", str(author or "")).strip()
    if not title:
        return []

    queries = [f'intitle:"{title}"']
    if author:
        queries.insert(0, f'intitle:"{title}" inauthor:"{author}"')
    results = []

    for query in queries:
        try:
            response = requests.get(
                "https://www.googleapis.com/books/v1/volumes",
                params={"q": query, "maxResults": 10, "orderBy": "relevance", "printType": "books"},
                timeout=10,
            )
            if response.status_code != 200:
                continue
            for item in response.json().get("items", []):
                info = item.get("volumeInfo", {})
                candidate_title = str(info.get("title") or "").strip()
                if not candidate_title:
                    continue
                authors = info.get("authors") or []
                identifiers = info.get("industryIdentifiers") or []
                isbn = next((str(x.get("identifier", "")) for x in identifiers if x.get("type") == "ISBN_13"), "")
                if not isbn:
                    isbn = next((str(x.get("identifier", "")) for x in identifiers if x.get("type") == "ISBN_10"), "")
                results.append({
                    "title": candidate_title,
                    "author": ", ".join(authors),
                    "isbn": isbn,
                    "cover_url": (info.get("imageLinks") or {}).get("thumbnail", ""),
                    "source": "Google Books",
                })
        except Exception:
            continue

    wanted = re.sub(r"[^a-z0-9 ]", " ", title.lower())
    wanted_words = set(wanted.split())
    author_words = set(re.sub(r"[^a-z0-9 ]", " ", author.lower()).split())
    for book in results:
        found = re.sub(r"[^a-z0-9 ]", " ", book["title"].lower())
        found_words = set(found.split())
        author_found = set(re.sub(r"[^a-z0-9 ]", " ", book["author"].lower()).split())
        book["_score"] = (
            100 * len(wanted_words & found_words) / max(len(wanted_words), 1)
            + 25 * len(author_words & author_found) / max(len(author_words), 1)
            + (30 if wanted and wanted in found else 0)
        )

    unique = {}
    for book in sorted(results, key=lambda row: row["_score"], reverse=True):
        key = (book["title"].casefold(), book["author"].casefold())
        if key not in unique:
            book.pop("_score", None)
            unique[key] = book
    return list(unique.values())[:limit]


# ============================================================
# SEARCH BOOKS USING OCR TEXT
# ============================================================

def search_books_by_text(text, limit=5):
    """
    Search Google Books and Open Library using OCR text.

    Uses multiple search strategies because OCR text from
    book covers may contain extra words or small OCR errors.

    Returns the best matching books ranked by title similarity.
    """

    if not text:
        return []


    # ========================================================
    # CLEAN OCR TEXT
    # ========================================================

    import re

    cleaned_text = str(text).strip()

    if not cleaned_text:
        return []


    # --------------------------------------------------------
    # NORMALISE COMMON OCR ERRORS
    # --------------------------------------------------------

    ocr_corrections = {
        "whimpy": "wimpy",
        "wimpyy": "wimpy",
        "kidss": "kids",
    }

    words = cleaned_text.split()

    corrected_words = []

    for word in words:

        punctuation = ""

        while word and not word[0].isalnum():
            punctuation += word[0]
            word = word[1:]

        trailing = ""

        while word and not word[-1].isalnum():
            trailing = word[-1] + trailing
            word = word[:-1]

        lower_word = word.lower()

        if lower_word in ocr_corrections:

            word = ocr_corrections[lower_word]

        corrected_words.append(
            word
        )


    cleaned_text = " ".join(
        corrected_words
    ).strip()


    # ========================================================
    # REMOVE OBVIOUS COVER NOISE
    # ========================================================

    noise_words = {
        "a",
        "an",
        "the",
        "by",
        "new",
        "from",
        "illustrated",
        "edition",
        "book",
        "novel",
        "number",
        "no",
        "series",
        "best",
        "selling",
        "bestseller",
    }

    meaningful_words = []

    for word in corrected_words:

        clean_word = re.sub(
            r"[^A-Za-z0-9]",
            "",
            word
        ).lower()

        if (
            clean_word
            and clean_word not in noise_words
        ):

            meaningful_words.append(
                clean_word
            )


    # ========================================================
    # BUILD MULTIPLE SEARCH QUERIES
    # ========================================================

    queries = []

    # 1. Full corrected OCR text
    if cleaned_text:

        queries.append(
            cleaned_text
        )


    # 2. First several meaningful words
    if meaningful_words:

        short_query = " ".join(
            meaningful_words[:8]
        )

        if short_query:

            queries.append(
                short_query
            )


    # 3. First 5 meaningful words
    if len(meaningful_words) >= 5:

        queries.append(
            " ".join(
                meaningful_words[:5]
            )
        )


    # 4. First 3 meaningful words
    if len(meaningful_words) >= 3:

        queries.append(
            " ".join(
                meaningful_words[:3]
            )
        )


    # 5. Specific title-style search
    if len(meaningful_words) >= 2:

        queries.append(
            "intitle:"
            + " ".join(
                meaningful_words[:6]
            )
        )


    # --------------------------------------------------------
    # REMOVE DUPLICATE QUERIES
    # --------------------------------------------------------

    unique_queries = []

    seen_queries = set()

    for query in queries:

        key = query.lower().strip()

        if (
            key
            and key not in seen_queries
        ):

            seen_queries.add(key)

            unique_queries.append(
                query
            )


    # ========================================================
    # STORE ALL RESULTS
    # ========================================================

    results = []


    # ========================================================
    # GOOGLE BOOKS
    # ========================================================

    for query in unique_queries:

        try:

            url = (
                "https://www.googleapis.com/books/v1/volumes"
            )

            params = {
                "q": query,
                "maxResults": 10,
                "orderBy": "relevance",
                "printType": "books",
            }

            response = requests.get(
                url,
                params=params,
                timeout=10,
            )

            if response.status_code != 200:
                continue

            data = response.json()

            items = data.get(
                "items",
                []
            )

            for item in items:

                volume_info = item.get(
                    "volumeInfo",
                    {}
                )

                title = str(
                    volume_info.get(
                        "title",
                        ""
                    )
                ).strip()

                if not title:
                    continue


                # ------------------------------------------------
                # AUTHOR
                # ------------------------------------------------

                authors = volume_info.get(
                    "authors",
                    []
                )

                author = (
                    ", ".join(authors)
                    if authors
                    else ""
                )


                # ------------------------------------------------
                # COVER
                # ------------------------------------------------

                image_links = volume_info.get(
                    "imageLinks",
                    {}
                )

                cover_url = image_links.get(
                    "thumbnail",
                    ""
                )


                # ------------------------------------------------
                # ISBN
                # ------------------------------------------------

                isbn = ""

                identifiers = volume_info.get(
                    "industryIdentifiers",
                    []
                )

                for identifier in identifiers:

                    identifier_type = identifier.get(
                        "type",
                        ""
                    )

                    identifier_value = str(
                        identifier.get(
                            "identifier",
                            ""
                        )
                    )

                    if (
                        identifier_type
                        == "ISBN_13"
                    ):

                        isbn = identifier_value

                        break


                # If ISBN-13 wasn't available,
                # try ISBN-10.
                if not isbn:

                    for identifier in identifiers:

                        identifier_type = identifier.get(
                            "type",
                            ""
                        )

                        identifier_value = str(
                            identifier.get(
                                "identifier",
                                ""
                            )
                        )

                        if (
                            identifier_type
                            == "ISBN_10"
                        ):

                            isbn = identifier_value

                            break


                results.append(
                    {
                        "title": title,
                        "author": author,
                        "isbn": isbn,
                        "cover_url": cover_url,
                        "source": "Google Books",
                        "query": query,
                    }
                )


        except Exception:

            continue


    # ========================================================
    # OPEN LIBRARY
    # ========================================================

    for query in unique_queries:

        # Open Library does not need the Google-specific
        # intitle: syntax for our fallback searches.

        open_library_query = (
            query
            .replace(
                "intitle:",
                ""
            )
            .strip()
        )

        if not open_library_query:
            continue

        try:

            url = (
                "https://openlibrary.org/search.json"
            )

            params = {
                "q": open_library_query,
                "limit": 10,
            }

            response = requests.get(
                url,
                params=params,
                timeout=10,
            )

            if response.status_code != 200:
                continue

            data = response.json()

            docs = data.get(
                "docs",
                []
            )

            for doc in docs:

                title = str(
                    doc.get(
                        "title",
                        ""
                    )
                ).strip()

                if not title:
                    continue


                # ------------------------------------------------
                # AUTHOR
                # ------------------------------------------------

                authors = doc.get(
                    "author_name",
                    []
                )

                author = (
                    ", ".join(
                        authors[:2]
                    )
                    if authors
                    else ""
                )


                # ------------------------------------------------
                # COVER
                # ------------------------------------------------

                cover_id = doc.get(
                    "cover_i"
                )

                cover_url = ""

                if cover_id:

                    cover_url = (
                        "https://covers.openlibrary.org/"
                        f"b/id/{cover_id}-M.jpg"
                    )


                # ------------------------------------------------
                # ISBN
                # ------------------------------------------------

                isbn = ""

                isbn_list = doc.get(
                    "isbn",
                    []
                )

                if isbn_list:

                    isbn = str(
                        isbn_list[0]
                    )


                results.append(
                    {
                        "title": title,
                        "author": author,
                        "isbn": isbn,
                        "cover_url": cover_url,
                        "source": "Open Library",
                        "query": query,
                    }
                )


        except Exception:

            continue


    # ========================================================
    # NO RESULTS
    # ========================================================

    if not results:
        return []


    # ========================================================
    # CALCULATE MATCH SCORE
    # ========================================================

    search_words = set(
        meaningful_words
    )


    def calculate_score(book):

        title = str(
            book.get(
                "title",
                ""
            )
        ).lower()

        author = str(
            book.get(
                "author",
                ""
            )
        ).lower()

        title_clean = re.sub(
            r"[^a-z0-9\s]",
            " ",
            title
        )

        title_words = set(
            title_clean.split()
        )

        score = 0


        # ----------------------------------------------------
        # WORD MATCHES
        # ----------------------------------------------------

        for word in search_words:

            if word in title_words:

                score += 10

            elif word in title:

                score += 5

            elif word in author:

                score += 2


        # ----------------------------------------------------
        # PHRASE MATCH
        # ----------------------------------------------------

        full_cleaned = re.sub(
            r"[^a-z0-9\s]",
            " ",
            cleaned_text.lower()
        )

        full_cleaned = " ".join(
            full_cleaned.split()
        )

        if (
            full_cleaned
            and full_cleaned in title
        ):

            score += 30


        # ----------------------------------------------------
        # IMPORTANT TITLE WORDS
        # ----------------------------------------------------

        if "wimpy" in search_words:

            if "wimpy" in title:

                score += 25


        if "meltdown" in search_words:

            if "meltdown" in title:

                score += 25


        return score


    # ========================================================
    # SCORE RESULTS
    # ========================================================

    for book in results:

        book["score"] = calculate_score(
            book
        )


    # ========================================================
    # REMOVE DUPLICATES
    # ========================================================

    unique_results = []

    seen = set()

    for book in sorted(
        results,
        key=lambda x: x.get(
            "score",
            0
        ),
        reverse=True,
    ):

        key = (
            book["title"].lower().strip(),
            book["author"].lower().strip(),
        )

        if key not in seen:

            seen.add(key)

            unique_results.append(
                book
            )


    # ========================================================
    # REMOVE INTERNAL SEARCH METADATA
    # ========================================================

    for book in unique_results:

        book.pop(
            "query",
            None
        )

        book.pop(
            "score",
            None
        )


    # ========================================================
    # RETURN BEST MATCHES
    # ========================================================

    return unique_results[:limit]

def test_page_text_search(ocr_text):
    """
    Identify a book from OCR text captured from an inside page.

    Strategy:
    1. Clean OCR text.
    2. Extract distinctive words and short phrases.
    3. Search Google Books using several targeted queries.
    4. Capture Google's textSnippet for each result.
    5. Compare OCR text against:
       - Google Books textSnippet
       - title
       - author
       - description
       - categories
    6. Reward books returned by multiple search queries.
    7. Rank candidates and return the strongest matches.

    This function is designed specifically for INSIDE-PAGE scanning.
    It does not change the existing cover-search function.
    """

    import re
    import requests
    from collections import Counter

    # ========================================================
    # 1. BASIC VALIDATION
    # ========================================================

    if not ocr_text or not str(ocr_text).strip():
        return []

    text = str(ocr_text).strip()

    # ========================================================
    # 2. NORMALISE OCR TEXT
    # ========================================================

    text_lower = text.lower()

    # Fix a few common OCR mistakes.
    ocr_corrections = {
        "whimpy": "wimpy",
        "wimpyy": "wimpy",
        "kidss": "kids",
        "diarry": "diary",
        "journnal": "journal",
        "jounal": "journal",
    }

    for wrong, correct in ocr_corrections.items():
        text_lower = re.sub(
            rf"\b{re.escape(wrong)}\b",
            correct,
            text_lower
        )

    # Extract normal words.
    words = re.findall(
        r"[a-zA-Z]{3,}",
        text_lower
    )

    if not words:
        return []

    # ========================================================
    # 3. STOPWORDS
    # ========================================================

    stopwords = {
        "the",
        "and",
        "that",
        "this",
        "with",
        "from",
        "they",
        "them",
        "their",
        "there",
        "here",
        "have",
        "has",
        "had",
        "was",
        "were",
        "are",
        "you",
        "your",
        "for",
        "not",
        "but",
        "what",
        "when",
        "where",
        "which",
        "who",
        "how",
        "why",
        "into",
        "about",
        "then",
        "than",
        "just",
        "like",
        "know",
        "said",
        "say",
        "she",
        "her",
        "his",
        "him",
        "its",
        "our",
        "out",
        "one",
        "all",
        "can",
        "could",
        "would",
        "should",
        "will",
        "been",
        "being",
        "get",
        "got",
        "did",
        "does",
        "doing",
        "mom",
        "dad",
        "today",
        "first",
        "time",
        "went",
        "going",
        "come",
        "came",
        "back",
        "really",
        "thing",
        "things",
        "just",
        "even",
        "because",
        "very",
        "much",
        "more",
        "some",
        "them",
        "then",
        "than",
        "only",
        "over",
        "under",
        "before",
        "after",
        "while",
        "through",
        "down",
        "from",
        "onto",
        "also",
        "still",
        "made",
        "make",
        "know",
        "think",
        "thought",
    }

    # ========================================================
    # 4. CREATE USEFUL WORD LIST
    # ========================================================

    useful_words = [
        word
        for word in words
        if (
            word not in stopwords
            and len(word) >= 4
        )
    ]

    # Preserve order while removing duplicates.
    unique_words = list(
        dict.fromkeys(useful_words)
    )

    if not unique_words:
        return []

    # ========================================================
    # 5. IDENTIFY DISTINCTIVE WORDS
    # ========================================================

    # Words appearing only once are often more useful than
    # extremely common words.
    word_counts = Counter(words)

    distinctive_words = [
        word
        for word in unique_words
        if word_counts[word] == 1
    ]

    # Prefer longer distinctive words.
    distinctive_words = sorted(
        distinctive_words,
        key=lambda x: len(x),
        reverse=True
    )

    # ========================================================
    # 6. BUILD SEARCH PHRASES
    # ========================================================

    queries = []

    # --------------------------------------------------------
    # A. Consecutive phrases from the ORIGINAL OCR
    # --------------------------------------------------------

    # Keep the original word order because book text is
    # sequential. This is much better than simply taking
    # the longest words from the entire page.
    original_words = re.findall(
        r"[a-zA-Z]{3,}",
        text_lower
    )

    # Create short 5-word windows.
    for i in range(
        max(0, len(original_words) - 4)
    ):
        phrase_words = original_words[i:i + 5]

        meaningful_count = sum(
            1
            for w in phrase_words
            if w not in stopwords
        )

        if meaningful_count >= 2:
            phrase = " ".join(
                phrase_words
            )

            if phrase not in queries:
                queries.append(phrase)

    # --------------------------------------------------------
    # B. Sentences from OCR
    # --------------------------------------------------------

    sentences = re.split(
        r"[.!?\n]+",
        text_lower
    )

    for sentence in sentences:

        sentence_words = re.findall(
            r"[a-zA-Z]{4,}",
            sentence
        )

        if not sentence_words:
            continue

        # Remove generic words.
        meaningful_sentence_words = [
            w
            for w in sentence_words
            if w not in stopwords
        ]

        if len(meaningful_sentence_words) >= 3:

            # Take a maximum of 6 words.
            phrase = " ".join(
                meaningful_sentence_words[:6]
            )

            if phrase not in queries:
                queries.append(phrase)

    # --------------------------------------------------------
    # C. Distinctive word combinations
    # --------------------------------------------------------

    if len(distinctive_words) >= 3:

        queries.append(
            " ".join(
                distinctive_words[:3]
            )
        )

    if len(distinctive_words) >= 5:

        queries.append(
            " ".join(
                distinctive_words[:5]
            )
        )

    # --------------------------------------------------------
    # D. Original first meaningful words
    # --------------------------------------------------------

    if len(unique_words) >= 4:

        queries.append(
            " ".join(
                unique_words[:4]
            )
        )

    if len(unique_words) >= 6:

        queries.append(
            " ".join(
                unique_words[:6]
            )
        )

    # ========================================================
    # 7. CLEAN / DEDUPLICATE QUERIES
    # ========================================================

    cleaned_queries = []

    seen_queries = set()

    for query in queries:

        query = re.sub(
            r"\s+",
            " ",
            query
        ).strip()

        if not query:
            continue

        # Avoid extremely short queries.
        if len(query.split()) < 3:
            continue

        key = query.lower()

        if key in seen_queries:
            continue

        seen_queries.add(key)
        cleaned_queries.append(query)

    # Limit API calls.
    # We want several different phrases, but not too many.
    cleaned_queries = cleaned_queries[:10]

    print("\nPAGE SEARCH QUERIES:")

    for query in cleaned_queries:
        print(" -", query)

    if not cleaned_queries:
        return []

    # ========================================================
    # 8. SEARCH GOOGLE BOOKS
    # ========================================================

    candidates = {}

    for query in cleaned_queries:

        try:

            response = requests.get(
                "https://www.googleapis.com/books/v1/volumes",
                params={
                    "q": query,
                    "maxResults": 10,
                    "orderBy": "relevance",
                    "printType": "books",
                },
                timeout=10
            )

            if response.status_code != 200:
                print(
                    f"Google Books HTTP "
                    f"{response.status_code} "
                    f"for query: {query}"
                )
                continue

            data = response.json()

            items = data.get(
                "items",
                []
            )

            for item in items:

                volume_info = item.get(
                    "volumeInfo",
                    {}
                )

                title = str(
                    volume_info.get(
                        "title",
                        ""
                    )
                ).strip()

                if not title:
                    continue

                authors = volume_info.get(
                    "authors",
                    []
                )

                if not isinstance(
                    authors,
                    list
                ):
                    authors = []

                author = ", ".join(
                    str(a)
                    for a in authors
                    if a
                )

                description = str(
                    volume_info.get(
                        "description",
                        ""
                    )
                )

                categories = volume_info.get(
                    "categories",
                    []
                )

                if not isinstance(
                    categories,
                    list
                ):
                    categories = []

                # ------------------------------------------------
                # IMPORTANT:
                # Google Books provides textSnippet under
                # searchInfo.
                # ------------------------------------------------

                search_info = item.get(
                    "searchInfo",
                    {}
                )

                snippet = str(
                    search_info.get(
                        "textSnippet",
                        ""
                    )
                ).strip()

                # Remove HTML tags sometimes present in snippets.
                snippet_clean = re.sub(
                    r"<[^>]+>",
                    " ",
                    snippet
                )

                snippet_clean = re.sub(
                    r"\s+",
                    " ",
                    snippet_clean
                ).strip()

                metadata = " ".join([
                    title,
                    author,
                    description,
                    " ".join(categories),
                ]).lower()

                book_id = item.get(
                    "id"
                )

                if not book_id:
                    book_id = (
                        title.lower()
                        + "|"
                        + author.lower()
                    )

                if book_id not in candidates:

                    candidates[book_id] = {
                        "title": title,
                        "author": author,
                        "description": description,
                        "categories": categories,
                        "metadata": metadata,
                        "snippet": snippet_clean,
                        "cover_url": (
                            volume_info
                            .get(
                                "imageLinks",
                                {}
                            )
                            .get(
                                "thumbnail",
                                ""
                            )
                        ),
                        "google_books_id": (
                            item.get("id")
                        ),
                        "query_hits": 1,
                        "matched_queries": [
                            query
                        ],
                    }

                else:

                    candidate = candidates[
                        book_id
                    ]

                    candidate[
                        "query_hits"
                    ] += 1

                    candidate[
                        "matched_queries"
                    ].append(query)

                    # Keep a useful snippet if the first
                    # result did not contain one.
                    if (
                        not candidate.get(
                            "snippet"
                        )
                        and snippet_clean
                    ):
                        candidate[
                            "snippet"
                        ] = snippet_clean

        except Exception as e:

            print(
                "Google Books search error "
                f"for '{query}': {e}"
            )

            continue

    # ========================================================
    # 9. NO GOOGLE RESULTS
    # ========================================================

    if not candidates:

        print(
            "\nPAGE SEARCH RESULTS: "
            "No Google Books candidates."
        )

        return []

    # ========================================================
    # 10. NORMALISE TEXT FOR MATCHING
    # ========================================================

    def normalise_for_matching(value):

        value = str(
            value or ""
        ).lower()

        value = re.sub(
            r"<[^>]+>",
            " ",
            value
        )

        value = re.sub(
            r"[^a-z0-9\s]",
            " ",
            value
        )

        value = re.sub(
            r"\s+",
            " ",
            value
        )

        return value.strip()

    ocr_normalised = normalise_for_matching(
        text_lower
    )

    ocr_words = set(
        w
        for w in re.findall(
            r"[a-z]{4,}",
            ocr_normalised
        )
        if w not in stopwords
    )

    # ========================================================
    # 11. CREATE OCR PHRASES FOR MATCHING
    # ========================================================

    ocr_phrases = []

    # Use consecutive 4-word phrases.
    ocr_word_list = re.findall(
        r"[a-z]{3,}",
        ocr_normalised
    )

    for i in range(
        max(0, len(ocr_word_list) - 3)
    ):

        phrase_words = ocr_word_list[
            i:i + 4
        ]

        meaningful = [
            w
            for w in phrase_words
            if w not in stopwords
        ]

        if len(meaningful) >= 2:

            phrase = " ".join(
                phrase_words
            )

            ocr_phrases.append(
                phrase
            )

    # Remove duplicate phrases.
    ocr_phrases = list(
        dict.fromkeys(
            ocr_phrases
        )
    )

    # ========================================================
    # 12. SCORE CANDIDATES
    # ========================================================

    results = []

    for candidate in candidates.values():

        title = normalise_for_matching(
            candidate.get(
                "title",
                ""
            )
        )

        author = normalise_for_matching(
            candidate.get(
                "author",
                ""
            )
        )

        description = normalise_for_matching(
            candidate.get(
                "description",
                ""
            )
        )

        categories = normalise_for_matching(
            " ".join(
                candidate.get(
                    "categories",
                    []
                )
            )
        )

        snippet = normalise_for_matching(
            candidate.get(
                "snippet",
                ""
            )
        )

        metadata = " ".join([
            title,
            author,
            description,
            categories,
        ])

        metadata_words = set(
            re.findall(
                r"[a-z]{4,}",
                metadata
            )
        )

        snippet_words = set(
            re.findall(
                r"[a-z]{4,}",
                snippet
            )
        )

        score = 0

        matched_words = []

        # ----------------------------------------------------
        # A. WORD MATCHES IN GOOGLE TEXT SNIPPET
        # ----------------------------------------------------

        snippet_matches = (
            ocr_words.intersection(
                snippet_words
            )
        )

        if snippet_matches:

            score += (
                len(snippet_matches) * 8
            )

            matched_words.extend(
                snippet_matches
            )

        # ----------------------------------------------------
        # B. WORD MATCHES IN METADATA
        # ----------------------------------------------------

        metadata_matches = (
            ocr_words.intersection(
                metadata_words
            )
        )

        if metadata_matches:

            score += (
                len(metadata_matches) * 2
            )

            matched_words.extend(
                metadata_matches
            )

        # ----------------------------------------------------
        # C. EXACT PHRASE MATCH IN SNIPPET
        # ----------------------------------------------------

        phrase_matches = []

        for phrase in ocr_phrases:

            if (
                phrase
                and phrase in snippet
            ):

                phrase_matches.append(
                    phrase
                )

                # Strong evidence.
                score += 25

        # ----------------------------------------------------
        # D. PARTIAL PHRASE MATCH
        # ----------------------------------------------------

        for phrase in ocr_phrases:

            phrase_words = [
                w
                for w in phrase.split()
                if w not in stopwords
            ]

            if len(phrase_words) < 2:
                continue

            matched_count = sum(
                1
                for w in phrase_words
                if w in snippet_words
            )

            # At least 2 words from a phrase
            # appearing in the snippet is useful.
            if matched_count >= 2:

                score += (
                    matched_count * 5
                )

        # ----------------------------------------------------
        # E. TITLE MATCH
        # ----------------------------------------------------

        title_matches = (
            ocr_words.intersection(
                set(
                    re.findall(
                        r"[a-z]{4,}",
                        title
                    )
                )
            )
        )

        if title_matches:

            # Title matches are highly valuable,
            # because these are actual book-title words.
            score += (
                len(title_matches) * 12
            )

            matched_words.extend(
                title_matches
            )

        # ----------------------------------------------------
        # F. AUTHOR MATCH
        # ----------------------------------------------------

        author_words = set(
            re.findall(
                r"[a-z]{4,}",
                author
            )
        )

        author_matches = (
            ocr_words.intersection(
                author_words
            )
        )

        if author_matches:

            score += (
                len(author_matches) * 10
            )

            matched_words.extend(
                author_matches
            )

        # ----------------------------------------------------
        # G. MULTIPLE QUERY HITS
        # ----------------------------------------------------

        query_hits = int(
            candidate.get(
                "query_hits",
                1
            )
        )

        if query_hits >= 2:

            score += (
                (query_hits - 1) * 8
            )

        # ----------------------------------------------------
        # H. DISTINCTIVE WORDS
        # ----------------------------------------------------

        distinctive_matches = (
            set(distinctive_words)
            .intersection(
                snippet_words
            )
        )

        if distinctive_matches:

            score += (
                len(distinctive_matches)
                * 10
            )

            matched_words.extend(
                distinctive_matches
            )

        # Remove duplicates.
        matched_words = list(
            dict.fromkeys(
                matched_words
            )
        )

        candidate["score"] = score

        candidate[
            "matched_words"
        ] = matched_words

        candidate[
            "phrase_matches"
        ] = phrase_matches

        results.append(
            candidate
        )

    # ========================================================
    # 13. SORT RESULTS
    # ========================================================

    results.sort(
        key=lambda x: x.get(
            "score",
            0
        ),
        reverse=True
    )

    # ========================================================
    # 14. REMOVE WEAK / RANDOM RESULTS
    # ========================================================

    # Require stronger evidence for inside-page matches.
    #
    # A result can qualify if:
    # - it has a reasonably strong score, OR
    # - Google returned a snippet containing an OCR phrase.
    #
    strong_results = []

    for result in results:

        score = result.get(
            "score",
            0
        )

        snippet = result.get(
            "snippet",
            ""
        )

        phrase_matches = result.get(
            "phrase_matches",
            []
        )

        if (
            score >= 12
            or (
                snippet
                and phrase_matches
            )
        ):

            strong_results.append(
                result
            )

    # Maximum 5 candidates.
    strong_results = (
        strong_results[:5]
    )

    # ========================================================
    # 15. CONVERT TO THE FORMAT USED BY YOUR UI
    # ========================================================

    final_results = []

    for result in strong_results:

        final_results.append(
            {
                "title": result.get(
                    "title",
                    "Unknown title"
                ),

                "author": result.get(
                    "author",
                    ""
                ),

                "snippet": result.get(
                    "snippet",
                    ""
                ),

                "phrase": (
                    result.get(
                        "phrase_matches",
                        []
                    )[0]
                    if result.get(
                        "phrase_matches",
                        []
                    )
                    else (
                        result.get(
                            "matched_queries",
                            [""]
                        )[0]
                        if result.get(
                            "matched_queries"
                        )
                        else ""
                    )
                ),

                "cover_url": result.get(
                    "cover_url",
                    ""
                ),

                "google_books_id": result.get(
                    "google_books_id"
                ),

                "score": result.get(
                    "score",
                    0
                ),

                "matched_words": result.get(
                    "matched_words",
                    []
                ),
            }
        )

    # ========================================================
    # 16. DEBUG OUTPUT
    # ========================================================

    print(
        "\nPAGE SEARCH RESULTS:"
    )

    if not final_results:

        print(
            " - No strong matches found."
        )

    else:

        for result in final_results:

            print(
                f" - {result['title']} "
                f"(score={result['score']}, "
                f"matched={result['matched_words']})"
            )

            if result.get(
                "snippet"
            ):

                print(
                    f"   snippet: "
                    f"{result['snippet']}"
                )

    return final_results

# ============================================================
# TEST OPENAI CONNECTION
# ============================================================

def test_openai_connection():
    """
    Tests whether ReadTap can communicate with OpenAI.
    """

    if openai_client is None:
        return False, "OpenAI client was not initialised."

    try:
        response = openai_client.responses.create(
            model="gpt-4.1-mini",
            input="Reply with exactly: ReadTap connection successful"
        )

        result = response.output_text.strip()

        return True, result

    except Exception as e:
        return False, f"OpenAI connection failed: {str(e)}"


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

    # Book identification
    "scanning_cover": False,
    "scanning_page": False,
    "book_candidates": [],
    "ocr_text": "",
    "book_clues": {"title": "", "author": ""},
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

        st.session_state.reading = False

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
style="width:{progress_percent}%;"
></div>

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
        "📚 Start Another Reading Session",
        use_container_width=True,
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
    # SCAN ISBN
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
            key="isbn_camera",
            resolution="1080p",
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

                    st.session_state.scanned_book = book
                    st.session_state.book_candidates = []
                    st.session_state.scanning_isbn = False

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
            key="back_from_isbn",
            use_container_width=True,
        ):

            st.session_state.scanning_isbn = False

            st.rerun()


    # ========================================================
    # SCAN BOOK COVER
    # ========================================================

    elif st.session_state.scanning_cover:

        st.markdown(
            "### 📕 Scan Book Cover"
        )

        st.caption(
            "Take a clear photo of the front cover "
            "so ReadTap can identify the title."
        )

        st.info(
            "📕 ReadTap will read the cover and use its layout "
            "to separate the title and author from other text."
        )

        cover_image = st.camera_input(
            "Take a photo of the book cover",
            key="cover_camera",
            resolution="1080p",
        )

        if cover_image:

            with st.spinner(
                "🔎 Reading the book cover..."
            ):

                detected_text = extract_text_from_image(
                    cover_image
                )

            if detected_text:

                st.session_state.ocr_text = detected_text

                st.success(
                    "✅ Text detected on the book cover!"
                )

                # ------------------------------------------------
                # SEARCH FOR POSSIBLE BOOKS
                # ------------------------------------------------

                with st.spinner(
                    "📚 Searching for matching books..."
                ):
                    book_clues = identify_book_from_image(
                        cover_image, detected_text
                    )
                    st.session_state.book_clues = book_clues
                    candidates = search_books_by_title(
                        book_clues.get("title"), book_clues.get("author")
                    ) if book_clues.get("title") else []
                    if not candidates:
                        candidates = search_books_by_text(detected_text)

                if candidates:

                    st.session_state.book_candidates = candidates
                    st.session_state.scanning_cover = False
                    st.session_state.scanning_page = False

                    st.rerun()

                else:

                    st.warning(
                        "I found text on the cover, "
                        "but couldn't match it to a book."
                    )

                    st.text_area(
                        "Text detected by ReadTap",
                        detected_text,
                        height=150,
                        key="cover_detected_text",
                    )

                    st.info(
                        "Try taking another photo with "
                        "the book cover clearly visible."
                    )

            else:

                st.warning(
                    "I couldn't detect any text on the book cover."
                )

                st.caption(
                    "Try again with the cover facing the camera "
                    "and make sure the title is clearly visible."
                )

        if st.button(
            "← Back",
            key="back_from_cover",
            use_container_width=True,
        ):

            st.session_state.scanning_cover = False
            st.session_state.ocr_text = ""

            st.rerun()


    # ========================================================
    # SCAN INSIDE PAGE
    # ========================================================

    elif st.session_state.scanning_page:

        st.markdown(
            "### 📄 Scan Inside Page"
        )

        st.caption(
            "Take a clear photo of a page containing "
            "the book title or other identifying text."
        )

        st.info(
            "📄 ReadTap will read the page and look for visible "
            "title or author clues before searching."
        )

        page_image = st.camera_input(
            "Take a photo of an inside page",
            key="page_camera",
            resolution="1080p",
        )

        if page_image:

            with st.spinner(
                "🔎 Reading the page..."
            ):

                detected_text = extract_text_from_image(
                    page_image
                )

            if detected_text:

                st.session_state.ocr_text = detected_text

                st.success(
                    "✅ Text detected on the page!"
                )

                with st.spinner("📚 Identifying the book from the page..."):
                    book_clues = identify_book_from_image(page_image, detected_text)
                    st.session_state.book_clues = book_clues
                    candidates = search_books_by_title(
                        book_clues.get("title"), book_clues.get("author")
                    ) if book_clues.get("title") else []

                    # A normal page may not show a title. Fall back to matching
                    # distinctive passage text against Google Books snippets.
                    if not candidates:
                        page_matches = test_page_text_search(detected_text)
                        candidates = [
                            {
                                "title": match.get("title", ""),
                                "author": match.get("author", ""),
                                "isbn": "",
                                "cover_url": match.get("cover_url", ""),
                                "source": "Google Books page-text match",
                            }
                            for match in page_matches
                            if isinstance(match, dict)
                        ]

                if candidates:
                    st.session_state.book_candidates = candidates[:5]
                    st.session_state.scanning_page = False
                    st.session_state.scanning_cover = False
                    st.rerun()
                else:
                    st.warning(
                        "I found text, but couldn't identify a strong book match. "
                        "Try a title/copyright page, the cover, or scan the ISBN."
                    )
                    if book_clues.get("title"):
                        st.caption(
                            "Visual title guess: " + book_clues["title"]
                            + (" — " + book_clues["author"] if book_clues.get("author") else "")
                        )
                    st.text_area(
                        "Text detected by ReadTap",
                        detected_text,
                        height=150,
                        key="page_detected_text",
                    )

            else:

                st.warning(
                    "I couldn't detect any text on this page."
                )

                st.caption(
                    "Try another page containing the book title "
                    "or other identifying information."
                )

        if st.button(
            "← Back",
            key="back_from_page",
            use_container_width=True,
        ):

            st.session_state.scanning_page = False
            st.session_state.ocr_text = ""

            st.rerun()


    # ========================================================
    # BOOK CANDIDATES FROM OCR
    # ========================================================

    elif st.session_state.book_candidates:

        st.markdown(
            "### 📚 Possible Books"
        )

        book_clues = st.session_state.get("book_clues", {})
        if book_clues.get("title"):
            clue_text = "Visual title guess: " + book_clues["title"]
            if book_clues.get("author"):
                clue_text += " — " + book_clues["author"]
            st.caption(clue_text)

        st.caption(
            "ReadTap found these possible matches. "
            "Choose the book you were reading."
        )

        if st.session_state.ocr_text:

            with st.expander(
                "🔎 See text ReadTap detected"
            ):

                st.text(
                    st.session_state.ocr_text
                )


        # ----------------------------------------------------
        # DISPLAY CANDIDATES
        # ----------------------------------------------------

        for i, candidate in enumerate(
            st.session_state.book_candidates
        ):

            title = candidate.get(
                "title",
                "Unknown title"
            )

            author = candidate.get(
                "author",
                ""
            )

            source = candidate.get(
                "source",
                ""
            )

            cover_url = candidate.get(
                "cover_url",
                ""
            )

            col1, col2 = st.columns(
                [1, 3]
            )

            with col1:

                if cover_url:

                    try:

                        st.image(
                            cover_url,
                            width=90,
                        )

                    except Exception:

                        st.write(
                            "📚"
                        )

                else:

                    st.markdown(
                        "### 📚"
                    )


            with col2:

                st.markdown(
                    f"**{title}**"
                )

                if author:

                    st.caption(
                        f"✍️ {author}"
                    )

                if source:

                    st.caption(
                        f"Source: {source}"
                    )

                if st.button(
                    "✅ Select This Book",
                    key=f"select_ocr_book_{i}",
                    use_container_width=True,
                ):

                    st.session_state.scanned_book = candidate
                    st.session_state.book_candidates = []
                    st.session_state.ocr_text = ""
                    st.session_state.scanning_cover = False
                    st.session_state.scanning_page = False

                    st.rerun()


            st.write("")


        # ----------------------------------------------------
        # TRY AGAIN
        # ----------------------------------------------------

        if st.button(
            "🔄 Scan Again",
            key="scan_again_book_found",
            use_container_width=True,
        ):

            st.session_state.book_candidates = []
            st.session_state.ocr_text = ""

            st.rerun()


        # ----------------------------------------------------
        # MANUAL ENTRY
        # ----------------------------------------------------

        if st.button(
            "✏️ Enter Title Manually",
            key="manual_entry_book_found",
            use_container_width=True,
        ):

            st.session_state.book_candidates = []
            st.session_state.ocr_text = ""

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
🔢 ISBN: {book["isbn"] or "Not available"}
</div>

</div>
"""

        st.markdown(
            reading_html,
            unsafe_allow_html=True
        )

        st.write("")


        # ----------------------------------------------------
        # USE BOOK
        # ----------------------------------------------------

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
                st.session_state.scanning_cover = False
                st.session_state.scanning_page = False
                st.session_state.book_candidates = []
                st.session_state.ocr_text = ""
                st.session_state.awaiting_confirmation = False
                st.session_state.stopped_session = None
                st.session_state.reading = False
                st.session_state.start_time = None
                st.session_state.current_book = ""
                st.session_state.show_summary = True

                st.rerun()


        # ----------------------------------------------------
        # SCAN AGAIN
        # ----------------------------------------------------

        if st.button(
            "🔄 Scan Again",
            key="scan_again_candidates",
            use_container_width=True,
        ):

            st.session_state.scanned_book = None
            st.session_state.book_candidates = []
            st.session_state.ocr_text = ""
            st.session_state.scanning_isbn = True
            st.session_state.scanning_cover = False
            st.session_state.scanning_page = False

            st.rerun()


        # ----------------------------------------------------
        # MANUAL ENTRY
        # ----------------------------------------------------

        if st.button(
            "✏️ Enter Title Manually",
            key="manual_entry_candidates",
            use_container_width=True,
        ):

            st.session_state.scanned_book = None
            st.session_state.book_candidates = []
            st.session_state.ocr_text = ""
            st.session_state.scanning_isbn = False
            st.session_state.scanning_cover = False
            st.session_state.scanning_page = False

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


        # ----------------------------------------------------
        # EXISTING BOOK
        # ----------------------------------------------------

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
        # BOOK SCANNING OPTIONS
        # ====================================================

        st.markdown(
            "### 🔎 Identify Your Book"
        )

        st.caption(
            "Choose how you'd like ReadTap to identify "
            "the book you were reading."
        )


        # ----------------------------------------------------
        # SCAN ISBN
        # ----------------------------------------------------

        if st.button(
            "📷 Scan ISBN",
            use_container_width=True,
        ):

            st.session_state.scanning_isbn = True
            st.session_state.scanning_cover = False
            st.session_state.scanning_page = False
            st.session_state.book_candidates = []
            st.session_state.ocr_text = ""

            st.rerun()


        # ----------------------------------------------------
        # SCAN COVER
        # ----------------------------------------------------

        if st.button(
            "📕 Scan Book Cover",
            use_container_width=True,
        ):

            st.session_state.scanning_cover = True
            st.session_state.scanning_isbn = False
            st.session_state.scanning_page = False
            st.session_state.book_candidates = []
            st.session_state.ocr_text = ""

            st.rerun()


        # ----------------------------------------------------
        # SCAN INSIDE PAGE
        # ----------------------------------------------------

        if st.button(
            "📄 Scan Inside Page",
            use_container_width=True,
        ):

            st.session_state.scanning_page = True
            st.session_state.scanning_isbn = False
            st.session_state.scanning_cover = False
            st.session_state.book_candidates = []
            st.session_state.ocr_text = ""

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


        # ----------------------------------------------------
        # CONFIRM READING
        # ----------------------------------------------------

        if st.button(
            "✅ Confirm Reading",
            use_container_width=True,
        ):

            if not final_book.strip():

                st.warning(
                    "Please enter a book title."
                )

            else:

                result = finish_reading(
                    student_name=nickname,
                    final_book_title=final_book.strip(),
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
                    st.session_state.scanning_cover = False
                    st.session_state.scanning_page = False
                    st.session_state.book_candidates = []
                    st.session_state.ocr_text = ""
                    st.session_state.awaiting_confirmation = False
                    st.session_state.stopped_session = None
                    st.session_state.reading = False
                    st.session_state.start_time = None
                    st.session_state.current_book = ""
                    st.session_state.show_summary = True

                    st.rerun()

# ============================================================
# TEMPORARY OPENAI CONNECTION TEST
# ============================================================

if st.button("🔌 Test OpenAI Connection"):
    success, message = test_openai_connection()

    if success:
        st.success(message)
    else:
        st.error(message)


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

            st.session_state.scanned_book = None
            st.session_state.scanning_isbn = False
            st.session_state.scanning_cover = False
            st.session_state.scanning_page = False
            st.session_state.book_candidates = []
            st.session_state.ocr_text = ""

            st.rerun()


# ============================================================
# TAP TO START
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
                st.session_state.scanning_cover = False
                st.session_state.scanning_page = False
                st.session_state.book_candidates = []
                st.session_state.ocr_text = ""

                st.rerun()


        # ====================================================
        # ACTIVE SESSION → STOP
        # ====================================================

        elif active_session.get("status") == "active":

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

                st.session_state.scanned_book = None
                st.session_state.scanning_isbn = False
                st.session_state.scanning_cover = False
                st.session_state.scanning_page = False
                st.session_state.book_candidates = []
                st.session_state.ocr_text = ""

                st.rerun()


        # ====================================================
        # AWAITING CONFIRMATION
        # ====================================================

        elif (
            active_session.get("status")
            == "awaiting_confirmation"
        ):

            st.session_state.reading = False

            st.session_state.awaiting_confirmation = True

            st.session_state.stopped_session = {
                "book": active_session.get(
                    "book",
                    ""
                ),
                "start": active_session.get(
                    "start"
                ),
                "end": active_session.get(
                    "end"
                ),
                "minutes": active_session.get(
                    "minutes",
                    0
                ),
            }

            st.rerun()
