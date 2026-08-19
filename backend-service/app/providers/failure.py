"""소스 호출 실패를 **사람이 읽고 다음에 무엇을 할지 아는 문장**으로 바꾼다.

이 문자열은 `tn_ingest_run.failed_reason` 에 적히고 **화면에 그대로 보인다.** 그래서 두 가지를
동시에 지켜야 한다:

1. **다음 행동을 말한다.** 403 은 「앱 설정에서 이 서버 IP 를 허용하라」는 아주 구체적인 요구인데,
   원문(`Client error '403 Forbidden' for url '...'`)은 그 말을 못 한다.
2. **원문을 싣지 않는다.** `httpx.HTTPStatusError` 의 문자열에는 요청 URL 이 통째로 들어 있고,
   data.go.kr 은 인증키를 **쿼리 파라미터로** 받는다 — 원문을 그대로 적으면 키가 화면에 실린다.
   가림(`redact_secrets`)은 마지막 방어층이지 첫 방어층이 아니다.

기술 원문은 버리지 않는다 — 로그로 간다. 화면과 로그의 독자가 다르기 때문이다.
"""

from __future__ import annotations

import httpx

#: 상태 코드 → (무엇이 일어났나, 무엇을 하면 되나). 코드를 모르면 아래 기본 문장으로 떨어진다.
_BY_STATUS: dict[int, tuple[str, str]] = {
    400: ("소스가 요청을 거절했습니다", "요청 구간·종목 코드가 그 소스에서 유효한지 확인하세요"),
    401: ("소스가 자격을 거절했습니다", "설정 화면에서 키를 다시 넣으세요 — 값이 틀렸거나 만료됐습니다"),
    403: (
        "소스가 이 서버의 접근을 막았습니다",
        "발급처 앱 설정에서 **이 서버의 IP 를 허용 목록에 등록**하세요. 키가 맞아도 IP 가 안 열리면 막힙니다",
    ),
    404: ("소스에 그 자원이 없습니다", "종목 코드와 시장이 맞는지 확인하세요"),
    429: ("소스의 호출 한도에 걸렸습니다", "잠시 뒤 다시 시도하세요 — 받은 것까지는 저장돼 있습니다"),
}

_SERVER_SIDE = ("소스 쪽에 장애가 있습니다", "잠시 뒤 다시 시도하세요 — 우리 쪽 설정 문제가 아닙니다")


def describe_provider_failure(exc: BaseException, source: str) -> str:
    """화면에 낼 실패 사유. **URL·원문·자격을 담지 않는다.**"""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        what, todo = _BY_STATUS.get(status, _SERVER_SIDE if status >= 500 else _BY_STATUS[400])
        return f"{source}: {what} (HTTP {status}). {todo}."
    if isinstance(exc, httpx.TimeoutException):
        return f"{source}: 소스가 제때 응답하지 않았습니다. 잠시 뒤 다시 시도하세요."
    if isinstance(exc, httpx.TransportError):
        return f"{source}: 소스에 연결하지 못했습니다. 네트워크와 소스 상태를 확인하세요."
    if isinstance(exc, httpx.DecodingError):
        return (
            f"{source}: 소스 응답을 해석하지 못했습니다. 소스의 응답 형식이 바뀌었을 수 있습니다 — 로그를 확인하세요."
        )
    # 모르는 실패를 아는 척하지 않는다 — 무엇이 났는지(종류)만 남기고 원문은 로그로 보낸다.
    return f"{source}: 적재 중 처리하지 못한 오류가 났습니다 ({type(exc).__name__}). 서버 로그를 확인하세요."
