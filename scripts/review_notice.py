"""문서 전용 PR 판정 — 「독립 리뷰 없음」 고지와 App 승인의 공용 판정부 (stdlib 전용, fail-closed).

## 왜 있나

cross-review.yml 은 `paths-ignore: ['**.md', 'docs/**']` 로 문서 전용 PR 을 아예 안 본다 —
판정 코멘트도 마커도 생기지 않는다. required 체크는 경로 필터가 없어 전부 초록이 되므로,
체크만 보면 「리뷰 통과」와 「리뷰가 애초에 안 돎」이 구분되지 않는다.
구 review-gate.yml 의 문서 전용 라우팅(`human: merge` 부착)이 그 구분을 만들었는데
#23 Task 8 이 라벨 체계와 함께 지웠다. 이 판정부는 그 자리를 라벨 없이 잇는다 —
ci.yml 의 docs-notice 잡이 문서 전용 PR 에 「독립 리뷰 없음」 코멘트를 남긴다
(2026-08-10 리드 결정: 경량 가시화 — 조용한 것이 통과로 읽히는 것을 막는다).

같은 잡의 다음 스텝이 **같은 판정**으로 App 승인 + 자동 머지 arm 을 건다 (2026-08-28 리드
결정 — ruleset 승인 요구 1 이 문서 전용 PR 을 영구 차단하던 구멍을 면제 규약대로 메운다,
루트 CLAUDE.md 「목표층 문서 변경 — 통행료를 걷지 않는다」). 승인 판정은 PR 트리가 아니라
**기본 브랜치 판본**의 이 파일로 한다 — PR 이 자기 승인 판정을 고치지 못하게.

## 판정 규칙 — 정의는 여기 한 곳이다

`IGNORE_PATTERNS` 가 cross-review.yml `on.pull_request.paths-ignore` 와 **같은 목록**이어야 한다.
불변식: *cross-review 가 건너뛰는 PR 이 정확히 App 이 승인하는 PR 이다* — 빈틈(둘 다 안 봄)도
겹침(둘 다 봄)도 없어야 한다. `scripts/verify_docs_only_lockstep.py` 가 두 목록을 정적으로
대조한다. 글롭 의미는 `ci_path_filter.glob_to_regex`(GitHub `on.paths` 문법의 `*`·`**`)를
그대로 쓴다 — 경로 판정 구현이 레포에 하나뿐이도록.

GitHub 의 paths-ignore 는 변경 파일 **전부**가 무시 패턴에 걸릴 때만 워크플로를 건너뛰고,
패턴 대조는 **대소문자를 가린다** — `README.MD` 는 `**.md` 에 안 걸려 리뷰가 돈다. 그래서
여기서도 소문자로 접지 않는다. `.docs/` 밑의 비-md 파일은 `docs/**` 에 안 걸리므로 문서가
아니다 (리뷰가 돈다).

fail-closed: 파일 목록을 못 읽었거나 0건이면 docs_only=false + error — 판독 불가를
「문서 전용」으로 접으면 리뷰가 돈 PR 에 「리뷰 없음」을 잘못 붙이고, 승인 경로에서는
리뷰 없는 코드가 승인된다. `ci_path_filter.py` 의 「모르면 돌린다(run=true)」와 극성이
반대인 이유다 — 판정 기준(어떤 경로가 문서인가)만 공유하고 극성은 용도별로 가른다.

입력(stdin JSON): {"files": ["path", ...]}
출력(stdout JSON): {"docs_only": bool, "total": int, "nondoc": [최대 5건], "error": str|null}
"""

from __future__ import annotations

import json
import re
import sys

from ci_path_filter import glob_to_regex

# cross-review.yml `on.pull_request.paths-ignore` 와 한 벌(lockstep) — 그쪽을 고치면 여기도.
# verify_docs_only_lockstep.py 가 두 목록의 불일치를 CI 에서 잡는다.
IGNORE_PATTERNS: tuple[str, ...] = ("**.md", "docs/**")

_MATCHERS = tuple(re.compile(glob_to_regex(p)) for p in IGNORE_PATTERNS)


def is_doc(path: str) -> bool:
    return any(m.match(path) for m in _MATCHERS)


def decide(payload) -> dict:
    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, list) or not files or not all(isinstance(f, str) and f for f in files):
        return {
            "docs_only": False,
            "total": 0,
            "nondoc": [],
            "error": "파일 목록을 읽지 못했다 (없음·빈 목록·형식 불량) — "
            "판독 불가는 문서 전용으로 접지 않는다 (fail-closed)",
        }
    nondoc = [f for f in files if not is_doc(f)]
    return {
        "docs_only": not nondoc,
        "total": len(files),
        "nondoc": nondoc[:5],
        "error": None,
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        payload = {"_parse_error": str(e)}
    print(json.dumps(decide(payload), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
