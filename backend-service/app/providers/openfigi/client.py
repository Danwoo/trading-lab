"""OpenFIGI HTTP 클라이언트 — 배치 크기·한도가 끝나는 자리.

한도(2026-08 기준 공표값): 키 없이 분당 25요청 · 요청당 10잡, 키가 있으면 분당 25요청 ·
요청당 100잡. 이 어댑터는 **키를 요구하지 않는다** — 키가 있으면 배치가 커져 같은 종목 수를 더
적은 요청으로 처리할 뿐이다. 그래서 `capabilities()` 는 키 유무와 무관하게 `available=True` 다.

배치 쪼개기·요청 간 간격은 이 클래스가 소유한다(구현설계 §5.2 #4) — 호출부에 `sleep` 이나
`page` 가 나오면 그 자체가 경계 위반이다.
"""

import asyncio
from typing import Any

import httpx
from utils.common.retry_utils import is_http_retryable, retry

BASE_URL = "https://api.openfigi.com/v3"

# 요청당 잡 수 상한 — 키 유무로 갈린다(위 docstring).
MAX_JOBS_ANONYMOUS = 10
MAX_JOBS_WITH_KEY = 100

# 분당 25요청 = 요청 간 2.4초. 배치 사이에 이 간격을 두어 한도에 닿기 전에 스스로 멈춘다.
_SECONDS_BETWEEN_BATCHES = 2.4


class OpenFigiClient:
    def __init__(self, api_key: str | None, timeout: float = 20.0, connect_timeout: float = 5.0):
        self.api_key = api_key or None
        self.timeout = httpx.Timeout(timeout, connect=connect_timeout)

    @property
    def max_jobs(self) -> int:
        return MAX_JOBS_WITH_KEY if self.api_key else MAX_JOBS_ANONYMOUS

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-OPENFIGI-APIKEY"] = self.api_key
        return headers

    async def map_jobs(self, jobs: list[dict[str, str]]) -> list[dict[str, Any]]:
        """`/v3/mapping` 을 배치로 호출하고 잡 순서를 유지한 결과 배열을 반환한다."""
        results: list[dict[str, Any]] = []
        batches = [jobs[i : i + self.max_jobs] for i in range(0, len(jobs), self.max_jobs)]
        for index, batch in enumerate(batches):
            if index:
                await asyncio.sleep(_SECONDS_BETWEEN_BATCHES)

            async def _do(payload: list[dict[str, str]] = batch) -> httpx.Response:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(f"{BASE_URL}/mapping", json=payload, headers=self._headers())
                if response.status_code in (429, 502, 503, 504):
                    response.raise_for_status()
                return response

            response = await retry(_do, base_delay=1.0, retryable=is_http_retryable)
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, list):
                raise httpx.DecodingError("OpenFIGI 응답 최상위가 배열이 아닙니다")
            results.extend(body)
        return results
