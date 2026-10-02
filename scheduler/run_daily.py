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
    # 콘솔 코드페이지(cp949)가 못 그리는 문자 때문에 로그 출력 자체가 죽는 걸 방지
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(line.encode(enc, errors="replace").decode(enc))
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", **kwargs.pop("env", {})}
    return subprocess.run(
        args, cwd=REPO_ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, **kwargs
    )


def main() -> int:
    log("=== 일일 자동 업데이트 시작 ===")

    # 시작 전에 output/ 아래가 깨끗한지부터 확인 - 수동 테스트하다 남긴 파일 등
    # 이 스크립트와 무관한 변경사항이 있으면, 그걸 "새로 받은 데이터"로 착각해서
    # 엉뚱한 걸 commit/push하는 사고를 막기 위함 (실제로 한 번 발생했었음)
    pre_status = run(["git", "status", "--porcelain", "--", "output/"])
    if pre_status.stdout.strip():
        log("시작 전부터 output/ 아래에 미확정 변경사항이 있음 - 안전을 위해 중단")
        log(pre_status.stdout)
        log("=== 종료(중단) ===\n")
        return 1

    result = run([sys.executable, "scheduler/auto_update.py"])
    log(result.stdout)
    if result.stderr:
        log("stderr: " + result.stderr)

    # auto_update.py는 exit 0/1로 "갱신 있었음/없었음"을 표시하는데, 이건 모듈
    # import 실패 같은 진짜 크래시와 구분이 안 됨 - stderr에 트레이스백이 있으면
    # 실행 자체가 깨진 것으로 보고 commit/push 없이 바로 중단
    if "Traceback (most recent call last)" in result.stderr:
        log("auto_update.py 실행 중 에러 발생 - commit/push 하지 않고 중단")
        log("=== 종료(실패) ===\n")
        return 1

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
