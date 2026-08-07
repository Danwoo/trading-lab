"""계약 검증 스크립트(scripts/verify_*.py) 러너 — fail-closed.

`run_standalone_tests.py`(tests/test_*.py 담당)의 짝이다. 서비스의 `scripts/` 를 글롭으로
훑어 존재하는 `verify_*.py` 를 **전부** 실행한다. 잡마다 스크립트를 하나씩 손으로 적던
방식(잡 36개 · 보일러플레이트 ~700줄)을 대신하며, 손으로 유지하는 목록이 현실과 갈리는
부류(#241·#252·#290·#302·#335)를 구조적으로 없앤다.

설계 규칙 셋:

1. **fail-closed** — 수집 0건이면 실패한다. 디렉터리가 사라지거나 이름 규칙이 바뀌어도
   조용히 초록이 되지 않는다. 검사한 파일 수를 항상 출력에 남겨, 통과가 "위반 없음"인지
   "아무것도 안 봤음"인지 읽는 사람이 구분할 수 있게 한다.

2. **fail-fast 안 함** — 첫 실패에서 멈추지 않고 전부 돌린 뒤 요약한다. 잡을 스위트로
   묶어도 앞 검증의 실패가 뒤 검증의 결과를 가리지 않게 하기 위함이다 (묶기의 유일한
   실질 비용이 그것이었다 — ci.yml 이 잡을 쪼개 놓았던 근거).

3. **제외는 존재를 강제한다** — `--skip NAME` 으로 뺀 이름이 실제로 글롭에 없으면 실패한다.
   제외 목록이 이름 변경·삭제로 낡아 "빼려던 것이 아니라 아무것도 안 뺀" 상태가 되면
   시끄럽게 실패해야 한다. (제외 대상은 별도 잡에서 실행되는 것들 — 예: 서비스 컨테이너와
   파괴적 플래그가 필요한 DB 스크립트.)

사용 (서비스 디렉터리를 cwd 로, 그 서비스 venv 로 실행):
    uv run python ../scripts/run_verify_scripts.py scripts
    uv run python ../scripts/run_verify_scripts.py scripts --skip verify_x.py --skip verify_y.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "scripts_dir", help="verify_*.py 가 있는 디렉터리 (보통 scripts)"
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        metavar="NAME",
        help="이 스위트에서 뺄 파일명 (다른 잡에서 실행됨). 글롭에 없으면 실패한다.",
    )
    args = parser.parse_args(argv[1:])

    scripts_dir = Path(args.scripts_dir)
    if not scripts_dir.is_dir():
        print(f"::error::검증 스크립트 디렉터리가 없습니다: {scripts_dir}")
        return 1

    found = sorted(scripts_dir.glob("verify_*.py"))
    found_names = {f.name for f in found}

    if not found:
        print(
            f"::error::{scripts_dir} 에서 verify_*.py 를 0건 수집했습니다 — fail-closed 종료"
        )
        print(
            "::error::파일이 이동·삭제됐거나 이름 규칙이 바뀌었을 수 있습니다. 확인하세요."
        )
        return 1

    # 규칙 3 — 낡은 제외 목록은 조용히 넘기지 않는다.
    stale = sorted(set(args.skip) - found_names)
    if stale:
        print(
            f"::error::--skip 으로 지정한 파일이 {scripts_dir} 에 없습니다: {', '.join(stale)}"
        )
        print(
            "::error::이름이 바뀌었거나 삭제된 것입니다. 워크플로의 --skip 목록을 갱신하세요."
        )
        return 1

    files = [f for f in found if f.name not in set(args.skip)]
    if not files:
        print(
            f"::error::{scripts_dir} 의 verify_*.py 가 --skip 으로 전부 빠졌습니다 — fail-closed 종료"
        )
        return 1

    print(
        f"수집한 검증 스크립트 {len(files)}개 (전체 {len(found)}개 중 {len(args.skip)}개 제외):"
    )
    for f in files:
        print(f"  - {f.name}")
    if args.skip:
        print(f"  제외(다른 잡 소관): {', '.join(sorted(args.skip))}")
    print()

    failed: list[str] = []
    for f in files:
        print(f"── {f} " + "─" * max(0, 60 - len(str(f))))
        result = subprocess.run([sys.executable, str(f)])
        if result.returncode != 0:
            failed.append(f.name)
        print()

    print(
        f"검사한 스크립트 {len(files)}개 중 {len(files) - len(failed)}개 통과, {len(failed)}개 실패"
    )
    if failed:
        print(f"::error::실패한 스크립트: {', '.join(failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
