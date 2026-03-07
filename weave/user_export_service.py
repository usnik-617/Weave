from __future__ import annotations

import csv
import io


def build_certificate_csv_text(user_row, activity_rows):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "이름",
        "아이디",
        "활동명",
        "시작",
        "종료",
        "장소",
        "출석상태",
        "봉사시간",
    ])

    for row in activity_rows:
        writer.writerow(
            [
                user_row["name"],
                user_row["username"],
                row["title"],
                row["start_at"],
                row["end_at"],
                row["place"],
                row["attendance_status"],
                row["hours"],
            ]
        )

    return output.getvalue()
