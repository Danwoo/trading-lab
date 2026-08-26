"""문서 전용 PR 판정 — 「독립 리뷰 없음」 고지의 판정부 (stdlib 전용, fail-closed).

## 왜 있나

cross-review.yml 은 `paths-ignore: ['**.md', 'docs/**']` 로 문서 전용 PR 을 아예 안 본다 —
판정 코멘트도 마커도 네이티브 리뷰 기록도 생기지 않는다. required 체크는 경로 필터가 없어
전부 초록이 되므로, 체크만 보면 「리뷰 통과」와 「리뷰가 애초에 안 돎」이 구분되지 않는다.
구 review-gate.yml 의 문서 전용 라우팅(`human: merge` 부착)이 그 구분을 만들었는데
#23 Task 8 이 라벨 체계와 함께 지웠다. 이 판정부는 그 자리를 라벨 없이 잇는다 —
ci.yml 의 docs-notice 잡이 문서 전용 PR 에 「독립 리뷰 없음」 코멘트를 남긴다
(2026-08-10 리드 결정: 경량 가시화 — 조용한 것이 통과로 읽히는 것을 막는다).

## 판정 규칙

cross-review 가 실제로 건너뛰는 집합과 **정확히 일치**해야 한다. GitHub 의 paths-ignore 는
변경 파일 **전부**가 무시 패턴에 걸릴 때만 워크플로를 건너뛰고, 패턴 대조는 **대소문자를
가린다** — `README.MD` 는 `**.md` 에 안 걸려 리뷰가 돈다. 그래서 여기서도 소문자로
접지 않는다. 문서 파일 = `*.md`(경로 무관, `**.md`) 또는 `docs/` 밑(`docs/**`).
`.docs/` 밑의 비-md 파일은 `docs/**` 에 안 걸리므로 문서가 아니다 (리뷰가 돈다).

fail-closed: 파일 목록을 못 읽었거나 0건이면 docs_only=false + error — 판독 불가를
「문서 전용」으로 접으면 리뷰가 돈 PR 에 「리뷰 없음」을 잘못 붙인다.

입력(stdin JSON): {"files": ["path", ...]}
출력(stdout JSON): {"docs_only": bool, "total": int, "nondoc": [최대 5건], "error": str|null}
"""

from __future__ import annotations

import json
import sys

# cross-review.yml `on.pull_request.paths-ignore` 와 한 벌(lockstep) — 그쪽을 고치면 여기도.
IGNORE_SUFFIX = ".md"  # '**.md'
IGNORE_PREFIX = "docs/"  # 'docs/**'


def is_doc(path: str) -> bool:
    return path.endswith(IGNORE_SUFFIX) or path.startswith(IGNORE_PREFIX)


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
