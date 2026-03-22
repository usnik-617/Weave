from weave.notice_calendar_integrity import run_notice_calendar_integrity


def main():
    summary = run_notice_calendar_integrity()
    print("[notice-calendar-integrity] done")
    for key in sorted(summary.keys()):
        print(f"- {key}: {summary[key]}")


if __name__ == "__main__":
    main()

