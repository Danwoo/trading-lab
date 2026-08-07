"""#243 — 데이터 소스 키가 로그·응답·예외로 새지 않는지 (fail-closed).

**정규식으로 소스를 훑는 그물이 아니다.** 가짜 키를 `.env` 자리에 꽂고 **실제 코드 경로를 태운
뒤**, 그 키 문자열이 나온 산출물(로그 한 줄·API 응답 본문·예외 메시지)에 있는지 본다. 우회를
잡으려면 그 방법뿐이다 — 소스에 `redact_secrets(` 가 있는지 세는 검사는 그 호출이 무력해진
순간을 못 잡는다.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행형이다:
    cd backend-service && uv run python tests/test_data_source_key_leak.py

검사하는 4축 (오더 #243 잔여):
1. **로그** — 재시도 경고·트레이스백. data.go.kr 은 인증키를 쿼리로 받으므로
   `httpx.HTTPStatusError.__str__` 이 키가 박힌 URL 을 문자열로 만든다.
2. **API 응답** — `capabilities()` 는 "있나/없나"와 "없으면 어디서 받나"만 답한다. 키 값도,
   앞자리 몇 글자도 돌려주지 않는다.
3. **에러 메시지** — 상류가 오류 본문에 우리 키를 되비춰도 그것이 응답 `detail`·
   `tn_ingest_run.failed_reason` 으로 흘러나가지 않는다.
4. **커밋** — 축 4(`.env` 가 실제로 gitignore 되는가)는 git 을 봐야 하므로
   `scripts/verify_data_key_env_boundary.py` 가 맡는다.

**뮤테이션 증명이 내장돼 있다.** 같은 로그 레코드를 가림 없는 포매터로 렌더해 키가 **나오는지**
확인한다 — 나오지 않으면 그물이 아무 일도 안 하는 것이므로 실패시킨다. 그물을 빼면 빨개진다는
것을 파일을 고치지 않고도 매 실행이 다시 증명한다.

외부 의존은 **소켓만** 대역으로 둔다(`httpx.MockTransport`). 어댑터·클라이언트·서비스·핸들러는
전부 실제 코드가 돈다.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import sys
from contextlib import contextmanager
from pathlib import Path

# 가짜 키 — 값에 `+ / = :` 를 섞는다. httpx 가 쿼리 파라미터를 퍼센트 인코딩하므로 원문 그대로는
# URL 안에서 발견되지 않는다. 인코딩 변형까지 가려지는지가 이 그물의 핵심 축이다.
FAKE_GOKR_KEY = "dummy-gokr-service-key-DO-NOT-USE-a+b/c=="
FAKE_ALPACA_KEY = "dummy-alpaca-keyid-DO-NOT-USE:dummy-alpaca-secret-DO-NOT-USE"
FAKE_OPENFIGI_KEY = "dummy-openfigi-key-DO-NOT-USE"
FAKE_KEYS = (FAKE_GOKR_KEY, FAKE_ALPACA_KEY, FAKE_OPENFIGI_KEY)

os.environ["APP_ENV"] = "key-leak-test"
for _key, _value in {
    "BACKEND_SQL_DB_DRIVER": "postgresql+psycopg",
    "BACKEND_SQL_DB_HOST": "localhost",
    "BACKEND_SQL_DB_PORT": "5432",
    "BACKEND_SQL_DB_NAME": "test",
    "BACKEND_SQL_DB_USER": "test",
    "BACKEND_SQL_DB_PASSWORD": "test",
    "SFTP_HOST": "localhost",
    "SFTP_PORT": "22",
    "SFTP_USERNAME": "test",
    "SFTP_PASSWORD": "test",
    "JWT_SECRET": "test-secret",
    "MARKET_DATA_CONTACT": "fintech-ai-platform/test (contact: leak-test@example.com)",
    "MARKET_DATA_GOKR_SERVICE_KEY": FAKE_GOKR_KEY,
    "MARKET_DATA_ALPACA_KEY": FAKE_ALPACA_KEY,
    "MARKET_DATA_OPENFIGI_KEY": FAKE_OPENFIGI_KEY,
}.items():
    os.environ.setdefault(_key, _value)

_TESTS_DIR = Path(__file__).resolve().parent
_APP_DIR = _TESTS_DIR.parent / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import datetime as dt  # noqa: E402
import json  # noqa: E402

import httpx  # noqa: E402
from core.config import settings  # noqa: E402
from core.exception_handler import handle_http_error  # noqa: E402
from core.logger import logger  # noqa: E402
from fastapi import Request  # noqa: E402
from providers import get_provider, list_sources, register_provider  # noqa: E402
from providers.base import ProviderResponseInvalid  # noqa: E402
from services.capability.capability_service import CapabilityService  # noqa: E402
from services.data_key.data_key_service import SOURCE_KEY_SETTINGS, DataKeyService  # noqa: E402
from services.ingest.ingest_service import IngestService  # noqa: E402
from utils.redaction.redactor import RedactingFormatter, redact_secrets, registered_count  # noqa: E402

# 키로 여는 소스 — 이 목록이 비면 아무것도 검사하지 않은 것이므로 fail-closed 로 실패한다.
KEY_REQUIRED_SOURCES = ("data_go_kr", "alpaca")

# 키 앞뒤 몇 글자도 새면 안 된다 — "힌트"라며 앞자리를 흘리는 API 가 흔하다.
FRAGMENT_LENGTH = 8

# 이 파일이 실제로 태운 코드 경로 수 — 마지막에 0 이면 실패한다.
_burned: list[str] = []


def _burn(label: str) -> None:
    _burned.append(label)


# ── 대역: 소켓만 바꾼다 ──────────────────────────────────────────────────────────
_REAL_ASYNC_CLIENT = httpx.AsyncClient


@contextmanager
def mock_socket(handler):
    """`httpx.AsyncClient` 가 네트워크 대신 handler 로 가게 한다 — 어댑터·클라이언트는 실코드."""

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return _REAL_ASYNC_CLIENT(*args, **kwargs)

    httpx.AsyncClient = factory
    try:
        yield
    finally:
        httpx.AsyncClient = _REAL_ASYNC_CLIENT


class LogCapture(logging.Handler):
    """앱이 실제로 설치한 가림 포매터로 렌더한 줄 + 원본 레코드를 함께 모은다."""

    def __init__(self, formatter: logging.Formatter):
        super().__init__(level=logging.DEBUG)
        self.setFormatter(formatter)
        self.rendered: list[str] = []
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)
        self.rendered.append(self.format(record))


@contextmanager
def capture_logs():
    installed = next((h.formatter for h in logger.handlers if isinstance(h.formatter, RedactingFormatter)), None)
    assert installed is not None, "앱 로거에 가림 포매터가 설치돼 있지 않다 — 로그 축의 그물이 통째로 빠졌다"
    capture = LogCapture(installed)
    logger.addHandler(capture)
    try:
        yield capture
    finally:
        logger.removeHandler(capture)


def assert_no_key(blob: str, where: str) -> None:
    """키 원문·URL 인코딩 변형·앞뒤 조각 어느 것도 없어야 한다."""
    from urllib.parse import quote, quote_plus

    for key in FAKE_KEYS:
        for form in (key, quote(key, safe=""), quote_plus(key)):
            assert form not in blob, f"{where} 에 키가 샜다: {form[:20]}…"
        assert key[:FRAGMENT_LENGTH] not in blob, f"{where} 에 키 앞 {FRAGMENT_LENGTH}자가 샜다"
        assert key[-FRAGMENT_LENGTH:] not in blob, f"{where} 에 키 뒤 {FRAGMENT_LENGTH}자가 샜다"


# ── 축 0: 로더 ──────────────────────────────────────────────────────────────────
def test_env_keys_reach_the_adapter():
    """`.env` 에 채운 키가 `DataKeyService` 를 지나 어댑터 생성자까지 간다."""
    service = DataKeyService(config=settings)
    for source in KEY_REQUIRED_SOURCES:
        key = service.get_key(workspace_id=None, source=source)
        assert key, f"{source} 의 키가 .env 에서 오지 않았다"
        assert get_provider(source, key).api_key == key, f"{source} 어댑터가 키를 받지 못했다"
    _burn("로더: .env → DataKeyService → 어댑터 생성자")


def test_keys_are_registered_for_redaction_on_load():
    """로드와 가림 등록이 같은 자리다 — 등록을 빠뜨린 키가 구조적으로 생기지 않는다."""
    assert registered_count() >= len(KEY_REQUIRED_SOURCES), (
        f"가림 대상이 {registered_count()}건 — 키 {len(KEY_REQUIRED_SOURCES)}개보다 적다"
    )
    for key in FAKE_KEYS:
        assert redact_secrets(f"prefix {key} suffix") != f"prefix {key} suffix", f"{key[:12]}… 이 가림 대상이 아니다"
    _burn("로더: 키 로드 시 가림 등록")


# ── 축 1: 로그 ──────────────────────────────────────────────────────────────────
def test_retry_warning_does_not_leak_key():
    """실 재시도 경로 — 503 한 번 → `retry_utils._before_sleep` 이 예외를 로그로 찍는다.

    그 예외는 `httpx.HTTPStatusError` 이고 `__str__` 이 **키가 박힌 URL 전체**를 만든다.
    """
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, text="service unavailable")
        return httpx.Response(200, json=_ok_envelope())

    provider = get_provider("data_go_kr", DataKeyService(config=settings).get_key(None, "data_go_kr"))
    with capture_logs() as captured, mock_socket(handler):
        asyncio.run(provider.fetch_daily("005930", "KOSPI", dt.date(2026, 1, 2), dt.date(2026, 1, 5)))

    warnings = [r for r in captured.records if r.levelno >= logging.WARNING]
    assert warnings, "재시도 경고가 한 줄도 안 나왔다 — 이 그물은 아무것도 검사하지 않았다"

    rendered = "\n".join(captured.rendered)
    assert_no_key(rendered, "재시도 경고 로그")

    # 뮤테이션 — 같은 레코드를 가림 없는 포매터로 렌더하면 키가 나와야 한다.
    plain = logging.Formatter("%(message)s")
    raw = "\n".join(plain.format(record) for record in warnings)
    assert any(form in raw for form in (FAKE_GOKR_KEY, _quoted(FAKE_GOKR_KEY))), (
        "가림을 뺀 렌더에도 키가 없다 — 이 그물은 새지 않는 문장을 검사하고 있다"
    )
    _burn("로그: 재시도 경고 (503 → _before_sleep)")


def test_traceback_does_not_leak_key():
    """`exc_info=True` 로 붙는 트레이스백 — 필터가 아니라 포매터를 관문으로 둔 이유가 이 축이다."""
    with capture_logs() as captured:
        try:
            raise _status_error_with_key()
        except httpx.HTTPStatusError:
            logger.exception("KEY_LEAK_PROBE — 트레이스백 축")

    rendered = "\n".join(captured.rendered)
    assert "Traceback" in rendered, "트레이스백이 렌더되지 않았다 — 이 그물은 축을 검사하지 못했다"
    assert_no_key(rendered, "트레이스백 로그")

    plain = logging.Formatter("%(message)s")
    raw = "\n".join(plain.format(record) for record in captured.records)
    assert _quoted(FAKE_GOKR_KEY) in raw or FAKE_GOKR_KEY in raw, (
        "가림을 뺀 렌더에도 키가 없다 — 트레이스백에 키가 실리지 않는 상황을 검사하고 있다"
    )
    _burn("로그: exc_info 트레이스백")


# ── 축 2: API 응답 ──────────────────────────────────────────────────────────────
def test_capability_response_says_yes_no_but_never_the_value():
    """키가 꽂히면 capability 가 「키 있음」으로 바뀌고, 그 응답 어디에도 값이 없다."""
    service = CapabilityService(data_key_service=DataKeyService(config=settings))
    rows = service.list_capabilities(workspace_id=None)
    assert rows, "capability 표가 비었다 — 검사 대상 0건"

    opened = {row["source"] for row in rows if row["available"]}
    for source in KEY_REQUIRED_SOURCES:
        assert source in opened, f"{source} 에 키를 꽂았는데 available=True 인 행이 없다"

    assert_no_key(json.dumps(rows, ensure_ascii=False), "capability 응답")
    _burn(f"응답: capability {len(rows)}행 (키 있음으로 전환 확인)")


def test_reason_text_never_carries_the_value_even_when_the_key_is_set():
    """사유 문장은 **키가 채워져 있을 때도** 값을 싣지 않는다.

    앞의 두 축이 못 보던 조합이다 — 「키 있음」 경로는 사유를 만들지 않고, 「사유 있음」 경로는
    빈 설정으로 돌았다. 그래서 `unavailable_reason` 에 `key[:12]` 를 흘리는 뮤테이션이 둘 다
    통과했다(실측). `key_hint(마지막 4자)` 를 응답에 담자는 것은 원래 T4 설계안이었으므로 이
    회귀는 가정이 아니라 실제로 돌아올 수 있는 모양이다.
    """
    service = DataKeyService(config=settings)
    reasons = [service.unavailable_reason(source) for source in (*SOURCE_KEY_SETTINGS, "sec")]
    assert len(reasons) > len(KEY_REQUIRED_SOURCES), "사유를 물어본 소스가 너무 적다 — 검사 대상 부족"
    for source, reason in zip((*SOURCE_KEY_SETTINGS, "sec"), reasons, strict=True):
        assert reason, f"{source} 의 사유가 비었다"
        assert_no_key(reason, f"{source} unavailable_reason (키가 채워진 상태)")
    _burn(f"응답: 키가 채워진 상태의 사유 {len(reasons)}건")


def test_missing_key_reason_names_the_env_slot_not_the_value():
    """키가 비었을 때의 사유는 「.env 의 어느 이름을 채워라」다 — 값은 애초에 없다."""
    service = CapabilityService(data_key_service=DataKeyService(config=_EmptyKeyConfig()))
    rows = service.list_capabilities(workspace_id=None)
    reasons = [row["reason"] or "" for row in rows]
    assert reasons, "사유 0건"
    for source in KEY_REQUIRED_SOURCES:
        setting = SOURCE_KEY_SETTINGS[source]
        assert any(setting in reason for reason in reasons), f"{source} 사유에 {setting} 이름이 없다"
    assert_no_key(json.dumps(rows, ensure_ascii=False), "키 없음 사유")
    _burn("응답: 키 없음 사유가 .env 슬롯 이름을 지목")


# ── 축 3: 에러 메시지 ───────────────────────────────────────────────────────────
def test_upstream_error_body_echoing_the_key_is_scrubbed():
    """상류가 오류 본문에 우리 키를 **되비추는** 최악의 경우.

    공공데이터포털은 오류도 200 + 오류 봉투로 주므로 그 문장이 어댑터를 지나 응답 `detail` 까지
    간다. 되비친 키가 그대로 흘러나가면 우리 로그·응답 양쪽이 동시에 오염된다.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "response": {
                    "header": {
                        "resultCode": "30",
                        "resultMsg": f"SERVICE_KEY_IS_NOT_REGISTERED_ERROR (serviceKey={FAKE_GOKR_KEY})",
                    }
                }
            },
        )

    provider = get_provider("data_go_kr", DataKeyService(config=settings).get_key(None, "data_go_kr"))
    raised: ProviderResponseInvalid | None = None
    with mock_socket(handler):
        try:
            asyncio.run(provider.fetch_daily("005930", "KOSPI", dt.date(2026, 1, 2), dt.date(2026, 1, 5)))
        except ProviderResponseInvalid as exc:
            raised = exc
    assert raised is not None, "오류 봉투를 조용히 0건으로 삼켰다 — 이 그물은 아무것도 검사하지 않았다"
    assert_no_key(f"{raised} {raised.detail}", "ProviderResponseInvalid")

    body = _error_response_body(raised)
    assert body["detail"], "에러 응답 detail 이 비었다"
    assert_no_key(json.dumps(body, ensure_ascii=False), "에러 HTTP 응답 본문")
    _burn("에러: 상류가 되비친 키 → 예외 + HTTP 응답 본문")


def test_ingest_failed_reason_does_not_leak_key():
    """어댑터가 변환하지 못한 예외가 그대로 올라오는 경우 — `failed_reason` 은 DB 컬럼이자 응답 필드다."""
    register_provider(_PROBE_SOURCE, lambda api_key: _RawErrorProvider(api_key))
    repository = _StubIngestRepository()
    service = IngestService(ingest_repository=repository, data_key_service=DataKeyService(config=settings))
    run = {"run_id": 1, "source": _PROBE_SOURCE, "job_kind": "instrument_master", "scope": "KOSPI", "workspace_id": 1}

    with capture_logs() as captured:
        result = asyncio.run(service.run_job(run))

    assert result["status"] == "failed", f"실패로 끝나지 않았다: {result}"
    assert repository.finished, "잡 상태가 기록되지 않았다 — 검사 대상 0건"
    assert_no_key(json.dumps(result, ensure_ascii=False), "run_job 반환")
    assert_no_key(json.dumps(repository.finished, ensure_ascii=False), "tn_ingest_run.failed_reason")
    assert_no_key("\n".join(captured.rendered), "적재 잡 실패 로그")

    # 뮤테이션 — 가림을 걷어낸 원본에는 키가 있어야 한다. 없으면 새지 않는 것을 검사한 것이다.
    assert _quoted(FAKE_GOKR_KEY) in str(_status_error_with_key()), (
        "이 축이 태우는 예외에 애초에 키가 없다 — 그물이 헛돌고 있다"
    )
    _burn("에러: 미변환 예외 → failed_reason (DB·응답) + 로그")


# ── 대역·헬퍼 ───────────────────────────────────────────────────────────────────
_PROBE_SOURCE = "_leak_probe"


class _RawErrorProvider:
    """상류 오류를 **변환하지 않고** 그대로 올리는 어댑터 — 백스톱이 지켜야 할 최악의 어댑터다."""

    def __init__(self, api_key: str | None):
        self.api_key = api_key

    def capabilities(self):
        return []

    async def list_instruments(self, market: str):
        raise _status_error_with_key()


class _StubIngestRepository:
    def __init__(self):
        self.finished: dict | None = None

    def update_ingest_run_status(self, args: dict) -> None:
        self.finished = dict(args, finished_dt=str(args.get("finished_dt")))


class _EmptyKeyConfig:
    """키가 하나도 없는 설정 — 키 없음 사유 축을 태우기 위한 최소 대역."""

    MARKET_DATA_CONTACT = ""
    MARKET_DATA_GOKR_SERVICE_KEY = ""
    MARKET_DATA_ALPACA_KEY = ""
    MARKET_DATA_OPENFIGI_KEY = ""


def _quoted(value: str) -> str:
    from urllib.parse import quote_plus

    return quote_plus(value)


def _ok_envelope() -> dict:
    return {"response": {"header": {"resultCode": "00"}, "body": {"items": {"item": []}, "totalCount": 0}}}


def _status_error_with_key() -> httpx.HTTPStatusError:
    """실제 어댑터가 만드는 것과 같은 예외 — httpx 가 직접 만들게 한다.

    손으로 `HTTPStatusError(...)` 를 지으면 메시지에 URL 이 안 들어가서 **새지 않는 문장을
    검사하는 그물**이 된다(이 파일의 뮤테이션 단언이 실제로 그것을 잡아냈다). 키가 URL 에
    실리는 것은 `raise_for_status()` 가 만드는 문구의 성질이므로 그것을 그대로 태운다.
    """
    request = httpx.Request(
        "GET",
        "https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo",
        params={"serviceKey": FAKE_GOKR_KEY, "resultType": "json"},
    )
    try:
        httpx.Response(503, request=request, text="service unavailable").raise_for_status()
    except httpx.HTTPStatusError as exc:
        return exc
    raise AssertionError("503 이 raise_for_status 를 통과했다")


def _error_response_body(exc) -> dict:
    """실제 에러 핸들러를 태워 응답 본문을 얻는다 — 모든 에러 응답이 이 함수로 모인다."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/bar/daily",
        "raw_path": b"/bar/daily",
        "query_string": b"",
        "headers": [],
        "scheme": "http",
        "server": ("testserver", 80),
        "root_path": "",
    }
    response = asyncio.run(handle_http_error(Request(scope), exc))
    return json.loads(bytes(response.body).decode())


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    if not tests:
        print("::error::테스트를 0건 수집했습니다 — fail-closed 종료")
        return 1
    if not KEY_REQUIRED_SOURCES:
        print("::error::키가 필요한 소스가 0건입니다 — 검사 대상 없음, fail-closed 종료")
        return 1
    missing = [source for source in KEY_REQUIRED_SOURCES if source not in list_sources()]
    if missing:
        print(f"::error::키가 필요한 소스가 레지스트리에 없습니다: {', '.join(missing)} — fail-closed 종료")
        return 1

    # 로그를 stdout 으로 흘리지 않는다 — 판정 출력만 남긴다 (레코드는 capture 로 받는다).
    logging.getLogger().handlers = [logging.StreamHandler(io.StringIO())]
    for handler in logger.handlers:
        handler.setLevel(logging.CRITICAL)

    # 앱 기동과 같은 순서 — 컨테이너가 `DataKeyService` 를 만들면 그때 로그 관문이 선다.
    DataKeyService(config=settings)
    gated = [h for h in logger.handlers if isinstance(h.formatter, RedactingFormatter)]
    if len(gated) != len(logger.handlers) or not gated:
        print(
            f"::error::앱 로거 핸들러 {len(logger.handlers)}개 중 {len(gated)}개만 관문을 지납니다 — fail-closed 종료"
        )
        return 1

    failed = 0
    for test in tests:
        try:
            test()
            print(f"  ✓ {test.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"::error::{test.__name__}: {exc}")

    if not _burned:
        print("::error::실제로 태운 코드 경로가 0건입니다 — fail-closed 종료")
        return 1

    print(f"\n검사한 키 {len(FAKE_KEYS)}개 · 가림 등록 문자열 {registered_count()}건 · 소스 {len(list_sources())}개")
    print(f"태운 코드 경로 {len(_burned)}개:")
    for label in _burned:
        print(f"  · {label}")
    print(f"테스트 {len(tests)}개 중 {len(tests) - failed}개 통과, {failed}개 실패")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
