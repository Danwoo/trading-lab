"""표준 실행형 테스트(tests/test_*.py) 러너 — fail-closed (#335).

이 레포는 아직 pytest 를 도입하지 않았다. 각 서비스의 tests/test_*.py 는 그 자체로
standalone 실행형이다 (`if __name__ == "__main__":` 로 자기 테스트를 돌리고 0/1 로 종료).

#335 이전에는 scripts/verify_*.py 는 CI 잡으로 전부 배선돼 있었는데 같은 서비스의
tests/test_*.py 는 하나도 안 걸려 있었다 — 그물을 짜 놓고 물에 안 담근 상태. 이 스크립트는
서비스별 tests/ 디렉터리를 글롭으로 훑어 존재하는 test_*.py 를 전부 실행한다.

**fail-closed**: 대상이 0건이면 실패한다. 파일이 사라지거나 이름 규칙이 바뀌어도
조용히 초록이 되지 않도록 하기 위함 — #252·#289·#290·#302 와 같은 "검사가 있는데
안 돈다" 부류를 반복하지 않는다.

사용 (서비스 디렉터리를 cwd 로, 그 서비스 venv 로 실행):
    uv run python ../scripts/run_standalone_tests.py tests
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: run_standalone_tests.py <tests-dir>", file=sys.stderr)
        return 2

    tests_dir = Path(argv[1])
    if not tests_dir.is_dir():
        print(f"::error::테스트 디렉터리가 없습니다: {tests_dir}")
        return 1

    files = sorted(tests_dir.glob("test_*.py"))

    if not files:
        print(
            f"::error::{tests_dir} 에서 test_*.py 를 0건 수집했습니다 — fail-closed 종료"
        )
        print(
            "::error::파일이 이동·삭제됐거나 이름 규칙이 바뀌었을 수 있습니다. 확인하세요."
        )
        return 1

    print(f"수집한 테스트 파일 {len(files)}개:")
    for f in files:
        print(f"  - {f.name}")
    print()

    failed: list[str] = []
    for f in files:
        print(f"── {f} " + "─" * max(0, 60 - len(str(f))))
        result = subprocess.run([sys.executable, str(f)])
        if result.returncode != 0:
            failed.append(f.name)
        print()

    print(
        f"검사한 파일 {len(files)}개 중 {len(files) - len(failed)}개 통과, {len(failed)}개 실패"
    )
    if failed:
        print(f"::error::실패한 파일: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
