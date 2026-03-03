import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_SECRET = "weave-local-dev-secret-key"
DEFAULT_ADMIN_PASSWORD = "Weave!2026"


class CheckCollector:
    def __init__(self):
        self.failures = []
        self.warnings = []
        self.passes = []

    def fail(self, message):
        self.failures.append(message)

    def warn(self, message):
        self.warnings.append(message)

    def ok(self, message):
        self.passes.append(message)

    def print_report(self):
        for item in self.passes:
            print(f"[PASS] {item}")
        for item in self.warnings:
            print(f"[WARN] {item}")
        for item in self.failures:
            print(f"[FAIL] {item}")

        print("\n=== Summary ===")
        print(
            json.dumps(
                {
                    "pass": len(self.passes),
                    "warn": len(self.warnings),
                    "fail": len(self.failures),
                    "status": "PASS" if not self.failures else "FAIL",
                },
                ensure_ascii=False,
            )
        )


def check_files(base_dir: Path, checks: CheckCollector):
    required_files = [
        "app.py",
        "wsgi.py",
        "gunicorn.conf.py",
        "requirements.txt",
        "DEPLOYMENT.md",
    ]
    for rel in required_files:
        file_path = base_dir / rel
        if file_path.exists():
            checks.ok(f"필수 파일 존재: {rel}")
        else:
            checks.fail(f"필수 파일 누락: {rel}")


def check_python_version(checks: CheckCollector):
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 11):
        checks.ok(f"Python 버전 확인: {major}.{minor}")
    else:
        checks.fail(f"Python 3.11+ 필요 (현재 {major}.{minor})")


def check_production_env(effective_env: str, checks: CheckCollector):
    secret = os.environ.get("WEAVE_SECRET_KEY", "")
    trusted_hosts = os.environ.get("WEAVE_TRUSTED_HOSTS", "").strip()
    proxy_hops_raw = os.environ.get("WEAVE_PROXY_HOPS", "1")

    if effective_env != "production":
        checks.warn("WEAVE_ENV가 production이 아닙니다. (현재: %s)" % effective_env)
        return

    checks.ok("운영 모드 확인: WEAVE_ENV=production")

    if not secret:
        checks.fail("WEAVE_SECRET_KEY 누락")
    elif secret == DEFAULT_SECRET:
        checks.fail("WEAVE_SECRET_KEY가 기본값과 동일")
    elif len(secret) < 32:
        checks.fail("WEAVE_SECRET_KEY 길이 32자 미만")
    else:
        checks.ok("WEAVE_SECRET_KEY 설정 상태 양호")

    if not trusted_hosts:
        checks.fail("WEAVE_TRUSTED_HOSTS 누락")
    else:
        hosts = [h.strip() for h in trusted_hosts.split(",") if h.strip()]
        local_hosts = {"127.0.0.1", "localhost"}
        if any(h in local_hosts for h in hosts):
            checks.warn("WEAVE_TRUSTED_HOSTS에 로컬 호스트 포함")
        checks.ok(f"WEAVE_TRUSTED_HOSTS 설정됨 ({len(hosts)}개)")

    try:
        proxy_hops = int(proxy_hops_raw)
        if proxy_hops >= 1:
            checks.ok("WEAVE_PROXY_HOPS 설정값 유효")
        else:
            checks.fail("WEAVE_PROXY_HOPS는 1 이상이어야 함")
    except ValueError:
        checks.fail("WEAVE_PROXY_HOPS가 정수가 아님")


def check_default_admin_password(base_dir: Path, effective_env: str, checks: CheckCollector):
    app_py = (base_dir / "app.py").read_text(encoding="utf-8")
    if DEFAULT_ADMIN_PASSWORD in app_py:
        if effective_env == "production":
            checks.fail("코드에 기본 관리자 시드 비밀번호가 남아있음")
        else:
            checks.warn("코드에 기본 관리자 시드 비밀번호 문자열 존재")
    else:
        checks.ok("기본 관리자 시드 비밀번호 문자열 미검출")


def check_db(base_dir: Path, checks: CheckCollector):
    db_path = base_dir / "weave.db"
    if not db_path.exists():
        checks.warn("weave.db 파일이 아직 없음 (최초 실행 전일 수 있음)")
        return

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode")
        mode = (cur.fetchone() or [""])[0]
        cur.execute("SELECT 1")
        conn.close()

        checks.ok("SQLite 연결/쿼리 정상")
        if str(mode).lower() == "wal":
            checks.ok("SQLite journal_mode=WAL")
        else:
            checks.warn(f"SQLite journal_mode가 WAL이 아님 ({mode})")
    except Exception as exc:
        checks.fail(f"SQLite 점검 실패: {exc}")


def wait_for_healthz(url: str, timeout_sec: int = 15):
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                payload = response.read().decode("utf-8", errors="replace")
                if response.status == 200:
                    return True, payload
        except Exception:
            time.sleep(0.5)
    return False, ""


def check_health(health_url: str, checks: CheckCollector):
    try:
        with urllib.request.urlopen(health_url, timeout=5) as response:
            text = response.read().decode("utf-8", errors="replace")
            payload = None
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = None

            if response.status == 200 and isinstance(payload, dict) and bool(payload.get("ok")) is True:
                checks.ok(f"헬스체크 정상: {health_url}")
            elif response.status == 200:
                checks.warn(f"헬스체크 응답 200이나 JSON 본문 확인 필요: {health_url}")
            else:
                checks.fail(f"헬스체크 비정상(status={response.status}): {health_url}")
    except urllib.error.URLError as exc:
        checks.fail(f"헬스체크 접속 실패: {health_url} ({exc})")


def main():
    parser = argparse.ArgumentParser(description="Weave 운영 시작 기본 점검")
    parser.add_argument("--env", default=os.environ.get("WEAVE_ENV", "development"))
    parser.add_argument("--health-url", default="http://127.0.0.1:5000/healthz")
    parser.add_argument("--start-local", action="store_true", help="점검 전에 로컬 Waitress 서버를 임시로 실행")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    checks = CheckCollector()
    effective_env = args.env.lower()

    check_python_version(checks)
    check_files(base_dir, checks)
    check_production_env(effective_env, checks)
    check_default_admin_password(base_dir, effective_env, checks)
    check_db(base_dir, checks)

    server_proc = None
    if args.start_local:
        python_exe = Path(sys.executable)
        cmd = [
            str(python_exe),
            "-m",
            "waitress",
            "--host=127.0.0.1",
            "--port=5000",
            "app:app",
        ]
        server_proc = subprocess.Popen(cmd, cwd=str(base_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ok, _ = wait_for_healthz(args.health_url, timeout_sec=15)
        if not ok:
            checks.fail("로컬 서버 기동 실패 또는 healthz 응답 없음")

    check_health(args.health_url, checks)

    if server_proc and server_proc.poll() is None:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()

    checks.print_report()
    return 1 if checks.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
