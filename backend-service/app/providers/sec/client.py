"""SEC EDGAR HTTP 클라이언트 — 인증·한도·재시도가 끝나는 자리.

SEC 는 API 키를 요구하지 않는 대신 **연락처가 담긴 User-Agent 를 요구**한다(전자공시 접근 정책).
그래서 이 어댑터의 `api_key` 자리는 비밀값이 아니라 연락처 문자열이다 — 공개돼도 무방하므로
로그·오류 메시지에 그대로 남겨도 된다.

**연락처가 없으면 호출하지 않는다.** 실측(2026-08-07): 이메일이 없는 User-Agent 는 403 이고,
`python-httpx/0.28.1` 같은 기본 UA 도 403 이다. 아무 이메일이나(예: `example.com`) 채워 넣으면
200 이 나오지만 그건 우리를 거짓으로 밝히는 것이라 하지 않는다 — 대신 `capabilities()` 가
"연락처 미설정"을 사유로 내고 화면이 그것을 보여준다.

한도는 초당 10요청이 공표된 상한이다. 이 어댑터가 실제로 치는 엔드포인트는 전 종목 스냅샷
파일 하나뿐이라 한도에 근접할 일이 없어 별도 스로틀을 두지 않는다 — 종목당 조회를 하는
엔드포인트를 나중에 추가하면 그때 이 클래스가 스로틀을 소유한다(구현설계 §5.2 #4).
"""

import re
from typing import Any

import httpx
from utils.common.retry_utils import is_http_retryable, retry

BASE_URL = "https://www.sec.gov"

# 전 종목(티커·CIK·상장 거래소) 스냅샷. 종목당 호출이 아니라 파일 하나라 국내 소스와 같은
# "날짜별 전종목" 성격이다 — 유니버스가 커져도 호출 수가 늘지 않는다.
COMPANY_TICKERS_EXCHANGE_PATH = "/files/company_tickers_exchange.json"

# SEC 가 받아들이는 UA 인지 가르는 최소 조건 — 연락처(이메일 모양)가 들어 있어야 한다.
_CONTACT_PATTERN = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


def contact_is_usable(contact: str | None) -> bool:
    return bool(contact and _CONTACT_PATTERN.search(contact))


class SecClient:
    def __init__(self, contact: str, timeout: float = 30.0, connect_timeout: float = 5.0):
        self.contact = contact.strip()
        self.timeout = httpx.Timeout(timeout, connect=connect_timeout)

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.contact,
            "Accept-Encoding": "gzip, deflate",
            "Host": "www.sec.gov",
        }

    async def company_tickers_exchange(self) -> dict[str, Any]:
        """`{"fields": [...], "data": [[...], ...]}` 형태의 전 종목 스냅샷 원문을 그대로 반환한다.

        원문 dict 가 이 클래스 밖으로 나가는 것은 같은 패키지의 `mapper` 까지다 — 어댑터가
        정규화 모델로 바꾼 뒤에야 `providers/` 경계를 넘는다.
        """

        async def _do() -> httpx.Response:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(
                    f"{BASE_URL}{COMPANY_TICKERS_EXCHANGE_PATH}",
                    headers=self._headers(),
                )
            if response.status_code in (429, 502, 503, 504):
                response.raise_for_status()
            return response

        response = await retry(_do, base_delay=0.5, retryable=is_http_retryable)
        response.raise_for_status()
        return response.json()
