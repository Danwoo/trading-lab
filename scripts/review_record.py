"""판정 코멘트 → GitHub 네이티브 PR 리뷰 기록기의 순수 판정 — stdlib 전용 (#23 Task 7).

`.github/workflows/review-record.yml` 이 이것을 부른다. 리뷰어(Orca 워커 또는 사람)는 판정을
PR 코멘트의 기계 마커(`<!-- cross-review v1 model=… verdict=… sha=… -->`)로 남기고, 워크플로가
그것을 `github-actions[bot]` 명의의 네이티브 리뷰(Approve / Request changes)로 옮겨 적는다 —
GitHub 이 자기 PR 자기 승인을 금지해 로컬 `gh`(리드 계정)로는 자기 PR 승인이 서지 않기 때문이다.

## 보안 경계 (공개 레포 — 이 넷이 위조 방어의 전부다)

1. **저자 필터**: 마커는 `OWNER`·`MEMBER`·`COLLABORATOR` 가 쓴 코멘트에서만 읽는다.
   승인을 required 로 걸지 않는 이 설계에서 유일한 위조 방어다 — 없으면 누구든 위조 마커로
   봇 승인·자동 머지를 일으킬 수 있다 (head sha 는 공개 정보다).
2. **sha 는 40자 동등 비교**: 접두사 매치 금지 — 접두 비교는 앞자리만 같은 다른 커밋의
   판정을 통과시킨다.
3. **`source=manual` 마커는 arm 하지 않는다**: 사람이 타이핑한 한 줄일 수 있다 (#285 규약 —
   수동 리뷰 마커는 기록은 되지만 자동 머지 권한을 얻지 못한다).
4. **봇 PR 의 상승 종류를 못 읽으면 arm 하지 않는다**: 종류는 PR 제목(`bump X from A to B`)에서
   읽고, 파싱 실패는 fail-closed 다.

## 자동 머지 arm 조건 (전부 참일 때만 — 설계 §4)

  ① required 게이트 초록 — `gate` 서브커맨드 (워크플로가 완료까지 재조회한다)
  ② 승인 리뷰가 있고 그 `commit_id` 가 현재 head 와 같다 — `arm`
  ③ `risk: low` **또는** 저자가 봇이면서 major 상승이 아니다 — `arm`

위험도의 SoT 는 **이슈의 risk 라벨**이고 판정 시점마다 fresh 조회한다 (merge-router.yml 이
못 박은 규칙 승계). 이슈 연결은 `closingIssuesReferences` 가 아니라 **PR 본문 파싱**으로 읽는다
(`Refs #N` 도 위험도 출처 — 2026-08-09 리드 결정. closing 키워드만 잡으면 위험도를 읽히려고
PR 마다 전용 이슈를 만들게 된다). 여러 이슈면 가장 높은 위험, 하나도 못 읽으면 미선언 = 고위험.

## 서브커맨드 (stdin JSON → stdout JSON, `gate` 만 종료코드 프로토콜)

  record  코멘트 목록 + head 에서 기록할 리뷰를 판정한다
  refs    PR 본문에서 참조 이슈 번호를 뽑는다 (한 줄에 하나)
  arm     승인·위험도·봇 상승 종류로 arm 여부를 판정한다
  gate    check-runs JSON 에서 required 게이트(`test: gate`)의 상태를 판정한다
          — 종료코드 0 초록 · 1 실패 · 2 미완(재조회 요망), `--final` 은 미완을 실패로 접는다
"""

from __future__ import annotations

import json
import re
import sys

import verify_upstream_gate as gate_lib

TRUSTED_ASSOCIATIONS = ("OWNER", "MEMBER", "COLLABORATOR")
BOT_REVIEWER_LOGIN = "github-actions"

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
_REF_BLOCK = re.compile(
    r"\b(?:refs?|close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b:?\s*"
    r"(#\d+(?:\s*(?:,|and)?\s*#\d+)*)",
    re.IGNORECASE,
)
_REF_NUMBER = re.compile(r"#(\d+)")

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
        if comment.get("author_association") not in TRUSTED_ASSOCIATIONS:
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
            "(저자 필터 OWNER/MEMBER/COLLABORATOR · 낡은 sha·접두 sha 불인정)",
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


def parse_refs(body) -> list[int]:
    """PR 본문에서 참조 이슈 번호를 뽑는다 (중복 제거, 오름차순)."""
    numbers: set[int] = set()
    for m in _REF_BLOCK.finditer(body or ""):
        for n in _REF_NUMBER.findall(m.group(1)):
            numbers.add(int(n))
    return sorted(numbers)


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


def read_risk(issue_risks):
    """이슈별 라벨에서 위험도를 접는다 — 이슈 없음·라벨 없음은 미선언 = 고위험 취급."""
    if not issue_risks:
        return "undeclared", "연결 이슈 없음 — 위험도 판독 불가"
    per_issue = {}
    for number, labels in issue_risks.items():
        labels = labels or []
        if "risk: high" in labels:
            per_issue[number] = "high"
        elif "risk: low" in labels:
            per_issue[number] = "low"
        else:
            per_issue[number] = "undeclared"
    evidence = ", ".join(f"#{n}={per_issue[n]}" for n in sorted(per_issue, key=str))
    if any(v == "high" for v in per_issue.values()):
        return "high", evidence
    if any(v == "undeclared" for v in per_issue.values()):
        return "undeclared", evidence
    return "low", evidence


def decide_arm(payload) -> dict:
    """자동 머지 arm 여부 — 조건 ②③ 을 판정한다 (① 게이트는 `gate` 서브커맨드가 맡는다)."""
    head_sha = payload.get("head_sha") or ""
    marker_sha = payload.get("marker_sha") or ""
    risk, evidence = read_risk(payload.get("issue_risks") or {})
    bump = classify_bump(payload.get("pr_title"))
    base = {"arm": False, "risk": risk, "risk_evidence": evidence, "bot_bump": bump}

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
    elif command == "refs":
        for number in parse_refs(payload.get("body")):
            print(number)
        return 0
    elif command == "arm":
        json.dump(decide_arm(payload), sys.stdout, ensure_ascii=False)
    else:
        print(f"::error::알 수 없는 서브커맨드: {command!r} (record|refs|arm|gate)")
        return 1
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
