"""판정 코멘트 → GitHub 네이티브 PR 리뷰 기록기의 순수 판정 — stdlib 전용 (#23 Task 7).

`.github/workflows/review-record.yml` 이 이것을 부른다. 리뷰어(Orca 워커 또는 사람)는 판정을
PR 코멘트의 기계 마커(`<!-- cross-review v1 model=… verdict=… sha=… -->`)로 남기고, 워크플로가
그것을 `github-actions[bot]` 명의의 네이티브 리뷰(Approve / Request changes)로 옮겨 적는다 —
GitHub 이 자기 PR 자기 승인을 금지해 로컬 `gh`(리드 계정)로는 자기 PR 승인이 서지 않기 때문이다.

## 보안 경계 (공개 레포 — 이 넷이 위조 방어의 전부다)

1. **저자 필터**: 마커는 `OWNER`·`MEMBER`·`COLLABORATOR` 가 쓴 코멘트, 또는 이 레포의
   워크플로 자신(`github-actions[bot]`)이 쓴 코멘트에서만 읽는다. 승인을 required 로 걸지
   않는 이 설계에서 유일한 위조 방어다 — 없으면 누구든 위조 마커로 봇 승인·자동 머지를
   일으킬 수 있다 (head sha 는 공개 정보다). 봇 축은 **로그인과 봇 타입이 둘 다** 맞을 때만
   열린다: 타입만 보면 이 레포에 설치된 아무 앱이나, 로그인만 보면 같은 이름의 사람 계정이
   통과한다.
2. **sha 는 40자 동등 비교**: 접두사 매치 금지 — 접두 비교는 앞자리만 같은 다른 커밋의
   판정을 통과시킨다.
3. **`source=manual` 마커는 arm 하지 않는다**: 사람이 타이핑한 한 줄일 수 있다 (#285 규약 —
   수동 리뷰 마커는 기록은 되지만 자동 머지 권한을 얻지 못한다).
4. **봇 PR 의 상승 종류를 못 읽으면 arm 하지 않는다**: 종류는 PR 제목(`bump X from A to B`
   또는 `update X requirement from ~=A to ~=B`)에서 읽고, 파싱 실패는 fail-closed 다.

## 자동 머지 arm 조건 (전부 참일 때만 — 설계 §4)

  ① required 게이트 초록 — `gate` 서브커맨드 (워크플로가 완료까지 재조회한다)
  ② 승인 리뷰가 있고 그 `commit_id` 가 현재 head 와 같다 — `arm`
  ③ 저자 벤더 ≠ 리뷰어 벤더, 또는 같은 벤더이면서 **작성 티어와 리뷰어 티어를 둘 다 알고
     서로 다르다** — `arm`
  ④ `risk: low` **또는** 저자가 봇이면서 major 상승이 아니다 — `arm`

조건 ③ 은 cross-review.yml 의 동일-벤더 폴백 차단을 arm 조건으로 승계한 것이다: 리뷰어
벤더가 저자 벤더와 같으면 교차 축이 티어뿐이다. 저자 신원은 커밋 author 이메일(1순위)·
브랜치명으로 읽고, 리뷰어 티어는 마커의 `tier=`(기동 배너 관측값)로 읽는다. **어느 쪽이든
판독이 안 되면 arm 하지 않는다** (fail-closed). 신원 형식의 SoT 는 `review_route` 하나다.

위험도의 SoT 는 **이슈의 risk 라벨**이고 판정 시점마다 fresh 조회한다 (구 merge-router.yml 이
못 박은 규칙 승계). 이슈 연결은 `closingIssuesReferences` 가 아니라 **PR 본문 파싱**으로 읽는다
(`Refs #N` 도 위험도 출처 — 2026-08-09 리드 결정. closing 키워드만 잡으면 위험도를 읽히려고
PR 마다 전용 이슈를 만들게 된다). 여러 이슈면 가장 높은 위험, 하나도 못 읽으면 미선언 = 고위험.
**`Refs #N` 의 N 은 PR 일 수 있다** — `issues/{N}` 은 PR 에도 응답하고 PR 의 risk 라벨은
가시화 미러라 판정 입력이 아니다. PR 은 배제하고 근거에 남긴다.

## 서브커맨드 (stdin JSON → stdout JSON, `gate` 만 종료코드 프로토콜)

  record  코멘트 목록 + head 에서 기록할 리뷰를 판정한다
  scan-refs
          PR 본문을 산문 참조(`refs`)와 버린 후보(`dropped`)로 갈라 낸다 — 한 번의 호출로
          둘을 함께 주므로, 한쪽만 실패해 조용히 빈 목록이 되는 경로가 없다
  arm     승인·위험도·봇 상승 종류로 arm 여부를 판정한다
  delegate
          위임 머지(지휘자가 워크플로에 시키는 머지)를 허용할지 판정한다 — ① 리뷰 통과 마커
          ② required 게이트 초록 ③ 저위험 확정. `arm` 을 재사용하고 사유를 **전부** 모아 낸다
  gate    check-runs JSON 에서 required 게이트(`test: gate`)의 상태를 판정한다
          — 종료코드 0 초록 · 1 실패 · 2 미완(재조회 요망), `--final` 은 미완을 실패로 접는다
"""

from __future__ import annotations

import json
import re
import sys

import review_route
import verify_upstream_gate as gate_lib

TRUSTED_ASSOCIATIONS = ("OWNER", "MEMBER", "COLLABORATOR")
# 네이티브 리뷰(승인·수정요청)를 낼 수 있는 봇 신원. **둘이다**:
#   · `github-actions` — Actions 의 GITHUB_TOKEN 이 게시하던 종전 경로. main 에 남아 있는
#     낡은 리뷰가 이 신원이라, 지우면 그 PR 들의 승인이 없던 일이 된다.
#   · `trading-lab-ci` — 승인 전용 GitHub App (2026-08-25). 승인을 CI 밖으로 못 옮기는 이유는
#     GitHub 이 자기 PR 자기 승인을 금지해서다 — 리뷰 워커의 `gh` 는 PR 저자와 같은 계정이다.
# **로그인 이름을 여기에 적는 것이 계약이다** — 목록 밖 신원의 승인은 arm 조건 ②를 못 채운다
# (위조 방어: 승인을 required 로 걸지 않던 설계의 유일한 방어선이었고, required 1 로 올린
# 뒤에도 「누구의 승인이 arm 을 여는가」는 여전히 이 목록이 정한다).
BOT_REVIEWER_LOGINS = ("github-actions", "trading-lab-ci")
# GITHUB_TOKEN 으로 올린 코멘트의 `author_association` 은 이 레포에서 `NONE` 이다
# (2026-08-09 실측) — cross-review 판정 게시 폴백분이 여기 걸려 영영 안 읽혔다.
TRUSTED_BOT_LOGINS = BOT_REVIEWER_LOGINS
REVIEWER_VENDORS = ("claude", "kimi", "codex")
# `review_route` 가 티어를 모으는 벤더 — 지금은 claude 뿐이다. 티어 축은 **리뷰어 벤더의**
# 티어를 알 때만 자기리뷰 차단을 푼다: 혼재 저자(claude+kimi)에서 claude 티어를 안다는
# 이유로 kimi 리뷰의 차단이 풀리면, 아는 티어와 겹치는 벤더가 달라 아무것도 배제하지 못한다.
TIER_KNOWN_VENDOR = "claude"

# cross-review.yml 의 마커 게시부와 같은 문법 (구 merge-router 의 arm 가드에서 승계). sha 자릿수는
# 여기서 안 좁힌다 — 접두 sha 를 정규식에서 거르면 「40자 동등 비교」가 검증 불가능한
# 암묵이 된다. 아래 판정이 길이 40 + 문자열 동등을 명시적으로 검사한다.
#
# `tier=` 는 **선택 필드**다 (#23 Task 9). 이미 달린 마커에는 없고, kimi·codex 리뷰와
# 티어를 확인하지 못한 claude 리뷰에도 없다 — 없으면 「미상」으로 읽는다. 값 어휘를 여기서
# 좁히지 않는 이유는 sha 와 같다: 어휘 밖 값을 정규식이 삼키면 「미상으로 접었다」가 아니라
# 「마커 자체를 못 봤다」가 되어 판정이 통째로 사라진다. 어휘 대조는 `read_marker_tier` 가
# `review_route` 의 목록으로 명시적으로 한다.
_MARKER = re.compile(
    r"<!-- cross-review v1 model=(?P<model>claude|kimi|codex)"
    r"(?: tier=(?P<tier>[a-z0-9.\-]+))?"
    r" verdict=(?P<verdict>merge_ok|needs_changes|unable)"
    r" sha=(?P<sha>[0-9a-f]+)(?P<manual> source=manual)? -->"
)
_FULL_SHA = re.compile(r"[0-9a-f]{40}\Z")

# PR 본문의 이슈 참조 — 키워드 + `#N` 목록 (`Refs #23, #24` 꼴 허용). closing 키워드도
# 위험도 출처로 같이 읽는다 (Closes 를 쓴 PR 이 Refs 만 못 읽혀 미선언이 되지 않게).
# **코드와 인용 안은 참조가 아니다** — 본문 어디에 있든 읽으면 재현 스크립트 인자·인용·서술
# 속 `Refs #<저위험 이슈>` 가 위험도 출처가 된다 (PR #67 본문 실측: 뽑힌 4건 중 진짜 참조는
# 1건. 나머지는 코드 펜스 안 테스트 인자와 인라인 코드 서술이었다). 코드 판별은 펜스(중첩
# 포함)·4칸 들여쓰기 블록·인라인 셋, 인용 판별은 `>` 와 그 lazy 연속행이다.
_REF_BLOCK = re.compile(
    r"\b(?:refs?|close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b:?\s*"
    r"(#\d+(?:\s*(?:,|and)?\s*#\d+)*)",
    re.IGNORECASE,
)
_REF_NUMBER = re.compile(r"#(\d+)")
# 펜스는 여는 표시를 기억했다가 **같은 문자로 그만큼 이상** 일 때만 닫는다 — 단일 토글이면
# 중첩 펜스(백틱 4개 안의 백틱 3개)에서 안팎이 뒤집혀 코드가 산문으로 읽힌다.
_FENCE = re.compile(r"^\s{0,3}(?P<mark>`{3,}|~{3,})")
_INDENTED_CODE = re.compile(r"^(?: {4}|\t)")
# 버린 자리 표시 — 산문을 이어붙일 때 경계가 되며 참조 문법에 절대 안 맞는다
_DROP_MARK = "\x00"
# 렌더되지 않는 HTML 주석 — 사람 눈에 안 보이는 선언이 위험도 출처가 되지 않게 접는다
# (기계 마커 `<!-- cross-review v1 … -->` 도 이 자리에 산다)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# 여는 백틱 수만큼으로 닫는다 — `` `[^`]*` `` 로는 이중 백틱 스팬의 여는 표시를 빈
# 스팬으로 먹어 안쪽이 산문으로 남는다
_INLINE_CODE = re.compile(r"(`+)[\s\S]*?\1")

# dependabot 제목 형식 **둘** (2026-08-13 실측 — 열린·머지된 PR 제목에서 떴다):
#
#   ① bump    `build(deps): bump mcp from 1.27.2 to 1.28.1 in /web-mcp-service`
#   ② update  `build(deps): update uvicorn[standard] requirement from ~=0.47.0 to ~=0.52.1
#              in /backend-service`
#
# ② 는 버전 업데이트를 켜면서(#106) 생겼다 — 패키지에 extras 대괄호가, 버전에 제약 연산자가
# 붙는다. 두 형식 다 상승 종류의 근거는 `from A to B` 이지만, **동사까지 요구한다**:
# `from … to …` 만 보면 dependabot 이 아닌 아무 제목의 두 토막이 상승 종류가 되고,
# 그 판독이 봇 PR 의 자동 머지 arm 조건 ④ 를 연다.
_TITLE_FORMS = (
    re.compile(r"\bbump\s+\S+\s+from\s+(?P<old>\S+)\s+to\s+(?P<new>\S+)"),
    re.compile(r"\bupdate\s+\S+\s+requirement\s+from\s+(?P<old>\S+)\s+to\s+(?P<new>\S+)"),
)
# 동사와 무관하게 「A 에서 B 로」 꼴을 세는 자 — 제목에 상승이 몇 개 실렸는지 본다.
_ANY_VERSION_PAIR = re.compile(r"\bfrom\s+\S+\s+to\s+\S+")
# 버전 토큰 — 제약 연산자(`~=`·`>=`·`^`)를 걷어낸 **숫자로 시작하는 단일 버전**만 읽는다.
# 끝을 `\Z` 로 못 박는 이유: 범위(`>=2.0,<3.0`)는 major 가 하나로 정해지지 않는데, 앞자리만
# 보는 판독은 그것을 `2` 로 접어 상한을 넘는 상승을 non-major 로 흘린다.
_VERSION_TOKEN = re.compile(r"[~^><=!]*v?(?P<major>\d+)(?:\.[0-9A-Za-z.\-+]*)?\Z")

VERDICT_TO_EVENT = {"merge_ok": "APPROVE", "needs_changes": "REQUEST_CHANGES"}
EVENT_TO_STATE = {"APPROVE": "APPROVED", "REQUEST_CHANGES": "CHANGES_REQUESTED"}


def read_marker_tier(model, tier):
    """마커의 `tier=` 를 어휘로 대조해 읽는다 — 어휘 밖·부재는 None (미상).

    어휘의 SoT 는 `review_route.VENDOR_TIERS` 하나다. 벤더와 티어가 짝이 맞아야 한다 —
    `model=kimi tier=opus` 처럼 남의 벤더 티어를 실은 마커는 위조이거나 형식 오류이고,
    어느 쪽이든 「그 티어로 리뷰했다」의 근거가 못 된다.
    """
    if not tier:
        return None
    if tier in review_route.VENDOR_TIERS.get(model, ()):
        return tier
    return None


def _normalize_login(login) -> str:
    # REST 는 `github-actions[bot]`, `gh pr view` 는 `github-actions` 로 준다
    return (login or "").removesuffix("[bot]")


def find_marker(comments, head_sha):
    """저자 필터를 통과한 코멘트에서 head 와 40자 동등한 마지막 유효 마커를 찾는다.

    반환은 dict(model·tier·verdict·manual·sha·comment_url) 또는 None. `tier` 는 어휘 대조를
    통과한 리뷰어 티어이고 **없거나 어휘 밖이면 None (미상)** 이다. 코멘트는 시간 오름차순
    입력을 전제한다 (GitHub API 기본 정렬) — 같은 head 에 판정이 여럿이면 마지막 것이 이긴다.
    """
    if not _FULL_SHA.match(head_sha or ""):
        return None
    found = None
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        if not is_trusted_author(comment):
            continue
        for m in _MARKER.finditer(comment.get("body") or ""):
            if len(m.group("sha")) != 40 or m.group("sha") != head_sha:
                continue
            found = {
                "model": m.group("model"),
                "tier": read_marker_tier(m.group("model"), m.group("tier")),
                "verdict": m.group("verdict"),
                "manual": m.group("manual") is not None,
                "sha": m.group("sha"),
                "comment_url": comment.get("html_url"),
            }
    return found


def is_trusted_author(comment) -> bool:
    """마커를 읽어도 되는 코멘트인가 — 멤버 축, 또는 워크플로 자신(봇) 축.

    봇 축은 로그인·타입을 **둘 다** 요구한다. 어느 한쪽만 보면 신뢰 경계가 「이 레포의
    워크플로」에서 「봇처럼 보이는 것」으로 넓어진다.
    """
    if comment.get("author_association") in TRUSTED_ASSOCIATIONS:
        return True
    return comment.get("user_type") == "Bot" and _normalize_login(comment.get("user_login")) in TRUSTED_BOT_LOGINS


def _bot_reviews_for_head(reviews, head_sha):
    out = []
    for review in reviews or []:
        if not isinstance(review, dict):
            continue
        if _normalize_login(review.get("user_login")) not in BOT_REVIEWER_LOGINS:
            continue
        if review.get("commit_id") != head_sha:
            continue
        if review.get("state") in ("APPROVED", "CHANGES_REQUESTED"):
            out.append(review)
    return out


def decide_record(payload) -> dict:
    """기록할 네이티브 리뷰를 판정한다 — 유효 마커 없음·unable·중복 기록은 게시하지 않는다."""
    head_sha = payload.get("head_sha") or ""
    base = {
        "verdict": None,
        "model": None,
        "tier": None,
        "manual": False,
        "marker_sha": None,
        "review_event": None,
        "post_review": False,
        "arm_candidate": False,
        "comment_url": None,
    }
    if not _FULL_SHA.match(head_sha):
        return {
            **base,
            "reason": f"head sha 형식 불량({head_sha!r}) — 무행동 (fail-closed)",
        }

    marker = find_marker(payload.get("comments") or [], head_sha)
    if marker is None:
        return {
            **base,
            "reason": "현재 head 와 40자 동등한 유효 마커 없음 "
            "(저자 필터 OWNER/MEMBER/COLLABORATOR + 이 레포 봇 게시분 · "
            "낡은 sha·접두 sha 불인정)",
        }

    result = {
        **base,
        "verdict": marker["verdict"],
        "model": marker["model"],
        "tier": marker["tier"],
        "manual": marker["manual"],
        "marker_sha": marker["sha"],
        "comment_url": marker["comment_url"],
        "arm_candidate": marker["verdict"] == "merge_ok" and not marker["manual"],
    }
    event = VERDICT_TO_EVENT.get(marker["verdict"])
    if event is None:
        return {
            **result,
            "reason": "판정 unable — 네이티브 리뷰를 남기지 않는다 (판정 없음)",
        }

    result["review_event"] = event
    bot_reviews = _bot_reviews_for_head(payload.get("existing_reviews") or [], head_sha)
    if bot_reviews and bot_reviews[-1].get("state") == EVENT_TO_STATE[event]:
        return {
            **result,
            "reason": f"같은 head 에 동일 상태({event}) 리뷰가 이미 기록됨 — 게시 생략",
        }
    return {
        **result,
        "post_review": True,
        "reason": f"기록: {event} (sha={marker['sha']})",
    }


def _numbers_in(text) -> set[int]:
    numbers: set[int] = set()
    for m in _REF_BLOCK.finditer(text):
        numbers.update(int(n) for n in _REF_NUMBER.findall(m.group(1)))
    return numbers


def scan_refs(body) -> dict:
    """본문을 산문과 버린 자리로 갈라 참조 후보를 모은다 — `{"refs": …, "dropped": …}`.

    코드는 버린다 — 펜스(중첩 포함)·4칸 들여쓰기 블록·인라인 코드, 그리고 인용은 lazy
    연속행(`>` 없는 다음 줄)까지. 거기 적힌 `Refs #N` 은 선언이 아니라 인용이다.
    **렌더되지 않는 HTML 주석도 버린다** — 사람 눈에 안 보이는 한 줄이 위험도 출처가 되면
    본문만 읽는 사람은 그 PR 이 왜 저위험으로 접혔는지 알 수 없다. 주석 판별은 **펜스 판별
    뒤에** 온다: 코드 블록 안의 `<!--` 는 주석이 아니고, 먼저 보면 그 뒤 펜스가 통째로
    주석에 먹혀 좁힘이 풀린다.

    **`dropped` 는 「본문 전체에서 보이는 후보」 빼기 「산문 후보」로 구한다.** 버린 줄에서만
    긁어모으면 판별 자체의 빈틈이 그대로 구멍이 된다 — 펜스 구분선(여는 줄의 info string·
    닫는 줄의 꼬리)처럼 산문도 코드도 아닌 자리, 줄바꿈으로 이어진 참조 목록의 둘째 줄처럼
    줄 단위 스캔이 놓치는 자리가 실제로 있었다. 차집합으로 구하면 **좁힘이 무엇을 잃든**
    그 번호가 `dropped` 로 남아 위험도를 올리는 쪽으로만 작용한다 (`read_risk` 가 그렇게 쓴다).

    반대 방향도 막아야 한다 — 버린 줄을 자리표시 없이 건너뛰면 앞뒤 산문이 이어붙어
    **원문에 없던 「키워드 + `#N`」이 생긴다** (`Refs:` / 펜스 블록 / `#1`). 그 번호는 탐욕
    판독에 없으므로 `dropped` 가 정의상 못 잡고, 위험도가 내려간다. 버린 자리마다 비-공백
    자리표시를 남겨 참조 문법의 공백 건너뛰기가 그 경계를 넘지 못하게 한다.
    """
    raw = body or ""
    prose: list[str] = []
    fence: str | None = None
    in_quote = False
    in_comment = False

    def drop():
        # 비-공백 자리표시 — 버린 자리를 사이에 두고 앞뒤 산문이 한 문장으로 붙지 않게
        prose.append(_DROP_MARK)

    for line in raw.splitlines():
        if in_comment:
            if "-->" not in line:
                drop()
                continue
            in_comment = False
            line = _DROP_MARK + line.split("-->", 1)[1]

        opened = _FENCE.match(line)
        if fence is not None:
            # 닫는 것은 같은 문자로 여는 길이 이상일 때만 (중첩 펜스 보호)
            if opened and opened.group("mark")[0] == fence[0] and len(opened.group("mark")) >= len(fence):
                fence = None
            drop()
            continue
        if opened:
            fence = opened.group("mark")
            drop()
            continue

        # 인라인 코드를 먼저 지운다 — 코드 스팬 안의 `<!--` 는 주석이 아니다. 이 순서가
        # 아니면 산문이 인용한 짝 없는 `<!--` 하나가 그 뒤 본문을 통째로 주석으로 먹는다
        line = _INLINE_CODE.sub(_DROP_MARK, line)

        # 주석 판별은 펜스·인라인 코드 밖에서만 — 한 줄에 닫힌 것은 지우고, 안 닫혔으면 잇는다
        if "<!--" in line:
            line = _HTML_COMMENT.sub(_DROP_MARK, line)
            if "<!--" in line:
                line = line.split("<!--", 1)[0] + _DROP_MARK
                in_comment = True

        if not line.strip():
            in_quote = False
            prose.append("")
            continue
        if line.lstrip().startswith(">"):
            in_quote = True
            drop()
            continue
        if in_quote or _INDENTED_CODE.match(line):
            drop()
            continue
        prose.append(line)

    refs = _numbers_in("\n".join(prose))
    return {"refs": sorted(refs), "dropped": sorted(_numbers_in(raw) - refs)}


def parse_refs(body) -> list[int]:
    """PR 본문의 산문에서 참조 이슈 번호를 뽑는다 (중복 제거, 오름차순)."""
    return scan_refs(body)["refs"]


def _major_of(version):
    """제약 연산자를 걷어낸 뒤 major 자리를 읽는다 — 단일 버전이 아니면 None."""
    m = _VERSION_TOKEN.match(version or "")
    return int(m.group("major")) if m else None


def parse_bump_versions(title):
    """PR 제목에서 (이전, 이후) 버전 토큰을 읽는다 — 아는 형식이 아니면 None.

    형식 판별은 `_TITLE_FORMS` 하나가 관장한다. 묶음 PR(`bump the non-major group across
    10 directories with 19 updates`)처럼 `from A to B` 가 없는 제목은 여기서 None 이 되고,
    그대로 arm 거부로 이어진다 (fail-closed).

    **상승이 둘 이상 실린 제목도 None 이다.** 첫 짝만 읽으면 뒤에 있는 major 상승이
    non-major 판정 뒤에 숨는다 — 한 제목이 상승 하나를 말할 때만 그 종류를 안다고 한다.
    세는 것은 **동사와 무관한** `from A to B` 다: 형식 정규식으로 세면 동사가 한 번만 붙는
    `bump a from … to … and b from … to …` 를 한 건으로 읽어 뒤쪽을 놓친다.
    """
    if len(_ANY_VERSION_PAIR.findall(title or "")) != 1:
        return None
    for form in _TITLE_FORMS:
        m = form.search(title or "")
        if m:
            return m.group("old"), m.group("new")
    return None


def classify_bump(title):
    """PR 제목에서 버전 상승 종류를 읽는다 — 못 읽으면 None (fail-closed)."""
    parsed = parse_bump_versions(title)
    if parsed is None:
        return None
    old, new = _major_of(parsed[0]), _major_of(parsed[1])
    if old is None or new is None:
        return None
    return "major" if new != old else "non-major"


def _ref_sort_key(ref):
    number = str(ref.get("number", "") if isinstance(ref, dict) else "")
    return (0, int(number)) if number.isdigit() else (1, number)


def read_risk(refs, dropped=()):
    """참조 번호별 메타에서 위험도를 접는다 — 라벨 없음·판독 불가는 미선언 = 고위험 취급.

    원소는 `{number, is_pr, labels, lookup_failed}`. **PR 은 위험도 출처가 아니다** —
    `issues/{N}` 이 PR 에도 응답해 PR 의 가시화 미러 라벨이 판정 입력으로 새는 것을 막는다.
    배제한 번호는 근거 문자열에 남긴다. 반환은 (위험도, 근거, 배제한 PR 번호 목록).

    `dropped` 는 `scan_refs` 가 코드·인용에서 버린 참조 후보다. **위험도를 올리는 쪽으로만**
    쓴다 — 버린 자리에 후보가 있었으면 그것이 진짜 선언이었을 수 있으므로 low 를 미선언으로
    접는다 (버린 것이 고위험 이슈였는데 저위험 이슈만 남는 경우가 fail-open 이다).
    """
    unknown = sorted(set(dropped) - {r.get("number") for r in refs if isinstance(r, dict)})

    def fold(risk, evidence, excluded):
        if unknown and risk != "high":
            listed = ", ".join(f"#{n}" for n in unknown)
            return (
                "undeclared",
                f"{evidence} · 코드·인용에서 버린 참조 후보({listed}) — 선언이었을 수 있어 미선언으로 접는다",
                excluded,
            )
        return risk, evidence, excluded

    if not refs:
        return fold("undeclared", "연결 이슈 없음 — 위험도 판독 불가", [])

    verdicts, notes, excluded = [], [], []
    for ref in sorted(refs, key=_ref_sort_key):
        if not isinstance(ref, dict):
            notes.append("#?=형식 불량(미선언)")
            verdicts.append("undeclared")
            continue
        number = ref.get("number")
        if ref.get("is_pr"):
            excluded.append(number)
            notes.append(f"#{number}=PR(제외 — risk 라벨은 가시화 미러)")
            continue
        if ref.get("lookup_failed"):
            notes.append(f"#{number}=조회 실패(미선언)")
            verdicts.append("undeclared")
            continue
        labels = ref.get("labels") or []
        if "risk: high" in labels:
            verdict = "high"
        elif "risk: low" in labels:
            verdict = "low"
        else:
            verdict = "undeclared"
        verdicts.append(verdict)
        notes.append(f"#{number}={verdict}")

    evidence = ", ".join(notes)
    if not verdicts:
        return fold("undeclared", f"{evidence} — 이슈 참조 0건, 위험도 판독 불가", excluded)
    if "high" in verdicts:
        return fold("high", evidence, excluded)
    if "undeclared" in verdicts:
        return fold("undeclared", evidence, excluded)
    return fold("low", evidence, excluded)


def judge_author_identity(payload) -> dict:
    """조건 ③ — 리뷰어 벤더가 저자 벤더와 같을 때 작성 티어를 아는가.

    같은 벤더면 교차 축이 티어뿐이다. 티어를 모르면 동일-티어 자기리뷰 가능성을 배제할 수
    없으므로 arm 을 거부한다 (리뷰 자체와 코멘트·네이티브 리뷰 기록은 그대로 남는다).
    신원을 아예 못 읽어도 거부한다 — 못 읽으면 arm 하지 않는다.

    **어휘 밖 에이전트형 이메일은 「사람 저자」가 아니라 「판독 불가」다.** 어휘
    (`review_route` 의 티어·벤더 목록)는 새 모델이 붙을 때 사람이 갱신하므로, 디스패치가
    어휘보다 먼저 도는 창이 반드시 생긴다. 그 창에서 저자 벤더를 모른 채 통과시키면
    자기리뷰가 조용히 arm 된다 — `review_route.decide()` 는 같은 입력에 `author_kind=human`
    을 내어 리뷰어로 claude 를 배정한다.

    작성 티어는 현재 claude 신원에서만 판독된다 (`review_route` 가 `claude_tiers_seen` 만
    모은다). 그래서 차단 해제는 **리뷰어 벤더가 claude 일 때만** 성립한다 — 동일-벤더
    kimi·codex 는 티어를 실어도 늘 사람 경로이고, 혼재 저자에서 claude 티어를 안다는 이유로
    kimi 리뷰의 차단이 풀리지도 않는다.

    **티어 대조는 이제 실측이다** (#23 Task 9). 종전엔 저자 티어만 알면 통과시키고 「폴백이
    반대 티어를 고른다」는 cross-review 쪽 계약을 믿었는데, 그 계약이 실제로는 지켜지지
    않고 있었다 — `worktree create --agent claude` 는 모델 인자를 받지 않아 계산된 폴백
    티어와 무관하게 Orca 기본 모델로 떴다(실측: 배정 sonnet, 기동 배너 `Opus 5 (1M context)`).
    즉 「저자 티어를 안다」가 「다른 티어가 리뷰했다」의 근거가 아니었다. 이제 마커가
    리뷰어 티어를 싣고(기동 배너 관측값), **둘을 직접 비교해** 같으면 차단한다.
    티어를 못 읽으면 — 어느 쪽이든 — arm 하지 않는다 (fail-closed).
    """
    emails = payload.get("commit_author_emails")
    reviewer = payload.get("marker_model") or ""
    reviewer_tier = payload.get("marker_tier") or None
    result = {
        "self_vendor": None,
        "author_models": None,
        "author_tier": None,
        "reviewer_tier": reviewer_tier,
        "identity_source": None,
        "unknown_agentish": None,
        "block": None,
    }
    if not isinstance(emails, list) or not [e for e in emails if e]:
        return {
            **result,
            "block": "커밋 저자 신원을 못 읽음(이메일 0건) — arm 하지 않는다 (fail-closed)",
        }
    if reviewer not in REVIEWER_VENDORS:
        return {
            **result,
            "block": f"리뷰어 벤더 미상({reviewer!r}) — 자기리뷰 여부를 판정할 수 없다 (fail-closed)",
        }

    identity = review_route.identify_author(emails, payload.get("head_ref") or "")
    author_models = identity["author_models"]
    unknown_agentish = identity["unknown_agentish"]
    self_vendor = reviewer in [v for v in author_models.split(",") if v]
    result = {
        "self_vendor": self_vendor,
        "author_models": author_models or None,
        "author_tier": identity["author_tier"],
        "reviewer_tier": reviewer_tier,
        "identity_source": identity["identity_source"],
        "unknown_agentish": unknown_agentish or None,
        "block": None,
    }
    if unknown_agentish:
        return {
            **result,
            "block": "어휘 밖 에이전트형 커밋 신원("
            + ", ".join(unknown_agentish)
            + ") — 저자 벤더를 판정할 수 없어 arm 하지 않는다 (fail-closed)",
        }
    if not self_vendor:
        return result

    # ── 동일-벤더: 교차 축이 티어뿐이다. 양쪽 티어를 **둘 다** 알고 **다를 때만** 푼다 ──
    # 티어 판독은 claude 신원에만 있으므로 동일-벤더 kimi·codex 는 여기서 늘 막힌다 —
    # 혼재 저자(claude+kimi)를 kimi 가 리뷰할 때 claude 쪽 티어로 차단이 풀리던 자리다.
    if reviewer != TIER_KNOWN_VENDOR:
        return {
            **result,
            "block": f"동일-벤더 리뷰({reviewer}) — 이 벤더는 티어 축이 없어 교차를 "
            "증명할 수 없다. arm 하지 않는다 (게이트만 사람에게)",
        }
    if identity["author_tier"] is None:
        return {
            **result,
            "block": f"동일-벤더 리뷰({reviewer}) + 작성 티어 미상 — 동일-티어 "
            "자기리뷰를 배제할 수 없어 arm 하지 않는다 (게이트만 사람에게)",
        }
    if reviewer_tier is None:
        return {
            **result,
            "block": f"동일-벤더 리뷰({reviewer}) + **리뷰어 티어 미상**(마커에 tier= 없음 "
            "또는 어휘 밖) — 작성 티어를 아는 것만으로는 다른 티어가 리뷰했다는 근거가 "
            "되지 않는다. arm 하지 않는다 (fail-closed)",
        }
    if reviewer_tier == identity["author_tier"]:
        return {
            **result,
            "block": f"동일-벤더·**동일-티어** 자기리뷰({reviewer}/{reviewer_tier}) — "
            "교차 축이 하나도 남지 않는다. arm 하지 않는다",
        }
    return result


def decide_arm(payload) -> dict:
    """자동 머지 arm 여부 — 조건 ②③④ 를 판정한다 (① 게이트는 `gate` 서브커맨드가 맡는다)."""
    head_sha = payload.get("head_sha") or ""
    marker_sha = payload.get("marker_sha") or ""
    risk, evidence, excluded_prs = read_risk(payload.get("issue_refs") or [], payload.get("dropped_refs") or [])
    bump = classify_bump(payload.get("pr_title"))
    identity = judge_author_identity(payload)
    base = {
        "arm": False,
        "risk": risk,
        "risk_evidence": evidence,
        "excluded_pr_refs": excluded_prs,
        "bot_bump": bump,
        "pr_author_login": payload.get("pr_author_login"),
        "self_vendor": identity["self_vendor"],
        "author_models": identity["author_models"],
        "author_tier": identity["author_tier"],
        "reviewer_tier": identity["reviewer_tier"],
        "identity_source": identity["identity_source"],
        "unknown_agentish": identity["unknown_agentish"],
    }

    if payload.get("verdict") != "merge_ok":
        return {**base, "reason": f"판정이 merge_ok 아님({payload.get('verdict')})"}
    if payload.get("manual"):
        return {
            **base,
            "reason": "source=manual 마커 — 사람이 타이핑한 한 줄일 수 있어 arm 하지 않는다",
        }
    if not _FULL_SHA.match(head_sha) or not _FULL_SHA.match(marker_sha):
        return {
            **base,
            "reason": "head·마커 sha 형식 불량 — arm 하지 않는다 (fail-closed)",
        }
    if marker_sha != head_sha:
        return {
            **base,
            "reason": f"마커 sha({marker_sha[:12]}…)가 현재 head 와 다름 — 낡은 판정",
        }

    bot_reviews = _bot_reviews_for_head(payload.get("reviews") or [], head_sha)
    if not bot_reviews or bot_reviews[-1].get("state") != "APPROVED":
        return {
            **base,
            "reason": "현재 head 에 대한 봇 승인 리뷰 없음 (조건 ② 미충족 — 리뷰 게시 실패 또는 push 로 낡음)",
        }

    if identity["block"]:
        return {**base, "reason": f"조건 ③ 미충족 — {identity['block']}"}

    if risk == "low":
        return {
            **base,
            "arm": True,
            "reason": f"risk: low ({evidence}) + 봇 승인 — arm",
        }
    # **미선언은 저위험으로 본다** (리드 결정 2026-08-18).
    #
    # 종전엔 미선언을 사람 경로로 보냈다(fail-closed). 그 결과 선언을 빠뜨린 저위험 PR 이
    # 전부 리드 대기열에 쌓여, 「고위험만 사람이 본다」는 원래 의도와 반대로 **리드가 사소한
    # 것까지 다 눌러야** 했다.
    #
    # **명시적 고위험은 그대로 사람 경로다** — 바뀐 것은 「모르겠으면 어느 쪽인가」뿐이다.
    # 선언 자체를 그만두는 것이 아니라(에이전트는 PR 마다 `gate declare` 를 계속 한다),
    # 빠뜨렸을 때 멈추지 않게 하는 것이다.
    #
    # **대가**: 선언을 빠뜨린 고위험이 자동으로 들어간다. 그래서 사유에 「미선언」을 남겨
    # 머지 기록에서 그 사실이 보이게 한다 — 조용히 저위험인 척하지 않는다.
    # 봇 PR 은 이 완화의 대상이 아니다 — 상승 종류(major/minor/patch)로 가르는 별도 규칙이
    # 아래에 있고, major 는 사람 경로다. 미선언을 이유로 그 규칙을 건너뛰면 major 의존성
    # 상승이 자동으로 들어간다(기존 그물이 실제로 잡았다).
    # **「못 읽음」과 「안 적음」은 다르다.** 이슈 조회가 실패한 것은 위험도를 *모르는* 것이지
    # *낮은* 것이 아니다 — 그 자리는 fail-closed 로 남긴다. 완화의 대상은 「선언을 빠뜨렸다」
    # 뿐이고, 「알 수 없다」는 종전대로 사람 경로다.
    lookup_failed = "조회 실패" in (evidence or "")
    if risk == "undeclared" and not lookup_failed and not payload.get("pr_author_is_bot"):
        return {
            **base,
            "arm": True,
            "reason": (f"위험도 미선언 ({evidence}) + 봇 승인 — arm (미선언은 저위험으로 본다 · 리드 결정 2026-08-18)"),
        }
    if payload.get("pr_author_is_bot"):
        if bump is None:
            return {
                **base,
                "reason": "봇 PR 인데 제목에서 상승 종류를 못 읽음 — arm 하지 않는다 (fail-closed)",
            }
        if bump == "major":
            return {**base, "reason": "봇 PR major 상승 — 사람 경로 (설계 §2-1)"}
        return {**base, "arm": True, "reason": f"봇 PR {bump} 상승 + 봇 승인 — arm"}
    return {**base, "reason": f"위험도 {risk} ({evidence}) — 사람 경로"}


def decide_delegate(payload) -> dict:
    """위임 머지 허용 판정 — 지휘자가 요청했다고 그냥 밀지 않는다 (#23 Task 9).

    지휘자는 버튼을 직접 누르는 대신 워크플로에 시킨다 (그래야 `mergedBy` 가
    `app/github-actions` 로 갈려 세 갈래가 구조적으로 구분된다). 그 대가로 **워크플로가 머지
    조건을 다시 판정한다**:

      ① 머지 대상 head 의 리뷰 통과 마커 — `merge_ok` · `source=manual` 아님 · sha 동등
      ② required 게이트(`test: gate`) 전수 초록 — `gate` 서브커맨드가 판정한 상태를 받는다
      ③ 저위험 확정 — `risk: low` 로 **읽힌** 것만. 미선언·고위험은 사람 경로다

    ①③ 과 자기리뷰 차단·승인 대조는 `decide_arm` 을 그대로 쓴다 (자동 머지와 같은 판정부를
    두 개로 갈라 놓으면 언젠가 갈린다). ② 만 여기서 더한다 — 자동 경로는 게이트를 기다리지만
    위임 경로는 **기다리지 않는다**: 지휘자가 지금 밀어 달라고 한 것이므로 지금 초록이
    아니면 거부하고 이유를 돌려준다.

    **사유를 하나만 내지 않는다.** 첫 실패에서 끊으면 지휘자가 고치고 다시 요청할 때마다
    다음 사유가 하나씩 나온다. 전부 모아 한 번에 돌려준다.
    """
    arm = decide_arm(payload)
    gate_state = payload.get("gate_state")
    reasons = []

    if payload.get("verdict") != "merge_ok" or payload.get("manual"):
        reasons.append(
            "① 리뷰 통과 마커 없음 — "
            f"판정={payload.get('verdict') or '없음'}"
            f"{' · source=manual(사람이 타이핑한 한 줄일 수 있다)' if payload.get('manual') else ''}"
        )
    elif payload.get("marker_sha") != payload.get("head_sha"):
        reasons.append("① 마커가 현재 head 의 것이 아님 — 낡은 판정으로는 머지하지 않는다")

    if gate_state != "pass":
        reasons.append(
            f"② required 게이트 비초록 (상태: {gate_state or '미상'}) — "
            "위임 머지는 게이트를 기다리지 않는다. 초록이 된 뒤 다시 요청하라"
        )

    # **미선언은 저위험으로 본다** — arm 경로와 같은 규칙이다 (리드 결정 2026-08-18).
    #
    # 종전엔 `arm` 이 완화를 받는데 `delegate` 는 `risk != "low"` 를 직접 봐, 자동 경로는
    # 흐르고 위임 경로만 막혔다. **같은 판정부를 재사용한다**는 이 함수의 전제가 여기서
    # 깨져 있었다(실측: PR #216 이 그 자리에 막혔다).
    #
    # 「못 읽음」과 「안 적음」의 구분도 arm 과 같다 — 조회 실패는 여전히 사람 경로다.
    # 봇 PR 은 이 완화의 대상이 아니다 — 위임 경로는 상승 종류 예외를 아예 안 타므로
    # (그물이 못박은 계약), 미선언을 이유로 그 문을 열면 major 의존성 상승이 위임으로 샌다.
    _lookup_failed = "조회 실패" in (arm.get("risk_evidence") or "")
    _bot = bool(payload.get("pr_author_is_bot"))
    _risk_ok = arm["risk"] == "low" or (arm["risk"] == "undeclared" and not _lookup_failed and not _bot)
    if not _risk_ok:
        reasons.append(
            f"③ 저위험 확정 아님 (위험도: {arm['risk']} — {arm['risk_evidence']}) — 미선언·고위험은 사람 경로다"
        )

    # `decide_arm` 이 막은 것은 **항상** 함께 싣는다. 승인 부재·자기리뷰 차단·sha 형식 불량은
    # 위 셋으로 환원되지 않고, 환원되는 것(①③)은 같은 말이 한 번 더 나올 뿐이다 —
    # 거부 사유가 겹치는 것보다 빠지는 쪽이 훨씬 나쁘다.
    if not arm["arm"]:
        reasons.append(f"부가 조건 미충족 — {arm['reason']}")

    return {
        "allow": not reasons,
        "reasons": reasons,
        "risk": arm["risk"],
        "risk_evidence": arm["risk_evidence"],
        "author_models": arm["author_models"],
        "author_tier": arm["author_tier"],
        "reviewer_tier": arm["reviewer_tier"],
        "arm_reason": arm["reason"],
        "gate_state": gate_state,
    }


def judge_gate(records, *, final: bool = False):
    """required 게이트(`test: gate`) 체크런의 상태를 판정한다 — (상태, 사람이 읽을 줄).

    같은 이름이 여럿이면(재실행) id 가 가장 큰 것만 본다. 체크런이 아예 없으면 미완이다 —
    아직 스케줄 전일 수 있다. 상한을 관장하는 것은 호출자 루프이고 `final` 이 미완을
    실패로 접는다 (fail-closed).
    """
    latest = None
    for record in records:
        if record.get("name") != gate_lib.SELF_CHECK_NAME:
            continue
        if latest is None or gate_lib._run_id(record) >= gate_lib._run_id(latest):
            latest = record

    if latest is None:
        line = f"게이트 체크런 `{gate_lib.SELF_CHECK_NAME}` 없음 — 아직 스케줄 전이거나 조회 실패"
        return ("fail" if final else "wait"), [line]

    status, conclusion = latest.get("status"), latest.get("conclusion")
    line = f"게이트 체크런 `{gate_lib.SELF_CHECK_NAME}`: {status}/{conclusion or '-'}"
    if status != "completed":
        return ("fail" if final else "wait"), [line]
    if conclusion in gate_lib.PASSING_CONCLUSIONS:
        return "pass", [line]
    return "fail", [line]


def _gate_main(argv) -> int:
    final = "--final" in argv
    records = gate_lib.parse_check_runs(sys.stdin.read() if not sys.stdin.isatty() else "")
    state, lines = judge_gate(records, final=final)
    for line in lines:
        print(line)
    if state == "pass":
        print("판정: required 게이트 초록")
        return 0
    if state == "wait":
        print("판정: 대기 — 게이트 미완 (재조회 요망)")
        return 2
    print("판정: required 게이트 비초록 — arm 불가 (fail-closed)")
    return 1


def main(argv) -> int:
    command = argv[1] if len(argv) > 1 else ""
    if command == "gate":
        return _gate_main(argv[2:])

    payload = json.load(sys.stdin)
    if command == "record":
        json.dump(decide_record(payload), sys.stdout, ensure_ascii=False)
    elif command == "scan-refs":
        json.dump(scan_refs(payload.get("body")), sys.stdout, ensure_ascii=False)
        print()
        return 0
    elif command == "arm":
        json.dump(decide_arm(payload), sys.stdout, ensure_ascii=False)
    elif command == "delegate":
        json.dump(decide_delegate(payload), sys.stdout, ensure_ascii=False)
    else:
        print(f"::error::알 수 없는 서브커맨드: {command!r} (record|scan-refs|arm|delegate|gate)")
        return 1
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
