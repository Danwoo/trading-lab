#!/usr/bin/env python3
"""main 으로의 직접 push 를 거부한다 (#420 P1, private 전환 대비).

## 왜 이 층이 필요한가

지금 main 을 지키는 것은 GitHub ruleset `main protection` 이다 — PR 필수·승인 1건·게이트 3종·
force push 금지. 그런데 **이 계정은 GitHub Free 라 private 으로 돌리는 순간 ruleset 이 통째로
사라진다** (GitHub 이 직접 그렇게 답한다: *"Upgrade to GitHub Pro or make this repository public
to enable this feature."*). 리드 결정은 **결제하지 않는다**(2026-08-29)이므로, 서버가 하던 일 중
로컬에서 대신할 수 있는 것을 로컬로 내린다.

`no-commit-to-branch` 는 main **위 커밋**만 막는다. 다음은 그물을 통째로 지나간다:

    git checkout -b tmp && git commit && git push origin HEAD:main

커밋은 tmp 위에서 났으므로 훅이 볼 것이 없고, push 는 훅이 없어서 통과한다.

## 무엇을 하나

pre-commit 의 `pre-push` 스테이지로 돌며, 밀어 넣는 원격 브랜치가 main 이면 거부한다.

**`core.hooksPath` 를 쓰지 않는다.** 그 설정은 git 이 훅을 찾는 자리를 통째로 바꿔서,
`.git/hooks` 에 설치된 **pre-commit 훅 전부가 조용히 죽는다.** 이 레포의 방어 대부분이 그 위에
있으므로, 하나를 더하려다 나머지를 끄는 교환은 성립하지 않는다. 대신 이미 도는 메커니즘
(pre-commit) 안에 스테이지를 하나 더 연다.

## 한계 — 이것은 과속방지턱이지 벽이 아니다

- `--no-verify` 로 지나갈 수 있다. **그래야 한다** — 되돌릴 수 없는 상황(훅 자체가 고장 남)에서
  사람이 손으로 밀 길은 남겨야 하고, 우회가 **의식적 행위**이면 실수는 걸린다.
- 훅이 안 설치된 클론에는 없다. `pre-commit install` 이 선행 조건이고,
  `default_install_hook_types` 가 그것을 한 번에 걸어 준다.
- 그래서 이 층은 **예방**이고, 뚫렸을 때를 잡는 것은 **사후 감사**(#420 P2)다. 둘이 짝이다.

이 레포의 위협 모델은 적대자가 아니라 **실수**다 (1인 레포). 그 전제에서 「예방을 약하게, 발각을
확실하게」 하는 교환이 성립한다 — 그 판단의 근거는 `.docs/` 의 위협 모델 문서(P3)에 적는다.

실행: pre-commit 이 부른다. 손으로 확인하려면
    PRE_COMMIT_REMOTE_BRANCH=refs/heads/main python3 scripts/reject_push_to_main.py
"""

from __future__ import annotations

import os
import sys

#: 직접 push 를 막을 브랜치. 원격 참조 이름(`refs/heads/<name>`)으로도, 짧은 이름으로도 온다.
PROTECTED = ("main",)


def _short(ref: str) -> str:
    """`refs/heads/main` · `main` 어느 쪽으로 와도 짧은 이름으로 맞춘다."""
    return ref.rsplit("/", 1)[-1] if ref else ""


def main() -> int:
    # pre-commit 이 pre-push 훅에 넘기는 값. 비어 있으면 판정할 대상이 없다는 뜻이다.
    remote_branch = os.environ.get("PRE_COMMIT_REMOTE_BRANCH", "")
    local_branch = os.environ.get("PRE_COMMIT_LOCAL_BRANCH", "")
    target = _short(remote_branch)

    if not target:
        # **판정 대상을 못 읽으면 통과시키지 않는다** — 이 훅이 조용히 초록으로 죽는 자리다.
        # 다만 pre-commit 밖에서(예: 손으로) 부른 경우와 구분해 사유를 남긴다.
        print(
            "::error::pre-push: 밀어 넣을 원격 브랜치를 못 읽었다 (PRE_COMMIT_REMOTE_BRANCH 없음). "
            "훅이 무엇을 검사했는지 말할 수 없으므로 통과시키지 않는다.",
            file=sys.stderr,
        )
        return 1

    if target not in PROTECTED:
        print(f"pre-push: {target} — 보호 대상 아님 (보호: {', '.join(PROTECTED)})")
        return 0

    print(
        f"\npush 거부 — {target} 로 직접 밀 수 없습니다.\n"
        f"  민 브랜치: {_short(local_branch) or '(이름 없음)'}\n"
        "\n"
        "  변경은 PR 로 올립니다. 브랜치를 밀고 PR 을 여세요:\n"
        "    git push -u origin <브랜치>\n"
        "\n"
        "  정말 직접 밀어야 한다면 --no-verify 로 지나갈 수 있습니다 —\n"
        "  그건 의식적인 행위여야 하고, main 착륙 감사가 그 커밋을 따로 봅니다.\n",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
