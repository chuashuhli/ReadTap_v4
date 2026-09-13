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
        print("ERROR: OPENAI_API_KEY was not found in Streamlit Secrets.")
    else:
        openai_client = OpenAI(
            api_key=st.secrets["OPENAI_API_KEY"]
        )
        print("OpenAI client initialised successfully.")

except Exception as e:
    print("OpenAI client initialisation failed:", repr(e))


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
    2. Extract useful/distinctive words.
    3. Build several loose Google Books queries.
    4. Collect candidates from Google Books.
    5. Score candidates against the OCR text.
    6. Return only reasonably strong matches.
    """

    import re
    import requests

    if not ocr_text or not ocr_text.strip():
        return []

    # --------------------------------------------------------
    # 1. CLEAN OCR TEXT
    # --------------------------------------------------------

    text = ocr_text.lower()

    # Remove punctuation but keep words
    words = re.findall(r"[a-zA-Z]{3,}", text)

    if not words:
        return []

    # Common OCR / English words that are not useful for
    # identifying a particular book.
    stopwords = {
        "the", "and", "that", "this", "with", "from",
        "they", "them", "their", "there", "here",
        "have", "has", "had", "was", "were", "are",
        "you", "your", "for", "not", "but", "what",
        "when", "where", "which", "who", "how",
        "why", "into", "about", "then", "than",
        "just", "like", "know", "said", "say",
        "she", "her", "his", "him", "its", "our",
        "out", "one", "all", "can", "could",
        "would", "should", "will", "been", "being",
        "get", "got", "did", "does", "do",
        "mom", "dad", "today", "first", "time"
    }

    # Keep words that are reasonably distinctive.
    useful_words = [
        w for w in words
        if w not in stopwords and len(w) >= 4
    ]

    # Remove duplicates while preserving order
    unique_words = list(dict.fromkeys(useful_words))

    # --------------------------------------------------------
    # 2. CREATE SEARCH QUERIES
    # --------------------------------------------------------

    queries = []

    # A. Distinctive individual words
    #
    # Take the longest words because these tend to be more
    # useful than generic short words.
    long_words = sorted(
        unique_words,
        key=lambda x: len(x),
        reverse=True
    )

    if len(long_words) >= 3:
        queries.append(" ".join(long_words[:3]))

    if len(long_words) >= 5:
        queries.append(" ".join(long_words[:5]))

    # B. First meaningful words from the page
    #
    # These can be useful when the page contains a distinctive
    # sentence opening.
    first_words = unique_words[:]

    if len(first_words) >= 3:
        queries.append(" ".join(first_words[:3]))

    if len(first_words) >= 5:
        queries.append(" ".join(first_words[:5]))

    # C. Look for particularly distinctive phrases around
    # punctuation / sentence boundaries.
    sentences = re.split(r"[.!?\n]+", text)

    for sentence in sentences:
        sentence_words = re.findall(
            r"[a-zA-Z]{4,}",
            sentence
        )

        sentence_words = [
            w for w in sentence_words
            if w not in stopwords
        ]

        if len(sentence_words) >= 3:
            # Use only a short phrase.
            phrase = " ".join(sentence_words[:5])

            if phrase not in queries:
                queries.append(phrase)

    # Remove duplicates
    queries = list(dict.fromkeys(queries))

    # Limit the number of Google Books requests
    queries = queries[:6]

    print("PAGE SEARCH QUERIES:")
    for q in queries:
        print(" -", q)

    # --------------------------------------------------------
    # 3. SEARCH GOOGLE BOOKS
    # --------------------------------------------------------

    candidates = {}

    for query in queries:

        try:
            response = requests.get(
                "https://www.googleapis.com/books/v1/volumes",
                params={
                    "q": query,
                    "maxResults": 10
                },
                timeout=10
            )

            if response.status_code != 200:
                continue

            data = response.json()

            for item in data.get("items", []):

                volume_info = item.get(
                    "volumeInfo",
                    {}
                )

                title = volume_info.get(
                    "title",
                    ""
                ).strip()

                if not title:
                    continue

                authors = volume_info.get(
                    "authors",
                    []
                )

                description = volume_info.get(
                    "description",
                    ""
                )

                categories = volume_info.get(
                    "categories",
                    []
                )

                # Combine searchable book metadata
                metadata = " ".join([
                    title,
                    " ".join(authors),
                    description,
                    " ".join(categories)
                ]).lower()

                candidates[item.get("id", title)] = {
                    "title": title,
                    "authors": authors,
                    "description": description,
                    "metadata": metadata,
                    "cover_url": (
                        volume_info
                        .get("imageLinks", {})
                        .get("thumbnail", "")
                    ),
                    "google_books_id": item.get("id"),
                    "query_hits": candidates.get(
                        item.get("id", title),
                        {}
                    ).get("query_hits", 0) + 1
                }

        except Exception as e:
            print(
                f"Google Books search error for "
                f"'{query}': {e}"
            )

    # --------------------------------------------------------
    # 4. SCORE CANDIDATES
    # --------------------------------------------------------

    ocr_words = set(
        w for w in words
        if len(w) >= 4
    )

    results = []

    for candidate in candidates.values():

        metadata = candidate["metadata"]

        metadata_words = set(
            re.findall(
                r"[a-zA-Z]{4,}",
                metadata
            )
        )

        # Number of OCR words appearing in the metadata
        word_matches = ocr_words.intersection(
            metadata_words
        )

        word_score = len(word_matches)

        # Reward candidates returned by multiple queries
        query_score = candidate["query_hits"]

        # Overall score
        score = (
            word_score * 2
            + query_score * 3
        )

        candidate["score"] = score
        candidate["matched_words"] = list(
            word_matches
        )

        results.append(candidate)

    # --------------------------------------------------------
    # 5. SORT BEST MATCHES FIRST
    # --------------------------------------------------------

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    # --------------------------------------------------------
    # 6. REMOVE WEAK RESULTS
    # --------------------------------------------------------

    # We don't want random books appearing just because
    # Google Books returned them.
    strong_results = [
        r for r in results
        if r["score"] >= 5
    ]

    # Maximum 5 candidates shown to user
    strong_results = strong_results[:5]

    print("\nPAGE SEARCH RESULTS:")

    for result in strong_results:
        print(
            f" - {result['title']} "
            f"(score={result['score']}, "
            f"matched={result['matched_words']})"
        )

    return strong_results

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
            "📕 ReadTap will use Google Cloud Vision "
            "to read the text on the cover."
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
                    candidates = search_books_by_text(
                        detected_text
                    )

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
            "📄 ReadTap will use Google Cloud Vision "
            "to read the text on the page."
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

                                # =================================================
                # TEMPORARY PAGE SEARCH TEST
                # =================================================

                if st.button(
                    "🧪 Test Page Search",
                    use_container_width=True,
                ):

                    with st.spinner(
                        "🔎 Testing page text search..."
                    ):

                        page_test = (
                            test_page_text_search(
                                detected_text
                            )
                        )

                    st.markdown(
                        "### 🔎 Search phrases"
                    )

                    if isinstance(page_test, dict):

                        phrases = page_test.get(
                            "phrases",
                            []
                        )

                        results = page_test.get(
                            "results",
                            []
                        )

                    else:

                        phrases = []
                        results = page_test


                    for phrase in phrases:

                        st.write(
                            f'• "{phrase}"'
                        )


                    st.markdown(
                        "### 📚 Google Books results"
                    )

                    if results:

                        for result in results:

                            if not isinstance(
                                result,
                                dict
                            ):

                                continue

                            title = result.get(
                                "title",
                                "Unknown title"
                            )

                            author = result.get(
                                "author",
                                ""
                            )

                            snippet = result.get(
                                "snippet",
                                ""
                            )

                            matched_phrase = result.get(
                                "phrase",
                                ""
                            )

                            st.markdown(
                                f"**{title}**"
                            )

                            if author:

                                st.caption(
                                    f"✍️ {author}"
                                )

                            if snippet:

                                st.info(
                                    snippet
                                )

                            if matched_phrase:

                                st.caption(
                                    f"Matched phrase: "
                                    f"{matched_phrase}"
                                )

                            st.write("")

                    else:

                        st.warning(
                            "Google Books returned "
                            "no usable results."
                        )
                        
                                # =================================================
                    st.text_area(
                        "Text detected by ReadTap",
                        detected_text,
                        height=150,
                        key="page_detected_text",
                    )

                    st.info(
                        "Try another page containing "
                        "the book title, author, or other "
                        "identifying information."
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