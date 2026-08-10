"""review_verdict.judge 회귀 그물 — 판정 → 체크 색 대응이 fail-closed 로 서 있는지 못박는다.

뒤집히기 쉬운 세 자리를 케이스로 잡는다:
  ① 초록은 `merge_ok` **정확 일치** 하나뿐이다 — 대소문자·공백 관대함이 배관 오류를 삼키면
     이 스크립트가 막으려는 「초록인데 못 민다」가 「빨개야 하는데 초록」으로 재발한다
  ② `unable`·빈 값·미지 값도 빨강이다 — 판정을 못 낸 것이 통과로 읽히면 안 된다
  ③ 빨간 출력에는 교착 출구(dismiss 명령)가 실린다 — 빨간 체크의 로그가 사람이 막혔을 때
     여는 자리라, 출구 안내가 빠지면 문서를 아는 사람만 탈출한다
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_verdict as rv  # noqa: E402

# (설명, 입력 verdict, 기대 종료코드, 출력에 있어야 하는 조각들, 출력에 없어야 하는 조각들)
CASES = [
    ("merge_ok → 초록", "merge_ok", 0, ["머지 가능"], ["::error::"]),
    (
        "needs_changes → 빨강 + 교착 출구  (③)",
        "needs_changes",
        1,
        ["::error::", "수정 필요", "dismissals", "event=DISMISS"],
        [],
    ),
    (
        "unable → 빨강 + 교착 출구  (②③)",
        "unable",
        1,
        ["::error::", "리뷰 불가", "dismissals"],
        [],
    ),
    ("빈 값(판정 미산출) → 빨강  (②)", "", 1, ["::error::", "판정 미산출"], []),
    ("대소문자 관대 금지  (①)", "MERGE_OK", 1, ["::error::", "미지 판정값"], []),
    ("앞 공백 관대 금지  (①)", " merge_ok", 1, ["::error::"], []),
    ("뒤 개행 관대 금지  (①)", "merge_ok\n", 1, ["::error::"], []),
    ("미지 값 fail-closed  (②)", "success", 1, ["::error::", "미지 판정값"], []),
]


def main() -> int:
    failures = 0
    for desc, verdict, want_code, want_bits, ban_bits in CASES:
        code, lines = rv.judge(verdict)
        out = "\n".join(lines)
        if code != want_code:
            print(f"FAIL [{desc}] 종료코드: got {code}, want {want_code}")
            failures += 1
        for bit in want_bits:
            if bit not in out:
                print(f"FAIL [{desc}] 출력에 {bit!r} 없음")
                failures += 1
        for bit in ban_bits:
            if bit in out:
                print(f"FAIL [{desc}] 출력에 {bit!r} 있으면 안 됨")
                failures += 1
    print(f"review_verdict 케이스 {len(CASES)}건 검사 · 실패 {failures}건")
    if not CASES:
        print("FAIL 검사 대상 0건")
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
