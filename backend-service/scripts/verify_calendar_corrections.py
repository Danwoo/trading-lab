"""거래일 캘린더 **보정 목록**의 유효성 검증 (fail-closed).

`core/calendar.EXTRA_CLOSURES` 는 「라이브러리가 거래일이라 하지만 실제로는 휴장」인 날이다.
보정은 임시 조치이므로 **낡으면 위험하다** — 라이브러리가 나중에 그 날을 휴장으로 고치면
우리 보정은 아무 일도 안 하는 죽은 줄이 되고, 반대로 우리가 잘못 적었으면 **장이 선 날을
빼먹는다.** 그래서 매 실행이 다시 묻는다:

1. **아직 필요한가** — 보정에 적힌 날을 라이브러리가 여전히 거래일이라 하는가. 아니라고 하면
   그 줄은 지울 때가 된 것이다 (실패로 알린다)
2. **범위 안인가** — 캘린더 수록 범위 밖 날짜를 적어 두면 조용히 아무 효과가 없다
3. **보정 뒤에도 거래일이 남는가** — 한 해를 통째로 지워 버리는 실수를 막는다

**fail-closed**: 보정 대상이 0건이거나 캘린더를 못 읽으면 실패한다. 검사한 개수를 늘 출력한다.

실행: `cd backend-service && uv run python scripts/verify_calendar_corrections.py`
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent.parent / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

# `core.calendar` 는 `core.config` 를 안 탄다 — 설정 더미가 필요 없다.

import exchange_calendars as xcals  # noqa: E402
from core.calendar import EXTRA_CLOSURES  # noqa: E402


def main() -> int:
    if not EXTRA_CLOSURES:
        print("::error::보정 목록이 비어 있습니다 — 검사할 대상이 0건이라 fail-closed 종료")
        print("::error::보정이 정말 필요 없어졌다면 이 스크립트와 EXTRA_CLOSURES 를 함께 지우세요.")
        return 1

    failures: list[str] = []
    checked = 0
    for code, days in sorted(EXTRA_CLOSURES.items()):
        try:
            calendar = xcals.get_calendar(code)
        except Exception as exc:  # noqa: BLE001 — 못 읽으면 검사가 죽은 것이다
            failures.append(f"{code}: 캘린더를 읽지 못했습니다 ({type(exc).__name__})")
            continue
        if not days:
            failures.append(f"{code}: 보정 날짜가 0건입니다 — 빈 항목은 두지 않습니다")
            continue

        first, last = calendar.first_session.date(), calendar.last_session.date()
        for day in sorted(days):
            checked += 1
            if not (first <= day <= last):
                failures.append(f"{code} {day}: 캘린더 수록 범위({first}~{last}) 밖이라 아무 효과가 없습니다")
                continue
            if not calendar.is_session(day):
                failures.append(
                    f"{code} {day}: 라이브러리가 이미 휴장으로 압니다 — 이 보정은 낡았으니 지우세요"
                    f" (exchange_calendars {xcals.__version__})"
                )

        # 한 해를 통째로 지우는 실수 방어 — 보정 뒤에도 거래일이 충분히 남아야 한다.
        #
        # **고정 200일로 재지 않는다.** 캘린더 상한은 유한하고 시간과 함께 움직여, 다음 해
        # 날짜를 미리 넣는 「연 1회 갱신」에서는 그 해가 **부분 수록**이다 — 고정 하한이면
        # 정상 갱신을 「보정이 과합니다」로 오탐한다. 창의 실제 길이 대비 비율로 잰다.
        for year in sorted({day.year for day in days}):
            start = max(dt.date(year, 1, 1), first)
            end = min(dt.date(year, 12, 31), last)
            if start > end:
                print(f"  {code} {year}년: 캘린더 수록 범위({first}~{last}) 밖이라 잔여 거래일 검사를 건너뜁니다")
                continue
            sessions = [ts.date() for ts in calendar.sessions_in_range(start, end)]
            if not sessions:
                continue
            remaining = [day for day in sessions if day not in days]
            partial = (start, end) != (dt.date(year, 1, 1), dt.date(year, 12, 31))
            if len(remaining) < len(sessions) * 0.9:
                scope = "부분 수록" if partial else "전체"
                failures.append(
                    f"{code} {year}년({scope} {start}~{end}): 세션 {len(sessions)}일 중 {len(sessions) - len(remaining)}일을"
                    f" 뺐습니다 — 보정이 과합니다"
                )

    print(f"보정 대상 {checked}건 · 캘린더 {len(EXTRA_CLOSURES)}종 (exchange_calendars {xcals.__version__})")
    for code, days in sorted(EXTRA_CLOSURES.items()):
        print(f"  {code}: {', '.join(str(day) for day in sorted(days))}")

    if failures:
        print(f"::error::캘린더 보정 위반 {len(failures)}건")
        for failure in failures:
            print(f"::error::  {failure}")
        return 1

    print("보정 전부 유효 — 라이브러리는 아직 이 날들을 거래일로 안다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
