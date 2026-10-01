"""Windows 작업 스케줄러에서 매일 호출하는 래퍼.

scheduler/auto_update.py를 돌려서 새 분기 데이터가 있으면 받아오고,
output/**/final_df (및 보험사/캐피탈사)에 실제 변경이 생겼으면 git commit/push까지
자동으로 처리한다. 모든 출력은 scheduler/run_daily.log에 누적 기록됨
(백그라운드로 도는 작업이라 콘솔을 볼 사람이 없음).
"""
import datetime
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(REPO_ROOT, "scheduler", "run_daily.log")

UPDATED_RE = re.compile(r"^\[(.+?)\] 업데이트됨: (\d+) -> (\d+)$")


def log(msg: str) -> None:
    line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, cwd=REPO_ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", **kwargs
    )


def main() -> int:
    log("=== 일일 자동 업데이트 시작 ===")

    result = run(["python", "scheduler/auto_update.py"])
    log(result.stdout)
    if result.stderr:
        log("stderr: " + result.stderr)

    updated_sectors = [
        f"{m.group(1)}({m.group(2)}->{m.group(3)})"
        for m in UPDATED_RE.finditer(result.stdout)
    ]

    status = run(["git", "status", "--porcelain", "--", "output/"])
    changed_paths = [line[3:] for line in status.stdout.splitlines() if line.strip()]

    if not changed_paths:
        log("변경된 파일 없음 - commit/push 생략")
        log("=== 종료 ===\n")
        return 0

    log(f"변경 파일 {len(changed_paths)}개 감지 - commit/push 진행")
    run(["git", "add", "--", "output/"])

    summary = ", ".join(updated_sectors) if updated_sectors else "변경 감지"
    commit_msg = f"FISIS 데이터 자동 업데이트: {summary}"
    commit_result = run(["git", "commit", "-m", commit_msg])
    log(commit_result.stdout + commit_result.stderr)

    push_result = run(["git", "push", "origin", "main"])
    log(push_result.stdout + push_result.stderr)

    if push_result.returncode != 0:
        log("push 실패!")
        return 1

    log("push 완료")
    log("=== 종료 ===\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
