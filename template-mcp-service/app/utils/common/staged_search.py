"""단계적 검색 — 전체 조건으로 검색 후 0건이면 핵심 조건만 남겨 점진적 재검색.

외부 검색 API 는 선택 필터를 많이 걸수록 0건이 되기 쉽다. service 계층이 (전체 → 핵심) 순의
검색 시도 목록을 만들어 넘기면, 첫 비-0건 결과를 반환하고 모두 0건이면 마지막 결과를 반환한다.
LLM 프롬프트의 "키워드 줄여 재시도" 지시를 코드로 보장하는 결정론적 폴백 — sub-agent 가 같은
도구를 여러 번 호출하지 않아도 1회 호출로 완화 검색까지 끝난다.
"""

from collections.abc import Awaitable, Callable


def is_empty_out(out: object) -> bool:
    """{data: [...], total_count: N} 응답 모델이 빈 결과인지 — data 가 비면 True."""
    return not getattr(out, "data", None)


async def staged_search[T](
    stages: list[Callable[[], Awaitable[T]]],
    is_empty: Callable[[T], bool] = is_empty_out,
) -> T:
    """stages 를 순서대로 시도 — 첫 비어있지 않은 결과 즉시 반환, 모두 비면 마지막 결과.

    stages[0] 은 전체 조건, 이후로 갈수록 핵심 조건만 남긴 완화 검색. service 가 구성한다.
    """
    last: T | None = None
    for stage in stages:
        last = await stage()
        if not is_empty(last):
            return last
    return last  # type: ignore[return-value]
