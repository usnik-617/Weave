import argparse
import csv
import sys
from pathlib import Path


def to_float(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def main():
    parser = argparse.ArgumentParser(description="Assert Locust CSV thresholds")
    parser.add_argument("--stats", required=True, help="Path to locust stats CSV")
    parser.add_argument("--max-p95-ms", type=float, default=1000)
    parser.add_argument("--max-failure-ratio", type=float, default=0.01)
    parser.add_argument("--min-total-requests", type=int, default=500)
    args = parser.parse_args()

    stats_path = Path(args.stats)
    if not stats_path.exists():
        print(f"[FAIL] stats file not found: {stats_path}")
        return 2

    with stats_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    aggregate_row = None
    for row in rows:
        if row.get("Name", "").strip().lower() == "aggregated":
            aggregate_row = row
            break

    if not aggregate_row:
        print("[FAIL] Aggregated row not found in stats CSV")
        return 2

    p95 = to_float(
        aggregate_row.get("95%")
        or aggregate_row.get("95%ile")
        or aggregate_row.get("95 percentile")
    )
    total_requests = int(float(aggregate_row.get("Request Count") or 0))
    failure_count = int(float(aggregate_row.get("Failure Count") or 0))
    failure_ratio = to_float(
        aggregate_row.get("Failure Ratio") or aggregate_row.get("failure_ratio")
    )
    if failure_ratio is None:
        failure_ratio = (failure_count / total_requests) if total_requests > 0 else 1.0

    print(
        f"[INFO] total_requests={total_requests}, p95_ms={p95}, failure_ratio={failure_ratio}"
    )

    failures = []
    if total_requests < args.min_total_requests:
        failures.append(
            f"total_requests {total_requests} < min_total_requests {args.min_total_requests}"
        )
    if p95 is None or p95 > args.max_p95_ms:
        failures.append(f"p95_ms {p95} > max_p95_ms {args.max_p95_ms}")
    if failure_ratio is None or failure_ratio > args.max_failure_ratio:
        failures.append(
            f"failure_ratio {failure_ratio} > max_failure_ratio {args.max_failure_ratio}"
        )

    if failures:
        print("[FAIL] Load test thresholds failed")
        for item in failures:
            print(f" - {item}")
        return 1

    print("[PASS] Load test thresholds satisfied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
