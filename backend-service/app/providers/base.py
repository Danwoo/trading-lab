"""provider 계약 — Protocol + 도메인 예외.

이 파일은 소스 0개 상태의 **계약**이다. 실제 소스 호출은 없다(오더 3 T3). 새 소스를 붙이는 일이
`providers/<소스>/` 파일 하나 추가로 끝나게 하는 것이 이 Protocol 의 존재 이유 — 소스가 다뤄야
하는 인증·페이지네이션·한도·에러를 여기 이름 붙이고, 그 밖(서비스·리포지토리·라우터)으로는
소스 사정이 새지 않게 한다(구현설계 §5.2).

I/O 메서드(`list_instruments`·`fetch_daily`·`fetch_minute`·`fetch_quotes`)는 이 레포의 외부
HTTP 클라이언트 관례(`clients/doc_search/doc_search_client.py` 등, httpx.AsyncClient 기반
`async def`)를 따라 async 로 선언한다 — Service/Repository 의 DB 메서드를 sync 로 두는 룰 12 는
DB I/O 에 대한 것이고, 여기는 외부 네트워크 I/O 다. `capabilities()` 는 소스별로 정적으로 결정되는
표(키 유무·시장×데이터종류 지원표)라 I/O 가 없어 sync 로 둔다.
"""

from datetime import date, datetime
from typing import Protocol

from core.exceptions import BadGatewayError, ServiceUnavailableError, TooManyRequestsError
from utils.redaction.redactor import redact_secrets

from providers.models import Capability, NormalizedBar, NormalizedInstrument, NormalizedQuote


class RateLimitExhausted(TooManyRequestsError):
    """어댑터가 소스 호출 한도(NFR-007)에 걸렸을 때 올린다. `cursor` 는 다음 실행이 이어받을
    지점 — `IngestService`(오더 3 T6)가 이 값을 `tn_ingest_run.cursor` 에 그대로 옮겨 적는다.
    조용히 실패하지 않는다는 요구가 이 예외 하나로 강제된다."""

    def __init__(self, cursor: str):
        self.cursor = cursor
        super().__init__(f"소스 호출 한도에 도달했습니다. 재개 지점: {cursor}")


class ProviderResponseInvalid(BadGatewayError):
    """서드파티 응답이 정규화 모델로 파싱되지 않을 때(필드 누락·타입 불일치 등) 올린다. 서드파티
    응답은 무조건 untrusted — 어댑터가 조용히 통과시키지 않고 이 예외로 그 행만 버린다.
    `detail` 에는 무엇이 어긋났는지만 담는다(원문 그대로 노출 금지 — 로그에는 남기되 사용자
    노출 메시지는 별도).

    **상류 텍스트가 우리 도메인 객체로 들어오는 유일한 통로**라서, 데이터 소스 키를 여기서 지운다
    — 이 `detail` 은 API 응답 `detail` 과 `tn_ingest_run.failed_reason` 으로 그대로 흘러간다.

    응답 **상태 코드**를 옮겨 온 것이라면 `http_status` 로 그 코드를 함께 넘긴다. 「다음에 무엇을
    하면 되나」(403 이면 IP 허용)를 아는 것은 코드이고, 그 문장을 세우는 곳은 `providers/failure.py`
    한 곳이다 — 코드를 여기서 문장으로 눌러 버리면 그 조언이 화면까지 오지 못한다."""

    def __init__(self, detail: str, *, http_status: int | None = None):
        self.detail = redact_secrets(detail)
        self.http_status = http_status
        super().__init__(f"공급자 응답이 유효하지 않습니다: {self.detail}")


# 키가 없어 못 한다는 capability 사유가 공유하는 문구. 사유 문자열을 substring 으로 뒤지는 대신
# **한 곳에서 정의한 상수**를 쓰기 위해 여기 둔다 — 어느 계층이 이 사유에 "그럼 어디서 받나"를
# 덧붙일지 판단하는 근거가 된다(`services/capability/`). 어댑터가 각자 다른 문장을 쓰면 그
# 판단이 조용히 빗나가므로, 키가 필요한 어댑터는 이 상수를 사유에 포함시킨다.
CREDENTIAL_MISSING_HINT = ".env 에 데이터 소스 키를 채우세요"

# 위 사유를 **기계가 읽는 값**으로도 흘린다. 화면은 「키가 아직 없다」와 「진짜 장애」를 달리
# 다뤄야 하는데(전자는 임시 데이터로 골조를 보여주고, 후자는 숨기면 안 된다 — 결정 로그
# 2026-07-28), 문구로 가르면 문구만 바뀌어도 조용히 갈린다.
CREDENTIAL_MISSING_CODE = "credential_missing"


# 「이 시장·종류의 정본은 내가 아니다」(MD-AD-17)를 말하는 사유. **결손이 아니라 안내**다 —
# 이 줄이 섞였다고 화면이 「키 없음」 판정을 잃으면, 소스를 하나 더 붙일 때마다 빈 보드가
# 이유를 잃는다 (실측: 토스 어댑터를 붙이자 국내 일봉의 `credential_missing` 이 사라졌다).
NOT_CANONICAL_HINT = "MD-AD-17 — 시장마다 정본 소스 하나"
NOT_CANONICAL_CODE = "not_canonical"


def not_canonical_reason(what: str, canonical_source: str) -> str:
    """정본이 아닌 소스가 다는 표준 사유 — 문구를 어댑터마다 새로 쓰지 않게."""
    return f"{what}의 정본 소스는 {canonical_source} 입니다 ({NOT_CANONICAL_HINT})"


class ProviderKeyMissing(ServiceUnavailableError):
    """키가 있어야 하는 소스를 키 없이 호출했을 때 올린다.

    **기동을 막지 않는다**(FR-013) — 어댑터는 키가 없어도 만들어지고, `capabilities()` 가
    `available=False` + 사유로 그 사실을 데이터로 노출한다. 이 예외는 그 사유를 무시하고 실제
    호출까지 온 경로에서만 터진다. 조용히 빈 목록을 돌려주지 않는 이유는 "데이터가 없다"와
    "키가 없어 못 물어봤다"가 화면에서 구분돼야 하기 때문이다(FR-021).
    """

    def __init__(self, source: str, env_hint: str):
        self.source = source
        self.env_hint = env_hint
        super().__init__(f"{source} 소스의 API 키가 없습니다. .env 에 데이터 소스 키({env_hint})를 채우세요.")


class MarketDataProvider(Protocol):
    """시세 소스 어댑터가 구현해야 하는 계약. 못 하는 것은 예외가 아니라 `capabilities()` 의
    `available=False` 로 표현한다(FR-021) — 그래야 화면이 이유를 보여줄 수 있다."""

    def capabilities(self) -> list[Capability]:
        """이 어댑터(=이 소스, 이 인스턴스의 키 유무)가 시장 × 데이터종류마다 무엇을 줄 수 있는지."""
        ...

    async def list_instruments(self, market: str) -> list[NormalizedInstrument]:
        """종목 마스터 (FR-008)."""
        ...

    async def fetch_daily(self, symbol: str, market: str, date_from: date, date_to: date) -> list[NormalizedBar]:
        """일봉 — 기간 지정. 페이지네이션은 어댑터가 감춘다."""
        ...

    async def fetch_minute(
        self, symbol: str, market: str, ts_from: datetime, ts_to: datetime, interval_min: int
    ) -> list[NormalizedBar]:
        """분봉 — 유니버스 한정(FR-046). 저장 목적 호출은 항상 `interval_min=1`(AD-26) — 이 인자
        자체는 소스 쪽 조회 세분화용이지 저장 스키마가 여러 주기를 받는다는 뜻이 아니다."""
        ...

    async def fetch_quotes(self, symbols: list[tuple[str, str]]) -> list[NormalizedQuote]:
        """일괄 시세 조회 — 사이드바·봇이 쓴다(FR-048·049). 구독이 아니라 요청-응답이다."""
        ...


class AliasResolver(Protocol):
    """표준 식별자(FIGI·ISIN·CUSIP) 매핑 전용 계약 — `MarketDataProvider` 와 **별개**다.

    왜 나누는가: OpenFIGI 같은 식별자 소스는 티커를 **입력으로 받아** 매핑을 돌려주는 모양이라
    `list_instruments(market)`("시장을 통째로 내놔")를 구조적으로 만족할 수 없다. 그런 소스를
    `MarketDataProvider` 에 욱여넣으면 다섯 메서드 중 넷이 `available=False` 인 껍데기가 되고,
    "이 소스는 무엇을 하는가"가 capability 표에서 읽히지 않는다(T3 위험 항목이 경고한 형태).

    기존 계약을 바꾸지 않는 **추가**다 — `MarketDataProvider` 구현체는 이 Protocol 을 몰라도 된다.
    `tn_symbol_alias.alias_kind` 의 `figi`·`isin`·`cusip` 이 채워지는 유일한 경로이며,
    반환 dict 의 키는 그 `alias_kind` 문자열이다.
    """

    def capabilities(self) -> list[Capability]:
        """이 리졸버가 시장별로 별칭을 붙일 수 있는지 — `data_kind` 는 `instrument_master` 다."""
        ...

    async def resolve_aliases(self, symbols: list[tuple[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
        """`(market, symbol)` → `{alias_kind: alias_value}`. 매핑되지 않은 종목은 결과에서 빠진다
        (빈 dict 가 아니라 키 자체가 없다) — "매핑 없음"과 "매핑이 비었음"을 호출부가 가른다."""
        ...
