import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import send_due_event_reminders  # noqa: E402


def main():
    sent = send_due_event_reminders()
    print(f"전송 완료: {sent}건")


if __name__ == "__main__":
    main()
