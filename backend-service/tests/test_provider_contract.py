"""오더 3(시세 적재) T3 — provider 계약(Protocol·정규화 모델·레지스트리·도메인 예외) 검증.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    cd backend-service && uv run python tests/test_provider_contract.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

검증 대상 불변식 (오더 3 T3 증명 의무):
- `MarketDataProvider` 의 모든 메서드가 정규화 모델(또는 그 리스트)을 반환하도록 타입이 선언돼
  있다 — `dict` 반환 시그니처가 없다(소스 표기가 밖으로 새는 유일한 통로를 막는다, 구현설계 §5.2).
- `get_provider()` 는 미등록 소스를 조용히 `None` 으로 넘기지 않고 명시적으로 실패한다 — Phase 1
  은 레지스트리가 비어 있는 것이 정상 상태이므로, 이 실패가 "설정 누락"과 "코드 결함"을 가른다.
- `RateLimitExhausted`·`ProviderResponseInvalid` 는 `fastapi.HTTPException` 이 아니라
  `core.exceptions.HTTPError` 계열이다(룰 10) — 각자 429·502 상태코드와 cursor/detail 을 갖는다.
- 정규화 모델의 닫힌 필드(`Capability.data_kind`·`NormalizedBar.adj_policy`)는 서드파티 응답이
  경계를 넘기 전에 계약 밖 값을 거절한다 — 이게 "서드파티 응답은 어댑터 안에서 검증한다"의 실측이다.
"""

from __future__ import annotations

import os
import subprocess
import sys
import typing
from pathlib import Path

# import 사슬이 core.config(settings)까지 닿는다 — `get_provider` 가 어댑터 모듈을 지연 import
# 하면서 core.logger → core.config 를 끌어오기 때문이다(어댑터 0개였던 Phase 1 에는 없던 사슬).
# 존재하지 않는 APP_ENV 로 .env 간섭을 끊고 필수 설정만 더미로 채운다. DB 접속은 하지 않는다.
os.environ["APP_ENV"] = "provider-contract-test"
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
}.items():
    os.environ.setdefault(_key, _value)

_TESTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _TESTS_DIR.parent
_APP_DIR = _BACKEND_DIR / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from core.exceptions import BadGatewayError, HTTPError, TooManyRequestsError  # noqa: E402
from providers import get_provider, register_provider  # noqa: E402
from providers.base import MarketDataProvider, ProviderResponseInvalid, RateLimitExhausted  # noqa: E402
from providers.models import Capability, NormalizedBar, NormalizedInstrument, NormalizedQuote  # noqa: E402
from pydantic import ValidationError  # noqa: E402

# 경계 검사의 정의는 이 파일이 아니라 `scripts/verify_provider_boundary.py` 하나다 — 소스 패키지
# 목록을 파일시스템에서 읽어 그 이름만 금지하고, 계약 모듈(models·base·merge)은 허용한다.
# 여기서 다시 grep 을 쓰면 규칙이 두 벌이 되고, 실제로 한 번 갈렸다(#2: 어댑터가 붙자
# Phase 1 의 `from providers\.` 통짜 grep 이 계약 import 까지 위반으로 잡았다).
_BOUNDARY_SCRIPT = _BACKEND_DIR / "scripts" / "verify_provider_boundary.py"


def test_protocol_methods_return_normalized_models_not_dict() -> str:
    """`dict` 반환 시그니처가 없어야 한다 — 있으면 원본 응답을 그대로 내보내는 통로가 생긴다."""
    hints = typing.get_type_hints(MarketDataProvider.capabilities)
    method_names = ["capabilities", "list_instruments", "fetch_daily", "fetch_minute", "fetch_quotes"]
    normalized_types = {NormalizedInstrument, NormalizedBar, NormalizedQuote, Capability}

    for name in method_names:
        method = getattr(MarketDataProvider, name)
        hints = typing.get_type_hints(method)
        ret = hints.get("return")
        assert ret is not None, f"{name} 에 반환 타입 애노테이션이 없다"
        assert ret is not dict, f"{name} 이 dict 를 그대로 반환한다"
        origin = typing.get_origin(ret)
        assert origin is list, f"{name} 의 반환 타입이 list 가 아니다: {ret!r}"
        (item_type,) = typing.get_args(ret)
        assert item_type in normalized_types, f"{name} 이 정규화 모델이 아닌 {item_type!r} 을 담은 list 를 반환한다"
    return "test_protocol_methods_return_normalized_models_not_dict"


def test_get_provider_fails_loudly_when_unregistered() -> str:
    """Phase 1 은 레지스트리가 비어 있는 것이 정상 — 그래도 조회는 조용한 None 이 아니라 명시적 실패다."""
    try:
        get_provider("does-not-exist", None)
    except Exception as exc:
        assert isinstance(exc, HTTPError), f"NotFoundError 는 HTTPError 계열이어야 하는데 {type(exc)!r}"
        assert exc.status_code == 404, f"미등록 소스 조회의 상태코드가 404 가 아니다: {exc.status_code}"
    else:
        raise AssertionError("미등록 소스인데 get_provider 가 예외 없이 반환했다 — 조용한 실패다")
    return "test_get_provider_fails_loudly_when_unregistered"


class _StubProvider:
    """등록 경로 자체를 실측하기 위한 최소 스텁 — 실제 소스 호출은 하지 않는다(T3 은 어댑터 0개)."""

    def __init__(self, api_key: str | None):
        self.api_key = api_key

    def capabilities(self) -> list[Capability]:
        return []


def test_register_then_get_round_trips_the_key() -> str:
    """등록된 소스는 조회되고, 키는 어댑터 생성자로 그대로 전달된다(AD-20 — settings. 를 읽지 않는다)."""
    import providers as providers_pkg

    register_provider("stub-for-test", lambda key: _StubProvider(key))
    try:
        provider = get_provider("stub-for-test", "sekrit-key")
        assert isinstance(provider, _StubProvider)
        assert provider.api_key == "sekrit-key", "키가 팩토리 인자로 전달되지 않았다"
    finally:
        # 테스트가 전역 레지스트리를 오염시키지 않게 정리한다 — 표준 프로세스 실행에서는 없어도
        # 되지만, pytest 수집 시 다른 테스트와 순서가 섞여도 안전하게 한다.
        providers_pkg._REGISTRY.pop("stub-for-test", None)
    return "test_register_then_get_round_trips_the_key"


def test_domain_exceptions_follow_existing_http_error_system() -> str:
    """RateLimitExhausted·ProviderResponseInvalid 는 fastapi.HTTPException 이 아니라 core.exceptions
    체계를 따른다(룰 10) — 각자 429·502 이고 cursor/detail 을 속성으로 갖는다."""
    rate_limited = RateLimitExhausted(cursor="page=42")
    assert isinstance(rate_limited, HTTPError), "RateLimitExhausted 가 HTTPError 계열이 아니다"
    assert isinstance(rate_limited, TooManyRequestsError), "RateLimitExhausted 의 베이스가 429 계열이 아니다"
    assert rate_limited.status_code == 429, f"RateLimitExhausted 상태코드가 429 가 아니다: {rate_limited.status_code}"
    assert rate_limited.cursor == "page=42", "cursor 속성이 보존되지 않았다"

    invalid = ProviderResponseInvalid(detail="close 필드 누락")
    assert isinstance(invalid, HTTPError), "ProviderResponseInvalid 가 HTTPError 계열이 아니다"
    assert isinstance(invalid, BadGatewayError), "ProviderResponseInvalid 의 베이스가 502 계열이 아니다"
    assert invalid.status_code == 502, f"ProviderResponseInvalid 상태코드가 502 가 아니다: {invalid.status_code}"
    assert invalid.detail == "close 필드 누락", "detail 속성이 보존되지 않았다"

    # fastapi.HTTPException 을 쓰지 않는다(룰 10) — 상속선에 없어야 한다.
    from fastapi import HTTPException

    assert not isinstance(rate_limited, HTTPException), "RateLimitExhausted 가 fastapi.HTTPException 을 상속한다"
    assert not isinstance(invalid, HTTPException), "ProviderResponseInvalid 가 fastapi.HTTPException 을 상속한다"
    return "test_domain_exceptions_follow_existing_http_error_system"


def test_normalized_models_reject_off_contract_values_at_the_boundary() -> str:
    """서드파티 응답이 정규화 모델로 변환되는 지점 자체가 검증 경계다 — 계약 밖 값은 여기서 막힌다."""
    valid_bar_kwargs = dict(
        symbol="005930",
        market="KOSPI",
        ts="2026-08-01T00:00:00",
        open="1000",
        high="1010",
        low="990",
        close="1005",
        volume=1000,
        adj_policy="raw",
    )
    NormalizedBar(**valid_bar_kwargs)  # 정상 값은 통과해야 한다

    off_contract_bar = dict(valid_bar_kwargs, adj_policy="split_adjusted_by_upstream")  # 계약 밖 값
    try:
        NormalizedBar(**off_contract_bar)
    except ValidationError:
        pass
    else:
        raise AssertionError("계약 밖 adj_policy 값이 NormalizedBar 를 통과했다")

    Capability(market="KOSPI", data_kind="daily_bar", available=True)  # 정상 값
    try:
        Capability(market="KOSPI", data_kind="realtime_orderbook_v2", available=True)  # 계약 밖 값
    except ValidationError:
        pass
    else:
        raise AssertionError("계약 밖 data_kind 값이 Capability 를 통과했다")
    return "test_normalized_models_reject_off_contract_values_at_the_boundary"


def test_no_provider_import_outside_providers_package() -> str:
    """`providers/<소스>` 는 `providers/` 밖에서 import 되지 않는다 (구현설계 §5.2 #1, 룰 15).

    판정은 `scripts/verify_provider_boundary.py` 가 한다 — 그 스크립트가 fail-closed(소스 패키지
    0건·스캔 파일 0건이면 실패)이고 검사 규모를 출력에 남긴다. 이 테스트는 **그 스크립트가 실제로
    존재하고 통과하는지**를 표준 테스트 러너 안에서 한 번 더 확인하는 자리다.
    """
    assert _BOUNDARY_SCRIPT.is_file(), f"경계 검사 스크립트가 없다: {_BOUNDARY_SCRIPT}"
    result = subprocess.run([sys.executable, str(_BOUNDARY_SCRIPT)], capture_output=True, text=True, cwd=_BACKEND_DIR)
    for line in result.stdout.splitlines():
        print(f"     {line}")
    assert result.returncode == 0, f"provider 경계 검사 실패:\n{result.stdout}\n{result.stderr}"
    return "test_no_provider_import_outside_providers_package"


def _main() -> int:
    tests = [
        test_protocol_methods_return_normalized_models_not_dict,
        test_get_provider_fails_loudly_when_unregistered,
        test_register_then_get_round_trips_the_key,
        test_domain_exceptions_follow_existing_http_error_system,
        test_normalized_models_reject_off_contract_values_at_the_boundary,
        test_no_provider_import_outside_providers_package,
    ]
    passed = 0
    for tc in tests:
        name = tc()
        print(f"PASS {name}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
