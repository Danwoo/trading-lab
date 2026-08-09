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
4. **봇 PR 의 상승 종류를 못 읽으면 arm 하지 않는다**: 종류는 PR 제목(`bump X from A to B`)에서
   읽고, 파싱 실패는 fail-closed 다.

## 자동 머지 arm 조건 (전부 참일 때만 — 설계 §4)

  ① required 게이트 초록 — `gate` 서브커맨드 (워크플로가 완료까지 재조회한다)
  ② 승인 리뷰가 있고 그 `commit_id` 가 현재 head 와 같다 — `arm`
  ③ 저자 벤더 ≠ 리뷰어 벤더, 또는 같은 벤더여도 **그 벤더의** 작성 티어를 안다 — `arm`
  ④ `risk: low` **또는** 저자가 봇이면서 major 상승이 아니다 — `arm`

조건 ③ 은 cross-review.yml 의 동일-벤더 폴백 차단을 arm 조건으로 승계한 것이다: 리뷰어
벤더가 저자 벤더와 같으면 교차 축이 티어뿐인데, 작성 티어를 모르면 동일-티어 자기리뷰
가능성을 배제할 수 없다. 저자 신원은 커밋 author 이메일(1순위)·브랜치명으로 읽고, 판독
자체가 안 되면 arm 하지 않는다 (fail-closed). 신원 형식의 SoT 는 `review_route` 하나다.

위험도의 SoT 는 **이슈의 risk 라벨**이고 판정 시점마다 fresh 조회한다 (merge-router.yml 이
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
BOT_REVIEWER_LOGIN = "github-actions"
# GITHUB_TOKEN 으로 올린 코멘트의 `author_association` 은 이 레포에서 `NONE` 이다
# (2026-08-09 실측) — cross-review publish 폴백 게시분이 여기 걸려 영영 안 읽혔다.
TRUSTED_BOT_LOGINS = (BOT_REVIEWER_LOGIN,)
REVIEWER_VENDORS = ("claude", "kimi", "codex")
# `review_route` 가 티어를 모으는 벤더 — 지금은 claude 뿐이다. 티어 축은 **리뷰어 벤더의**
# 티어를 알 때만 자기리뷰 차단을 푼다: 혼재 저자(claude+kimi)에서 claude 티어를 안다는
# 이유로 kimi 리뷰의 차단이 풀리면, 아는 티어와 겹치는 벤더가 달라 아무것도 배제하지 못한다.
TIER_KNOWN_VENDOR = "claude"

# cross-review.yml 의 마커 게시부·merge-router.yml 의 arm 가드와 같은 문법. sha 자릿수는
# 여기서 안 좁힌다 — 접두 sha 를 정규식에서 거르면 「40자 동등 비교」가 검증 불가능한
# 암묵이 된다. 아래 판정이 길이 40 + 문자열 동등을 명시적으로 검사한다.
_MARKER = re.compile(
    r"<!-- cross-review v1 model=(?P<model>claude|kimi|codex)"
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

# dependabot 제목 형식: `build(deps): bump X from A to B in /path` (설계 §2-1 실측).
_TITLE_BUMP = re.compile(r"\bfrom\s+(\S+)\s+to\s+(\S+)")

VERDICT_TO_EVENT = {"merge_ok": "APPROVE", "needs_changes": "REQUEST_CHANGES"}
EVENT_TO_STATE = {"APPROVE": "APPROVED", "REQUEST_CHANGES": "CHANGES_REQUESTED"}


def _normalize_login(login) -> str:
    # REST 는 `github-actions[bot]`, `gh pr view` 는 `github-actions` 로 준다
    return (login or "").removesuffix("[bot]")


def find_marker(comments, head_sha):
    """저자 필터를 통과한 코멘트에서 head 와 40자 동등한 마지막 유효 마커를 찾는다.

    반환은 dict(model·verdict·manual·sha·comment_url) 또는 None. 코멘트는 시간 오름차순
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
    return (
        comment.get("user_type") == "Bot"
        and _normalize_login(comment.get("user_login")) in TRUSTED_BOT_LOGINS
    )


def _bot_reviews_for_head(reviews, head_sha):
    out = []
    for review in reviews or []:
        if not isinstance(review, dict):
            continue
        if _normalize_login(review.get("user_login")) != BOT_REVIEWER_LOGIN:
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
            "(저자 필터 OWNER/MEMBER/COLLABORATOR + github-actions[bot] · "
            "낡은 sha·접두 sha 불인정)",
        }

    result = {
        **base,
        "verdict": marker["verdict"],
        "model": marker["model"],
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
    본문만 읽는 사람은 그 PR 이 왜 저위험으로 접혔는지 알 수 없다.

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
    # 주석은 줄 수를 보존해 가린다 — 한 줄로 접으면 앞뒤 산문이 이어붙는다.
    # 닫히지 않은 `<!--` 는 그 자리부터 끝까지 주석으로 본다 (fail-closed)
    masked = _HTML_COMMENT.sub(
        lambda m: "\n".join(_DROP_MARK for _ in m.group(0).splitlines()), raw
    )
    if "<!--" in masked:
        head, _, tail = masked.partition("<!--")
        masked = head + "\n".join(_DROP_MARK for _ in ("<!--" + tail).splitlines())

    prose: list[str] = []
    fence: str | None = None
    in_quote = False

    def drop():
        # 비-공백 자리표시 — 버린 자리를 사이에 두고 앞뒤 산문이 한 문장으로 붙지 않게
        prose.append(_DROP_MARK)

    for line in masked.splitlines():
        opened = _FENCE.match(line)
        if fence is not None:
            if (
                opened
                and opened.group("mark")[0] == fence[0]
                and len(opened.group("mark")) >= len(fence)
            ):
                fence = None
            drop()
            continue
        if opened:
            fence = opened.group("mark")
            drop()
            continue
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
        prose.append(_INLINE_CODE.sub(_DROP_MARK, line))

    refs = _numbers_in("\n".join(prose))
    return {"refs": sorted(refs), "dropped": sorted(_numbers_in(raw) - refs)}


def parse_refs(body) -> list[int]:
    """PR 본문의 산문에서 참조 이슈 번호를 뽑는다 (중복 제거, 오름차순)."""
    return scan_refs(body)["refs"]


def _major_of(version):
    m = re.match(r"v?(\d+)", version or "")
    return int(m.group(1)) if m else None


def classify_bump(title):
    """PR 제목에서 버전 상승 종류를 읽는다 — 못 읽으면 None (fail-closed)."""
    m = _TITLE_BUMP.search(title or "")
    if not m:
        return None
    old, new = _major_of(m.group(1)), _major_of(m.group(2))
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
    unknown = sorted(
        set(dropped) - {r.get("number") for r in refs if isinstance(r, dict)}
    )

    def fold(risk, evidence, excluded):
        if unknown and risk != "high":
            listed = ", ".join(f"#{n}" for n in unknown)
            return (
                "undeclared",
                f"{evidence} · 코드·인용에서 버린 참조 후보({listed}) — 선언이었을 수 있어 "
                "미선언으로 접는다",
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
        return fold(
            "undeclared", f"{evidence} — 이슈 참조 0건, 위험도 판독 불가", excluded
        )
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

    **한계**: 마커는 `model=`(벤더)만 싣고 리뷰어 티어를 싣지 않으므로, 저자 티어를 안다는
    것이 「다른 티어가 리뷰했다」의 증명은 아니다 — 폴백이 반대 티어를 고른다는 cross-review
    쪽 계약을 믿는 것이다 (종전 bash 조건 승계). 실제로 대조하려면 마커에 리뷰어 티어를
    실어야 한다.
    """
    emails = payload.get("commit_author_emails")
    reviewer = payload.get("marker_model") or ""
    result = {
        "self_vendor": None,
        "author_models": None,
        "author_tier": None,
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
            "block": f"리뷰어 벤더 미상({reviewer!r}) — 자기리뷰 여부를 판정할 수 없다 "
            "(fail-closed)",
        }

    identity = review_route.identify_author(emails, payload.get("head_ref") or "")
    author_models = identity["author_models"]
    unknown_agentish = identity["unknown_agentish"]
    self_vendor = reviewer in [v for v in author_models.split(",") if v]
    result = {
        "self_vendor": self_vendor,
        "author_models": author_models or None,
        "author_tier": identity["author_tier"],
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
    # 아는 티어가 **리뷰어 벤더의 것**일 때만 차단이 풀린다 — 혼재 저자에서 다른 벤더의
    # 티어로 풀면 동일-티어 자기리뷰를 배제하지 못한 채 통과한다
    tier_known = identity["author_tier"] is not None and reviewer == TIER_KNOWN_VENDOR
    if self_vendor and not tier_known:
        return {
            **result,
            "block": f"동일-벤더 리뷰({reviewer}) + 그 벤더의 작성 티어 미상 — 동일-티어 "
            "자기리뷰를 배제할 수 없어 arm 하지 않는다 (게이트만 사람에게)",
        }
    return result


def decide_arm(payload) -> dict:
    """자동 머지 arm 여부 — 조건 ②③④ 를 판정한다 (① 게이트는 `gate` 서브커맨드가 맡는다)."""
    head_sha = payload.get("head_sha") or ""
    marker_sha = payload.get("marker_sha") or ""
    risk, evidence, excluded_prs = read_risk(
        payload.get("issue_refs") or [], payload.get("dropped_refs") or []
    )
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
            "reason": "현재 head 에 대한 봇 승인 리뷰 없음 (조건 ② 미충족 — "
            "리뷰 게시 실패 또는 push 로 낡음)",
        }

    if identity["block"]:
        return {**base, "reason": f"조건 ③ 미충족 — {identity['block']}"}

    if risk == "low":
        return {
            **base,
            "arm": True,
            "reason": f"risk: low ({evidence}) + 봇 승인 — arm",
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
    records = gate_lib.parse_check_runs(
        sys.stdin.read() if not sys.stdin.isatty() else ""
    )
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
    else:
        print(
            f"::error::알 수 없는 서브커맨드: {command!r} (record|scan-refs|arm|gate)"
        )
        return 1
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
