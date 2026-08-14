"""리뷰 판정을 체크 색으로 옮긴다 — merge_ok 만 초록, needs_changes 만 빨강 (순수 판정, stdlib 전용).

`cross-review.yml` 의 `verdict` 잡(`review: verdict (비게이트)`)이 publish 잡이 확정한
판정을 env `VERDICT` 로 넘긴다. 종전에는 리뷰 잡 셋(route·cross·publish)이 「리뷰를 돌리는 데
성공했나」만 보고해서, 판정이 `needs_changes` 여도 체크가 전부 초록이었다 — 머지는
네이티브 `CHANGES_REQUESTED` 리뷰가 막는데 체크 목록은 그 사실을 안 보여줘, 화면만 보는
사람에게 「초록인데 못 민다」가 된다 (#23 Task 10, PR #68 실측: 체크 26개 전부 초록 +
mergeStateStatus=BLOCKED).

## 판정 → 체크 색의 단일 표 (CHECK_CONCLUSION)

  merge_ok       → success (초록 — 통과)
  needs_changes  → failure (빨강 — 리뷰가 수정을 요구했다. **막는 게 맞다**)
  unable         → skipped (판정을 못 냈다 — 사람 판단으로 넘긴다)
  빈 값·그 외     → failure (publish 가 판정에 도달하지 못했거나 미지 값. 애매하면 빨강)

unable 을 빨강에서 뺀 이유 (2026-08-12): 리드가 쓰는 Orca 는 required 여부와 무관하게
빨간 체크가 있으면 머지 버튼을 잠근다. unable 은 「코드에 문제가 있다」가 아니라 「판정을
못 냈다」인데 둘을 같은 빨강으로 칠하면, 인터넷 끊김이 코드 결함과 똑같이 머지를 막는다
(PR #104 실측: kimi 접수 확인 오판 → unable 빨강 3회, 그중 2회는 리뷰가 7~8분 뒤 실제로
merge_ok 로 끝났는데 체크만 빨갛게 남았다). 조치 안내는 publish 의 판정 코멘트가 맡는다 —
조용히 사라지는 게 아니다.

이 표는 두 소비자가 같이 쓴다:
  ① `cross-review.yml` verdict 잡 — unable 은 잡 `if:` 가 스킵(= Skipped)하고, 나머지는
     이 스크립트의 `judge` 가 종료코드로 색을 낸다 (잡 `if:` 의 `!= 'unable'` 은 이 표의
     표현이다 — 표를 바꾸면 그 조건도 같이 바꾼다)
  ② `review-record.yml` — 워크플로가 끝난 뒤 도착한 판정 마커를 `check-payload` 모드로
     같은 이름의 체크런에 옮겨 적는다 (늦은 판정이 체크에 반영되는 경로)

정확 일치만 받는다 — 대소문자·공백을 다듬지 않는다. 다듬는 관대함은 배관 오류(따옴표 유실·
값 변형)를 초록으로 삼킨다.

## 이 체크가 아닌 것

  · **required 가 아니다** — 리뷰 인프라가 죽어도 사람 머지를 막지 않는다
    (설계 §4 「AI 판정이 작업 정지 장치가 되지 않는다」). 빨강은 알림이지 차단이 아니다.
  · **`test: ` 접두를 쓰지 않는다** — required 게이트(`verify_upstream_gate.py`)가
    그 접두를 전수 판정하므로, 판정 체크가 그 접두를
    달면 `needs_changes` 하나가 사람 머지까지 막는다.
  · 머지를 실제로 막는 것은 기록기(review-record)가 남기는 네이티브 `CHANGES_REQUESTED`
    리뷰다 — 이 체크는 그 사실을 체크 목록에 보이게만 한다.

실행: 인자 없음 = judge (verdict 잡) · `check-payload` = 체크런 JSON (기록기). 입력은 둘 다 env `VERDICT`.
"""

import json
import os
import sys

# 판정 → 체크 결론의 단일 표. 소비자는 머리 주석의 ①②. 어휘 밖 값은 표에 없다 —
# 소비자가 fail-closed(failure)로 접는다.
CHECK_CONCLUSION = {
    "merge_ok": "success",
    "needs_changes": "failure",
    "unable": "skipped",
}

# 교착 출구 — 리뷰 경로가 죽어 새 판정이 안 나오는데 CHANGES_REQUESTED 리뷰가 살아 있으면
# 머지가 영영 막힌다. 그때는 사람이 리뷰를 해제(dismiss)하는 것이 유일한 출구라, 빨간
# 체크의 로그(사람이 「왜 빨갛지」하고 여는 자리)에 그 명령을 싣는다. 상세는 설계 문서
# `.docs/specs/2026-08-08-ci-review-architecture-design.md` §4.
DEADLOCK_EXIT = (
    "교착 출구: 리뷰 경로가 죽어 새 판정이 안 나오는데 CHANGES_REQUESTED 리뷰가 살아\n"
    "머지가 막혀 있다면, 사람이 그 리뷰를 해제한다 —\n"
    "  gh api -X PUT repos/<owner>/<repo>/pulls/<PR>/reviews/<리뷰ID>/dismissals \\\n"
    '    -f message="<사유>" -f event=DISMISS\n'
    "(리뷰 ID: gh api repos/<owner>/<repo>/pulls/<PR>/reviews — 상세는 설계 문서 §4)"
)


def judge(verdict):
    """(종료코드, 사람이 읽을 줄 목록) 을 낸다 — merge_ok 만 0."""
    lines = [f"입력 판정: {verdict!r} (publish 잡 출력)"]
    if verdict == "merge_ok":
        lines.append("판정: merge_ok (머지 가능) — 초록")
        return 0, lines
    if verdict == "needs_changes":
        lines.append(
            "::error::리뷰 판정 needs_changes (수정 필요) — PR 의 판정 코멘트(리뷰 본문)를 "
            "읽고 고쳐 push 하면 재리뷰가 돈다. 머지를 막는 것은 이 체크가 아니라 기록기가 "
            "남긴 네이티브 CHANGES_REQUESTED 리뷰다 — 이 체크는 그 사실의 가시화다."
        )
        lines.append(DEADLOCK_EXIT)
        return 1, lines
    if verdict == "unable":
        # 정상 배선에서는 도달하지 않는다 — cross-review.yml 의 verdict 잡 `if:` 가 unable 을
        # 스킵(Skipped)한다 (CHECK_CONCLUSION 표). 여기 왔다는 것은 그 배선이 어긋났다는
        # 뜻이라 fail-closed 로 빨강을 유지한다. 문구 선두 「리뷰 판정 unable」은
        # runner_freeze_rerun.py 의 UNABLE_PREFIX 와 lockstep 이다 — 바꾸면 그쪽도 바꾼다.
        lines.append(
            "::error::리뷰 판정 unable (리뷰 불가) — 이 잡은 unable 이면 워크플로 if: 가 "
            "스킵해야 한다 (CHECK_CONCLUSION: unable → skipped). 잡이 실행된 채 unable 을 "
            "받았다는 것은 배선이 어긋났다는 뜻이다 — fail-closed 로 빨강. 조치: Actions run "
            "로그(원인 분류·막힌 지점)를 보고 Re-run all jobs 하거나 사람이 직접 리뷰하라."
        )
        lines.append(DEADLOCK_EXIT)
        return 1, lines
    if verdict == "":
        lines.append(
            "::error::판정 미산출 — publish 가 판정에 도달하지 못했다 (상류 취소·새 커밋 "
            "추월·잡 실패). fail-closed 로 빨강. 새 커밋에 추월된 run 이라면 새 run 의 "
            "체크가 이 커밋 대신 현재 head 에 확정 상태를 쓴다."
        )
        return 1, lines
    lines.append(
        f"::error::미지 판정값 {verdict!r} — 판정 어휘는 merge_ok·needs_changes·unable "
        "셋뿐이다. 배관(publish 잡 출력)이 변형됐거나 어휘가 갈렸다. fail-closed 로 빨강."
    )
    return 1, lines


def check_payload(verdict):
    """기록기(review-record)가 체크런으로 옮길 {conclusion, title, summary} 를 낸다.

    체크런 이름은 verdict 잡의 체크와 같다 — GitHub 은 같은 앱·같은 이름의 체크런 중
    최신 것을 PR 체크 목록에 보이므로, 워크플로가 끝난 뒤 도착한 판정이 이걸로 체크
    색을 덮어쓴다. 색은 CHECK_CONCLUSION 한 표에서 나온다 — verdict 잡과 갈릴 수 없다.
    """
    conclusion = CHECK_CONCLUSION.get(verdict)
    if conclusion is None:
        return {
            "conclusion": "failure",
            "title": f"미지 판정값 {verdict!r} — fail-closed 로 빨강",
            "summary": (
                f"판정 어휘는 merge_ok·needs_changes·unable 셋뿐인데 {verdict!r} 를 "
                "받았다. 배관(마커 파싱)이 변형됐거나 어휘가 갈렸다."
            ),
        }
    titles = {
        "merge_ok": "판정 merge_ok (머지 가능) — 초록",
        "needs_changes": "판정 needs_changes (수정 필요) — 빨강",
        "unable": "판정 unable (리뷰 불가) — Skipped (사람 판단으로 넘긴다)",
    }
    summaries = {
        "merge_ok": "리뷰 판정 merge_ok — 통과.",
        "needs_changes": (
            "리뷰가 수정을 요구했다. PR 의 판정 코멘트(리뷰 본문)를 읽고 고쳐 push 하면 "
            "재리뷰가 돈다. 머지를 실제로 막는 것은 기록기가 남긴 네이티브 "
            "CHANGES_REQUESTED 리뷰다 — 이 체크는 그 사실의 가시화다.\n\n"
            + DEADLOCK_EXIT
        ),
        "unable": (
            "판정을 못 냈다 — 통과도 실패도 아니라 사람 판단으로 넘긴다. 원인과 조치는 "
            "PR 의 판정 코멘트(CAUTION 배너)에 있다. 승인 리뷰가 없어 자동 머지는 arm "
            "되지 않는다."
        ),
    }
    return {
        "conclusion": conclusion,
        "title": titles[verdict],
        "summary": (
            f"{summaries[verdict]}\n\n기록기(review-record)가 판정 코멘트의 기계 마커를 "
            "체크런으로 옮겨 적었다 — 판정 → 색 매핑은 scripts/review_verdict.py "
            "CHECK_CONCLUSION 한 표다."
        ),
    }


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    verdict = os.environ.get("VERDICT", "")
    if argv and argv[0] == "check-payload":
        print(json.dumps(check_payload(verdict), ensure_ascii=False))
        return 0
    code, lines = judge(verdict)
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
