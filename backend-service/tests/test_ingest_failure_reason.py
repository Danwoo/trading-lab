"""적재 실패 사유가 **화면에 낼 만한 것**인지 (네트워크 없음).

이 문자열은 `tn_ingest_run.failed_reason` 에 적혀 화면에 그대로 보인다. 그물이 잠그는 것:

  ① 원문·URL 이 실리지 않는다 — `httpx` 문자열엔 요청 URL 이 통째로 들어 있고,
     data.go.kr 은 인증키를 쿼리로 받는다 (원문을 적으면 키가 화면에 실린다)
  ② **다음에 무엇을 하면 되는지**를 말한다 — 403 은 「IP 를 허용하라」는 구체적 요구다
  ③ 소스 이름이 들어간다 — 여러 소스가 섞인 이력에서 누가 실패했는지 알 수 있게
  ④ 모르는 실패를 아는 척하지 않는다 — 매핑 밖 상태 코드가 남의 조언을 빌리지 않는다
  ⑥ **우리 도메인 예외의 한국어 사유를 삼키지 않는다** (덮으면 main 보다 나빠진다)
  ⑦ 화면이 평문으로 그리므로 마크다운 강조 표기를 넣지 않는다
  ⑤ 적재 서비스가 실제로 이 변환을 태운다 (배선 확인)
  ⑧ **저장되는 사유의 내용** — 배선이 아니라 `IngestService.run_job` 이 실제로 남긴 문자열을
     본다. 배선만 보는 그물은 어댑터가 상태 코드를 먼저 눌러 담는 경로(`Alpaca 응답 상태 403`)를
     놓친다 — 그 경로가 화면에 「무엇을 하면 되는지」 없는 줄을 남겼다 (#287)
  ⑨ 어댑터 전수 — 상태 코드를 옮겨 담는 자리는 `http_status` 로 코드를 함께 넘긴다.
     한 자리만 고치면 다음 어댑터가 같은 구멍을 다시 판다

**경계** — 「영문 예외 클래스명 금지」는 상태 코드가 아는 실패에 대한 것이다. 아는 게 없는 실패
(`④`)는 종류(`ValueError`)를 남기기로 한 결정(#251)이 있어 그 한 자리만 예외로 둔다.

standalone 실행 겸용:
    cd backend-service && uv run python tests/test_ingest_failure_reason.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

os.environ["APP_ENV"] = "ingest-failure-test"
for _name, _value in {
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
}.items():
    os.environ.setdefault(_name, _value)

_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import httpx  # noqa: E402
from providers.failure import describe_provider_failure  # noqa: E402

FAILURES: list[str] = []
CHECKED = 0

# 실제로 겪은 모양 그대로 — 키를 쿼리에 싣는 소스가 있다.
SECRET = "dummy-service-key-CANARY-a+b/c=="
URL = f"https://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService?serviceKey={SECRET}"


#: URL 판정은 **스킴 패턴**으로 한다. 호스트 부분문자열(`"tossinvest.com" in text`)로 보면
#: 판정이 위치를 안 따져 URL 소독기의 전형적 결함 모양이 되고, 정적 분석이 그것을 잡는다
#: (CodeQL `py/incomplete-url-substring-sanitization` — 실제로 이 파일에서 잡혔다).
URL_SCHEME = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://")


def has_url(text: str) -> bool:
    """URL 이 실렸는가. 「HTTP 404」 같은 상태 표기는 URL 이 아니다."""
    return URL_SCHEME.search(text) is not None


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


def http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", URL)
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"Client error '{status}' for url '{URL}'", request=request, response=response)


#: 화면에 남으면 안 되는 라이브러리 원문. `httpx` 가 상태 오류에 붙이는 영문 문장들이다.
ENGLISH_RESIDUE = ("Client error", "Server error", "For more information check", "for url", "Traceback")

#: 예외 클래스명 모양. 상태 코드가 아는 실패에는 하나도 없어야 한다.
EXCEPTION_CLASS_NAME = re.compile(r"\b[A-Za-z]+(?:Error|Exception)\b")

HANGUL = re.compile(r"[가-힣]")


class _RecordingRepository:
    """`_finish` 가 DB 로 넘기는 인자를 그대로 붙든다 — 저장될 값을 DB 없이 본다."""

    def __init__(self) -> None:
        self.saved: list[dict] = []

    def update_ingest_run_status(self, args: dict) -> None:
        self.saved.append(args)


class _KeyStub:
    def get_key(self, workspace_id, source):  # noqa: ANN001, ANN201
        return "KEYID:SECRET"


class _FailingProvider:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc
        self.last_skipped: list[str] = []

    async def list_instruments(self, market: str):  # noqa: ANN201
        raise self.exc


def stored_reason(exc: BaseException, source: str) -> str:
    """그 예외로 적재 잡이 끝났을 때 `tn_ingest_run.failed_reason` 에 **실제로 적히는** 문자열."""
    import asyncio  # noqa: PLC0415
    import logging  # noqa: PLC0415

    from services.ingest import ingest_service as ingest_mod  # noqa: PLC0415

    repository = _RecordingRepository()
    service = ingest_mod.IngestService(repository, _KeyStub())
    original = ingest_mod.get_provider
    ingest_mod.get_provider = lambda *_args, **_kwargs: _FailingProvider(exc)
    logging.disable(logging.CRITICAL)
    try:
        asyncio.run(
            service.run_job(
                {
                    "run_id": 1,
                    "source": source,
                    "job_kind": "instrument_master",
                    "scope": "KOSPI",
                    "workspace_id": 1,
                }
            )
        )
    finally:
        logging.disable(logging.NOTSET)
        ingest_mod.get_provider = original
    return repository.saved[-1]["failed_reason"]


def adapter_converted(source: str, status: int) -> BaseException:
    """**실제 어댑터**가 그 상태 코드를 무엇으로 바꾸는지 — 손으로 지어낸 예외로 시험하지 않는다."""
    import asyncio  # noqa: PLC0415

    async def boom(*_args, **_kwargs):
        raise http_error(status)

    if source == "alpaca":
        from providers.alpaca.adapter import AlpacaProvider  # noqa: PLC0415
        from providers.alpaca.client import AlpacaClient  # noqa: PLC0415

        AlpacaClient.bars = boom
        import datetime as _dt  # noqa: PLC0415

        call = AlpacaProvider("KEYID:SECRET").fetch_daily("AAPL", "NASDAQ", _dt.date(2026, 1, 1), _dt.date(2026, 1, 2))
    elif source == "data_go_kr":
        from providers.data_go_kr.adapter import DataGoKrProvider  # noqa: PLC0415
        from providers.data_go_kr.client import DataGoKrClient  # noqa: PLC0415

        DataGoKrClient.stock_price_pages = boom
        call = DataGoKrProvider("SERVICEKEY").list_instruments("KOSPI")
    else:
        from providers.sec.adapter import SecProvider  # noqa: PLC0415
        from providers.sec.client import SecClient  # noqa: PLC0415

        SecClient.company_tickers_exchange = boom
        call = SecProvider("trading-lab admin@example.com").list_instruments("NASDAQ")

    try:
        asyncio.run(call)
    except BaseException as exc:  # noqa: BLE001
        return exc
    raise AssertionError(f"{source} 어댑터가 {status} 에 예외를 올리지 않았다")


def check_stored_reasons() -> None:
    """⑧ 배선이 아니라 **저장되는 문자열**을 본다 (DB·네트워크 없음)."""
    cases = [
        ("어댑터가 변환하지 않은 httpx", "toss", http_error(403)),
        ("alpaca 가 변환한", "alpaca", adapter_converted("alpaca", 403)),
        ("data_go_kr 이 변환한", "data_go_kr", adapter_converted("data_go_kr", 403)),
        ("sec 이 변환한", "sec", adapter_converted("sec", 403)),
    ]
    for label, source, exc in cases:
        reason = stored_reason(exc, source)
        check(f"저장: {label} 403 — 소스 이름이 있다", source in reason, True)
        check(f"저장: {label} 403 — 한국어다", HANGUL.search(reason) is not None, True)
        check(f"저장: {label} 403 — 다음 행동을 말한다", "IP" in reason and "등록" in reason, True)
        check(f"저장: {label} 403 — 상태 코드를 밝힌다", "HTTP 403" in reason, True)
        check(f"저장: {label} 403 — URL 이 없다", has_url(reason), False)
        check(f"저장: {label} 403 — 키가 없다", SECRET in reason, False)
        check(
            f"저장: {label} 403 — 영문 예외 클래스명이 없다",
            EXCEPTION_CLASS_NAME.search(reason) is not None,
            False,
        )
        for phrase in ENGLISH_RESIDUE:
            check(f"저장: {label} 403 — 원문 「{phrase}」 이 없다", phrase in reason, False)

    # 상태 코드가 아는 다른 실패도 같은 계층을 지난다
    for status, word in ((400, "확인"), (401, "키를 다시"), (404, "종목 코드"), (503, "우리 쪽")):
        reason = stored_reason(adapter_converted("alpaca", status), "alpaca")
        check(f"저장: alpaca {status} — 다음 행동을 말한다", word in reason, True)
        check(f"저장: alpaca {status} — 원문이 없다", "Client error" in reason or "Server error" in reason, False)

    # 429 는 실패가 아니라 이어받을 지점이 있는 상태다 — 그 갈래도 사람 말로 끝난다
    rate_limited = stored_reason(adapter_converted("alpaca", 429), "alpaca")
    check("저장: 429 — 재개 지점을 남긴다", "재개 지점" in rate_limited, True)
    check("저장: 429 — 영문 예외 클래스명이 없다", EXCEPTION_CLASS_NAME.search(rate_limited) is not None, False)

    # 우리 도메인 예외는 자기 이름을 두 번 부르지 않는다
    from providers.base import ProviderKeyMissing  # noqa: PLC0415

    key_missing = stored_reason(ProviderKeyMissing("toss", "ID:SECRET 형식"), "toss")
    check("저장: 키 없음 — 소스 이름이 한 번만", key_missing.count("toss"), 1)
    check("저장: 키 없음 — .env 를 가리킨다", ".env" in key_missing, True)


def check_adapters_carry_status() -> None:
    """⑨ 상태 코드를 옮겨 담는 자리는 코드를 함께 넘긴다 — 새 어댑터가 같은 구멍을 다시 파지 않게."""
    sites = 0
    for adapter_file in sorted((_APP_DIR / "providers").glob("*/adapter.py")):
        text = adapter_file.read_text(encoding="utf-8")
        for block in re.findall(r"except httpx\.HTTPStatusError as exc:(.*?)(?=\n    (?:async )?def |\Z)", text, re.S):
            if "ProviderResponseInvalid(" not in block:
                continue
            sites += 1
            check(
                f"{adapter_file.parent.name}: 상태 코드를 사유와 함께 넘긴다",
                "http_status=exc.response.status_code" in block,
                True,
            )
    check("상태 코드를 옮겨 담는 자리를 찾았다", sites > 0, True)
    if sites == 0:
        print("::error::어댑터에서 상태 코드 변환 자리를 하나도 못 찾았다 — 그물이 죽어 있다", file=sys.stderr)


def main() -> int:
    # ①·③ 상태 코드별로 사람 말이 나오고, 원문·URL·키가 안 실린다
    for status in (400, 401, 403, 404, 429, 500, 503, 418):
        reason = describe_provider_failure(http_error(status), "data_go_kr")
        check(f"{status}: 소스 이름이 있다", "data_go_kr" in reason, True)
        check(f"{status}: URL 이 없다", has_url(reason), False)
        check(f"{status}: 키가 없다", SECRET in reason, False)
        check(f"{status}: 원문 문구가 없다", "Client error" in reason, False)
        check(f"{status}: 상태 코드를 밝힌다", f"HTTP {status}" in reason, True)

    # ② 403 은 무엇을 하면 되는지까지 말한다 — 이 이슈의 발단이다
    forbidden = describe_provider_failure(http_error(403), "toss")
    check("403 이 IP 허용을 말한다", "IP" in forbidden, True)
    check("403 이 어디서 하는지 말한다", "앱 설정" in forbidden, True)

    check("401 은 키를 다시 넣으라고 한다", "키를 다시" in describe_provider_failure(http_error(401), "alpaca"), True)
    check("429 는 받은 것이 남는다고 말한다", "저장" in describe_provider_failure(http_error(429), "toss"), True)
    check("500 은 우리 문제가 아니라고 말한다", "우리 쪽" in describe_provider_failure(http_error(500), "toss"), True)

    # 네트워크 계열
    request = httpx.Request("GET", URL)
    for exc, word in (
        (httpx.ConnectTimeout("timed out", request=request), "제때"),
        (httpx.ConnectError("failed", request=request), "연결하지"),
        (httpx.DecodingError("bad json", request=request), "해석하지"),
    ):
        reason = describe_provider_failure(exc, "toss")
        check(f"{type(exc).__name__}: 사람 말이다", word in reason, True)
        check(f"{type(exc).__name__}: URL 이 없다", has_url(reason), False)

    # ⑥ 우리가 만든 예외는 이미 한국어 + 다음 행동이다 — 덮으면 안 된다
    from core.exceptions import BadRequestError, NotFoundError  # noqa: PLC0415

    ours = describe_provider_failure(NotFoundError("등록되지 않은 시세 소스입니다: 'tos'"), "tos")
    check("우리 예외의 사유가 남는다", "등록되지 않은 시세 소스입니다" in ours, True)
    check("우리 예외에 소스 이름이 붙는다", ours.startswith("tos:"), True)
    check("우리 예외를 뭉개지 않는다", "처리하지 못한 오류" in ours, False)
    bad = describe_provider_failure(BadRequestError("scope 가 비어 있습니다"), "toss")
    check("다른 도메인 예외도 그대로", "scope 가 비어 있습니다" in bad, True)

    # ③ 매핑 밖 상태 코드 — 400 의 조언을 빌리면 「종목 코드를 확인하세요」라는 틀린 말을 한다
    for odd in (302, 407, 409, 451, 418):
        reason = describe_provider_failure(http_error(odd), "toss")
        check(f"{odd}: 남의 조언을 빌리지 않는다", "종목 코드" in reason, False)
        check(f"{odd}: 모른다고 말한다", "예상 밖" in reason, True)
        check(f"{odd}: 상태 코드는 밝힌다", f"HTTP {odd}" in reason, True)

    # ⑦ 화면은 평문으로 그린다 — 강조 표기를 넣으면 별표가 그대로 보인다
    for status in (400, 401, 403, 404, 429, 500):
        reason = describe_provider_failure(http_error(status), "toss")
        check(f"{status}: 마크다운 강조가 없다", "**" in reason, False)

    # ④ 모르는 실패
    unknown = describe_provider_failure(ValueError(f"boom {SECRET} at {URL}"), "toss")
    check("모르는 실패: 종류를 남긴다", "ValueError" in unknown, True)
    check("모르는 실패: 원문을 안 싣는다", SECRET in unknown, False)
    check("모르는 실패: URL 을 안 싣는다", has_url(unknown), False)
    check("모르는 실패: 로그를 가리킨다", "로그" in unknown, True)

    # ⑤ 적재 서비스가 이 변환을 실제로 부른다 (문자열 배선 확인 — DB 없이)
    service_src = (_APP_DIR / "services" / "ingest" / "ingest_service.py").read_text(encoding="utf-8")
    check("적재 서비스가 변환을 태운다", "describe_provider_failure(exc, source)" in service_src, True)
    check("적재 서비스가 원문을 안 쓴다", 'redact_secrets(f"{type(exc).__name__}: {exc}")' in service_src, False)

    key_src = (_APP_DIR / "services" / "data_key" / "data_key_service.py").read_text(encoding="utf-8")
    check("키 확인 경로도 같은 변환을 태운다", "describe_provider_failure(exc, source)" in key_src, True)

    # 어댑터가 httpx 원문을 사유로 싣지 않는지 — 그 문자열도 화면까지 간다
    for adapter in ("alpaca", "data_go_kr"):
        text = (_APP_DIR / "providers" / adapter / "adapter.py").read_text(encoding="utf-8")
        check(f"{adapter}: 원문을 사유로 안 싣는다", "ProviderResponseInvalid(str(exc))" in text, False)

    check_stored_reasons()
    check_adapters_carry_status()

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    if CHECKED < 140:
        print(f"::error::단언이 {CHECKED}건뿐이다 — 그물이 죽어 있다", file=sys.stderr)
        return 1
    for line in FAILURES:
        print(f"::error::{line}", file=sys.stderr)
    if FAILURES:
        return 1
    print("판정: 실패 사유가 다음 행동을 말하고, 원문·URL·키를 싣지 않는다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
