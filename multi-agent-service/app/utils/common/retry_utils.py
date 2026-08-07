import inspect
from collections.abc import Awaitable, Callable

import httpx
from core.logger import logger
from tenacity import (
    AsyncRetrying,
    Retrying,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


def is_http_retryable(exc: BaseException) -> bool:
    """HTTP 재시도 대상: 네트워크 오류 또는 일시적 서버 오류 (502·503·504)."""
    if isinstance(exc, (httpx.TransportError, httpx.TimeoutException)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (502, 503, 504)
    return False


def _retry_kwargs(max_retries: int, base_delay: float, label: str, retryable) -> dict:
    def _before_sleep(retry_state) -> None:
        logger.warning(
            f"{label} attempt {retry_state.attempt_number} failed: "
            f"{retry_state.outcome.exception()}. "
            f"Retrying in {retry_state.next_action.sleep:.1f}s..."
        )

    return {
        "retry": retry_if_exception(retryable) if retryable else retry_if_exception_type(Exception),
        "wait": wait_exponential(multiplier=base_delay, min=base_delay),
        "stop": stop_after_attempt(max_retries + 1),
        "before_sleep": _before_sleep,
        "reraise": True,
    }


def retry[T](
    fn: Callable[[], T] | Callable[[], Awaitable[T]],
    max_retries: int = 2,
    base_delay: float = 1.0,
    label: str = "operation",
    retryable: Callable[[BaseException], bool] | None = None,
) -> T | Awaitable[T]:
    """동기·비동기 재시도 헬퍼. 실패 시 지수 백오프 후 재시도.

    fn 이 async 함수면 await 할 코루틴을 반환(``await retry(afn)``), 동기면 결과를 그대로 반환.
    retryable 미지정 시 모든 예외 재시도, 지정 시 그 예측자 충족 예외만 (예: is_http_retryable).
    """
    kwargs = _retry_kwargs(max_retries, base_delay, label, retryable)
    if inspect.iscoroutinefunction(fn):

        async def _run_async() -> T:
            async for attempt in AsyncRetrying(**kwargs):
                with attempt:
                    return await fn()
            raise RuntimeError("unreachable")

        return _run_async()

    for attempt in Retrying(**kwargs):
        with attempt:
            return fn()
    raise RuntimeError("unreachable")  # tenacity reraises on exhausted retries
