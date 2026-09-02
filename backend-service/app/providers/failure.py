"""소스 호출 실패를 **사람이 읽고 다음에 무엇을 할지 아는 문장**으로 바꾼다.

이 문자열은 `tn_ingest_run.failed_reason` 에 적히고 **화면에 그대로 보인다.** 그래서 두 가지를
동시에 지켜야 한다:

1. **다음 행동을 말한다.** 403 은 「앱 설정에서 이 서버 IP 를 허용하라」는 아주 구체적인 요구인데,
   원문(`Client error '403 Forbidden' for url '...'`)은 그 말을 못 한다.
2. **원문을 싣지 않는다.** `httpx.HTTPStatusError` 의 문자열에는 요청 URL 이 통째로 들어 있고,
   data.go.kr 은 인증키를 **쿼리 파라미터로** 받는다 — 원문을 그대로 적으면 키가 화면에 실린다.
   가림(`redact_secrets`)은 마지막 방어층이지 첫 방어층이 아니다.

기술 원문은 버리지 않는다 — 로그로 간다. 화면과 로그의 독자가 다르기 때문이다.

**어댑터가 상태 코드를 먼저 옮겨 담은 경우도 여기를 지난다.** 어댑터의 사유는 「무엇이 일어났나」
에서 멈추므로(`Alpaca 응답 상태 403`), 그런 예외는 `http_status` 로 코드를 들고 오고 다음 행동은
이 파일이 세운다 — 문구의 주인이 둘이 되면 소스마다 조언이 갈린다.
"""

from __future__ import annotations

import httpx
from core.exceptions import HTTPError

#: 상태 코드 → (무엇이 일어났나, 무엇을 하면 되나). 코드를 모르면 아래 기본 문장으로 떨어진다.
_BY_STATUS: dict[int, tuple[str, str]] = {
    400: ("소스가 요청을 거절했습니다", "요청 구간·종목 코드가 그 소스에서 유효한지 확인하세요"),
    401: ("소스가 자격을 거절했습니다", "설정 화면에서 키를 다시 넣으세요 — 값이 틀렸거나 만료됐습니다"),
    403: (
        "소스가 이 서버의 접근을 막았습니다",
        # 화면은 이 문자열을 **평문으로** 그린다(`IngestConsole` 에 마크다운 렌더러가 없다).
        # 강조 표기를 넣으면 별표가 그대로 보인다.
        #
        # **403 은 「키가 틀림」과 「IP 가 막힘」을 안 가른다.** 소스가 둘을 같은 코드로 답하기
        # 때문이다. 종전 문구는 IP 만 단정해, 명백히 가짜인 키를 넣었을 때도 사용자를 방화벽으로
        # 보냈다(#435 F31·B-15). 모호하면 모호한 채로 말하되 **사용자가 먼저 확인할 수 있는 것**을
        # 앞에 둔다 — 키는 설정 화면에서 바로 바꿀 수 있고, IP 허용은 발급처에 가야 한다.
        "먼저 설정 화면에서 키를 확인하세요 — 값이 틀렸거나 만료됐을 수 있습니다. "
        "키가 확실하다면 발급처 앱 설정에서 이 서버의 IP 를 허용 목록에 등록하세요",
    ),
    404: ("소스에 그 자원이 없습니다", "종목 코드와 시장이 맞는지 확인하세요"),
    429: ("소스의 호출 한도에 걸렸습니다", "잠시 뒤 다시 시도하세요 — 받은 것까지는 저장돼 있습니다"),
}

_SERVER_SIDE = ("소스 쪽에 장애가 있습니다", "잠시 뒤 다시 시도하세요 — 우리 쪽 설정 문제가 아닙니다")


def _describe_status(status: int) -> str:
    """상태 코드 하나를 「무엇이 일어났나 (HTTP n) — 무엇을 하면 되나」로. 소스 이름은 부르는 쪽이 붙인다."""
    known = _BY_STATUS.get(status)
    if known is None and status >= 500:
        known = _SERVER_SIDE
    if known is None:
        # **모르는 상태 코드에 아는 척하지 않는다.** 400 의 조언을 빌려 주면
        # 「종목 코드를 확인하세요」 같은 틀린 다음 행동을 말하게 된다 (302·407·451 등).
        return f"소스가 예상 밖의 응답을 냈습니다 (HTTP {status}). 서버 로그를 확인하세요."
    what, todo = known
    return f"{what} (HTTP {status}). {todo}."


def _named(source: str, message: str) -> str:
    """여러 소스가 섞인 이력에서 누가 실패했는지 알 수 있게. 이미 제 이름으로 시작하는 사유는 그대로 둔다."""
    return message if message.startswith(source) else f"{source}: {message}"


def describe_provider_failure(exc: BaseException, source: str) -> str:
    """화면에 낼 실패 사유. **URL·원문·자격을 담지 않는다.**"""
    status = getattr(exc, "http_status", None)
    if isinstance(status, int):
        # 어댑터가 상태 코드를 자기 말로 옮긴 경우다. 옮긴 문장은 「무엇이 일어났나」에서 멈추므로
        # (`Alpaca 응답 상태 403`) 다음 행동은 코드에서 다시 세운다 — 그것을 아는 것은 코드다.
        return _named(source, _describe_status(status))
    if isinstance(exc, HTTPError):
        # 우리가 만든 예외는 이미 한국어이고 다음 행동을 담고 있다 — 덮으면 나빠진다.
        # (`등록되지 않은 시세 소스입니다: 'tos'` 같은 문장이 「처리하지 못한 오류」로 뭉개졌다)
        return _named(source, str(exc))
    if isinstance(exc, httpx.HTTPStatusError):
        return _named(source, _describe_status(exc.response.status_code))
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
