#!/usr/bin/env python3
"""에이전트가 새 워크트리에서 「이 폴더를 신뢰합니까」로 멈추는 것을 미리 막는다.

## 왜 필요한가

리뷰·구현 워커는 **매번 새 워크트리 경로**에서 뜬다. kimi 는 처음 보는 폴더마다 신뢰를 묻는데,
헤드리스로 띄우면 그 질문에 답할 사람이 없어 **TUI 준비가 끝나지 않고 기동 실패**로 떨어진다.
실측: 그 때문에 밤새 모든 kimi 리뷰가 폴백을 탔다.

## 저장 규칙 (실측 — 표본 21건 전수 일치)

    ~/.kimi-code/workspace-trust/wd_<폴더이름>_<sha256(절대경로)[:12]>
    내용: {"root": "<절대경로>", "trustedAt": <epoch ms>}

**이 규칙은 kimi 의 내부 구현이다.** 버전이 오르면 바뀔 수 있다 — 그래서 「이미 신뢰돼 있으면
아무것도 안 한다」로 멱등하게 두고, **심고 나서 읽어 확인**한다. 심겼다고 말하기 전에 확인하지
않으면 규칙이 바뀐 날 조용히 거짓 보고를 한다.

## 실패해도 기동을 막지 않는다 (fail-open)

이건 **사람의 개입을 없애는 편의 장치**이지 안전 장치가 아니다. 규칙이 바뀌어 못 심어도
리뷰가 불가능한 것은 아니고(정말 못 뜨면 체인이 다음 후보로 간다), 여기서 죽이면 멀쩡한
리뷰까지 막는다. 대신 **경고를 남겨** 규칙이 바뀐 것이 눈에 띄게 한다.

    python3 scripts/seed_agent_trust.py <에이전트> <워크트리 절대경로>
    python3 scripts/seed_agent_trust.py --check kimi <경로>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

# 신뢰를 물어보는 에이전트만 적는다. claude 는 `--dangerously-skip-permissions` 로,
# codex 는 `exec`/샌드박스 플래그로 각자 해결하므로 여기 없다.
TRUST_DIRS = {"kimi": Path.home() / ".kimi-code" / "workspace-trust"}


def trust_file(agent: str, root: Path) -> Path:
    digest = hashlib.sha256(str(root).encode()).hexdigest()[:12]
    return TRUST_DIRS[agent] / f"wd_{root.name}_{digest}"


def is_trusted(agent: str, root: Path) -> bool:
    path = trust_file(agent, root)
    if not path.is_file():
        return False
    try:
        return json.loads(path.read_text())["root"] == str(root)
    except (OSError, ValueError, KeyError):
        return False


def seed(agent: str, root: Path) -> str:
    if is_trusted(agent, root):
        return "이미 신뢰됨"
    TRUST_DIRS[agent].mkdir(parents=True, exist_ok=True)
    path = trust_file(agent, root)
    path.write_text(json.dumps({"root": str(root), "trustedAt": int(time.time() * 1000)}))
    path.chmod(0o600)
    return "신뢰 심음"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("agent")
    parser.add_argument("root")
    parser.add_argument("--check", action="store_true", help="심지 않고 상태만 본다")
    args = parser.parse_args()

    if args.agent not in TRUST_DIRS:
        # 신뢰를 안 묻는 에이전트다 — 할 일이 없는 것이지 실패가 아니다.
        print(f"건너뜀: {args.agent} 는 폴더 신뢰를 묻지 않는다")
        return 0

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"::warning::신뢰를 심을 폴더가 없다: {root}", file=sys.stderr)
        return 1

    if args.check:
        print(f"{root} — {'신뢰됨' if is_trusted(args.agent, root) else '신뢰 안 됨'}")
        return 0 if is_trusted(args.agent, root) else 1

    result = seed(args.agent, root)
    # 심었다고 말하기 전에 읽어 확인한다.
    if not is_trusted(args.agent, root):
        print(
            f"::warning::{root} 에 신뢰를 심었는데 확인이 안 된다 — {args.agent} 의 저장 규칙이 바뀌었을 수 있다",
            file=sys.stderr,
        )
        return 1
    print(f"[{args.agent}] {root} — {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
