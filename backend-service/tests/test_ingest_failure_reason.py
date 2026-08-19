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

    print(f"검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    if CHECKED < 70:
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
