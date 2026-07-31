import pandas as pd
import os

LOG_FILE = "reading_log.csv"


def save_reading_session(
    student_name,
    nfc_id,
    student_class,
    book_title,
    start_time,
    end_time,
    minutes
):

    new_record = pd.DataFrame([{

    "nfc_id": nfc_id,
    "student_name": student_name,
    "class": student_class,
    "book_title": book_title,
    "start_datetime": start_time.strftime("%Y-%m-%d %H:%M:%S"),
    "end_datetime": end_time.strftime("%Y-%m-%d %H:%M:%S"),
    "duration_minutes": minutes

    }])

    if not os.path.exists(LOG_FILE):

        new_record.to_csv(LOG_FILE, index=False)

    else:

        new_record.to_csv(
            LOG_FILE,
            mode="a",
            header=False,
            index=False
        )
