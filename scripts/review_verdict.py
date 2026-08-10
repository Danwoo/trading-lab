"""리뷰 판정을 체크 색으로 옮긴다 — merge_ok 만 초록, 그 외 전부 빨강 (순수 판정, stdlib 전용).

`cross-review.yml` 의 `verdict` 잡(`review: verdict (비게이트)`)이 publish 잡이 확정한
판정을 env `VERDICT` 로 넘긴다. 종전에는 리뷰 잡 셋(route·cross·publish)이 「리뷰를 돌리는 데
성공했나」만 보고해서, 판정이 `needs_changes` 여도 체크가 전부 초록이었다 — 머지는
네이티브 `CHANGES_REQUESTED` 리뷰가 막는데 체크 목록은 그 사실을 안 보여줘, 화면만 보는
사람에게 「초록인데 못 민다」가 된다 (#23 Task 10, PR #68 실측: 체크 26개 전부 초록 +
mergeStateStatus=BLOCKED).

## 판정 규칙 (fail-closed)

  merge_ok       → 0 (초록)
  needs_changes  → 1 (빨강 — 리뷰가 수정을 요구했다)
  unable         → 1 (빨강 — 판정을 못 냈다. 못 낸 것이 통과로 읽히면 안 된다)
  빈 값·그 외     → 1 (빨강 — publish 가 판정에 도달하지 못했거나 미지 값. 애매하면 빨강)

정확 일치만 받는다 — 대소문자·공백을 다듬지 않는다. 다듬는 관대함은 배관 오류(따옴표 유실·
값 변형)를 초록으로 삼킨다.

## 이 체크가 아닌 것

  · **required 가 아니다** — 리뷰 인프라가 죽어도(unable) 사람 머지를 막지 않는다
    (설계 §4 「AI 판정이 작업 정지 장치가 되지 않는다」). 빨강은 알림이지 차단이 아니다.
  · **`test: ` 접두를 쓰지 않는다** — required 게이트(`verify_upstream_gate.py`)와
    merge-router 의 전수 초록 게이트가 그 접두를 전수 판정하므로, 판정 체크가 그 접두를
    달면 `needs_changes` 하나가 사람 머지까지 막는다.
  · 머지를 실제로 막는 것은 기록기(review-record)가 남기는 네이티브 `CHANGES_REQUESTED`
    리뷰다 — 이 체크는 그 사실을 체크 목록에 보이게만 한다.
"""

import os

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
        lines.append(
            "::error::리뷰 판정 unable (리뷰 불가) — 판정을 못 냈다. 못 낸 것이 통과로 "
            "읽히면 안 된다 (fail-closed). 이 체크는 required 가 아니라 사람 머지를 막지 "
            "않는다 — 승인 리뷰가 없어 자동 머지도 arm 되지 않는다. 조치: Actions run "
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


def main():
    code, lines = judge(os.environ.get("VERDICT", ""))
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
