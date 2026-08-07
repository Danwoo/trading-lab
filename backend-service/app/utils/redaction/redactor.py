"""우리가 쥔 데이터 소스 키가 프로세스 밖으로 나가기 전에 지운다 — 로그·응답·예외의 마지막 관문.

키는 **저장**보다 **유출**로 샌다. 이 레포에서 실제로 새는 자리는 셋이고 전부 값이 문자열에
섞여 나가는 모양이다:

1. `data.go.kr` 은 인증키를 **쿼리스트링**(`serviceKey=...`)으로 받는다. 그래서 상류가 4xx·5xx
   를 주면 `httpx.HTTPStatusError.__str__` 이 **키가 박힌 URL 전체**를 문자열로 만든다 — 그것이
   재시도 경고 로그(`utils/common/retry_utils.py` 의 `_before_sleep`)와 5xx 트레이스백
   (`core/exception_handler.py` 의 `exc_info=True`)에 그대로 실린다.
2. 상류 오류 본문을 그대로 예외 메시지에 옮기면 그 문장이 API 응답 `detail` 로 나간다.
3. 적재 잡의 `failed_reason` 은 DB 컬럼이자 200 응답 필드다.

**정규식으로 "키처럼 생긴 것"을 찾지 않는다.** 우리는 키의 실제 값을 알고 있으므로 정확한 값
치환이 가능하고, 그쪽이 오탐도 미탐도 없다. 대신 값이 **변형돼 나타나는 형태**를 등록 시점에
함께 넣는다 — httpx 가 쿼리 파라미터를 퍼센트 인코딩하므로 원문 그대로는 URL 안에서 발견되지
않기 때문이다(`+` → `%2B`, `%` → `%25`). 이 변형 등록이 없으면 정확 치환은 URL 축에서 통째로
빗나간다.

등록 주체는 **키를 읽는 유일한 자리**(`services/data_key/data_key_service.py`)다. 로드와 가림
등록이 같은 곳에 있어야 "등록을 빠뜨린 키"가 생기지 않는다. 로그 관문 설치(`install_log_redaction`)도
같은 자리에서 일어난다 — 「비밀이 존재하게 된 순간 = 관문이 서 있는 순간」을 한 호출로 묶는다.

**관문을 `core/logger.py` 안에 넣지 않은 이유**: 그 파일은 전 서비스 10벌이 byte-identical 이어야
하는 복제군이다(`scripts/verify_auth_lockstep.py` 의 `REPLICA_GROUPS`). 데이터 소스 키는
backend-service 에만 있으므로 그 규율을 깨면서까지 공통 파일을 고칠 이유가 없다. 대신 **런타임에
핸들러를 감싼다** — 결과는 같고, 복제군은 그대로 남는다. `core/exception_handler.py` 도 같은
복제군이라 응답 축은 관문이 아니라 **발생 지점**에서 지운다(`providers/base.py` 의
`ProviderResponseInvalid`·`services/ingest/` 의 `failed_reason`).

같은 레포의 `multi-agent-service`·`portfolio-mcp-service` 에도 `utils/redaction/redactor.py` 가
있지만 그것들은 **남의 식별자**(계좌·카드번호)를 자유텍스트에서 패턴으로 찾는 모듈이라 이 문제에
쓸 수 없다 — 여기서 가려야 하는 것은 우리가 값을 아는 우리 비밀이다. 모듈 위치·파일명·공개
함수명(`redact_secrets`)만 그 관례를 따른다.
"""

import logging
from urllib.parse import quote, quote_plus

_MASK = "[데이터 소스 키 가려짐]"

# 이보다 짧은 값은 등록하지 않는다 — 짧은 문자열은 멀쩡한 로그 문장에 우연히 섞여 있어서,
# 가리는 순간 읽을 수 없는 로그가 된다. 실 발급 키(data.go.kr 인코딩키·Alpaca 키)는 전부
# 수십 자라 이 하한에 걸리지 않는다.
MIN_REDACTABLE_LENGTH = 8

_secrets: set[str] = set()


def _variants(value: str) -> set[str]:
    """값이 실제로 문자열에 나타나는 형태들. 원문 + URL 인코딩 두 갈래(`%20`/`+`)."""
    return {value, quote(value, safe=""), quote_plus(value)}


def register_secret(value: str | None) -> bool:
    """비밀값을 가림 대상으로 등록한다. 등록됐으면 True (짧거나 비었으면 False)."""
    text = (value or "").strip()
    if len(text) < MIN_REDACTABLE_LENGTH:
        return False
    _secrets.update(_variants(text))
    return True


def registered_count() -> int:
    """등록된 문자열 수 — 그물이 "아무것도 안 보고 통과"했는지 세는 근거."""
    return len(_secrets)


def redact_secrets(text):
    """등록된 비밀값을 마스크로 치환. 문자열이 아니면 손대지 않고 그대로 돌려준다.

    긴 것부터 치환한다 — 짧은 변형이 긴 변형의 일부일 때 조각만 가려 남는 것을 막는다.
    """
    if not isinstance(text, str) or not _secrets:
        return text
    for secret in sorted(_secrets, key=len, reverse=True):
        if secret in text:
            text = text.replace(secret, _MASK)
    return text


class RedactingFormatter(logging.Formatter):
    """포맷이 끝난 최종 문자열에서 비밀값을 지운다 — 감싼 포매터의 결과를 통과시킨다.

    필터가 아니라 포매터인 이유: 키가 실제로 새는 경로는 메시지 본문이 아니라 `exc_info` 로 붙는
    **트레이스백**이다. 필터는 `record.msg` 만 만질 수 있고 트레이스백은 포매터가 렌더한다.
    """

    def __init__(self, inner: logging.Formatter):
        super().__init__()
        self._inner = inner

    def format(self, record: logging.LogRecord) -> str:
        return redact_secrets(self._inner.format(record))


def install_log_redaction() -> int:
    """앱 로거와 루트의 **모든 핸들러**를 관문으로 감싼다. 감싼 수를 돌려준다 (idempotent).

    로거가 아니라 핸들러에 거는 이유: 로거 단위로 걸면 외부 라이브러리(httpx·tenacity)가 전파해
    오는 레코드를 건너뛴다. 핸들러는 도달하는 모든 레코드를 본다.

    VictoriaLogs 싱크는 포매터가 아니라 `record.getMessage()` 를 읽지만 이 한 줄로 함께 덮인다 —
    그 앞의 `QueueHandler.prepare` 가 **자기 핸들러의 포매터로** 렌더한 문자열을 `record.msg` 에
    다시 넣고 큐에 태우기 때문이다.
    """
    from core.logger import logger as app_logger

    handlers = list(app_logger.handlers) + list(logging.getLogger().handlers)
    for handler in handlers:
        if not isinstance(handler.formatter, RedactingFormatter):
            handler.setFormatter(RedactingFormatter(handler.formatter or logging.Formatter()))
    return len(handlers)
