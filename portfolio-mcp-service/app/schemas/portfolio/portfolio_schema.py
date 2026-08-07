from typing import Literal

from pydantic import BaseModel, Field


class FxRate(BaseModel):
    rate: float = Field(description="1 단위 원통화 = rate 단위 기준통화 (통화쌍 '원통화/기준통화' 의 현재 환율)")
    asof: str = Field(default="", description="환율 기준 시각 (ISO-8601). 시세는 지연될 수 있음")


class AccountInfo(BaseModel):
    account_id: str = Field(description="계좌 식별자 (내부 ID, 마스킹 안 됨)")
    account_no: str = Field(
        description="계좌번호. 가운데가 '[계좌번호 일부 가려짐]' 형태로 마스킹된 상태 — 복원하지 말 것"
    )
    account_name: str = Field(description="계좌 별칭 (예: 종합매매계좌, ISA, 연금저축)")
    account_type: str = Field(description="계좌 유형: cash(위탁), margin(신용), isa, pension(연금) 등")
    base_currency: str = Field(description="기준 통화 (예: KRW, USD)")
    nav: float = Field(
        description="순자산가치(NAV) — 기준통화(base_currency) 분. 그 통화의 평가금액+예수금. 외화 보유분은 nav_by_currency 참조"
    )
    nav_by_currency: dict[str, float] = Field(
        description="통화별 순자산가치(환율 환산 없음). 예수금은 기준통화 버킷에 포함. 단일통화 계좌면 {base_currency: nav}"
    )
    nav_in_base: float = Field(
        default=0.0,
        description="기준통화(base_currency)로 환산 합산한 순자산가치. unconverted_currencies 통화는 환율이 없어 제외됨(그 통화 제외한 합)",
    )
    fx_rates_used: dict[str, FxRate] = Field(
        default_factory=dict,
        description="환산에 쓴 통화쌍별 환율 근거 {pair: {rate, asof}}. 환산이 없으면(단일통화) 빈 dict",
    )
    unconverted_currencies: list[str] = Field(
        default_factory=list,
        description="환율이 없어 nav_in_base 에서 제외된 통화 목록. 비어야 nav_in_base 가 전체를 포괄(지어내지 않음)",
    )
    cash_balance: float = Field(description="예수금(현금성) 잔액. 기준 통화 단위")


class AccountsOut(BaseModel):
    items: list[AccountInfo] = Field(description="계좌 목록")
    total_count: int = Field(description="계좌 총 개수")


class HoldingLine(BaseModel):
    account_id: str = Field(description="이 보유분이 속한 계좌 식별자")
    ticker: str = Field(description="종목 티커/코드 (예: 005930, AAPL)")
    name: str = Field(description="종목명")
    asset_class: str = Field(description="자산군: equity(주식), etf, bond(채권), fund, cash 등")
    quantity: float = Field(description="보유 수량")
    avg_price: float = Field(description="평균 매입단가. 종목 통화 단위")
    last_price: float = Field(description="현재가(평가단가). 종목 통화 단위. 시세 지연 가능")
    market_value: float = Field(description="평가금액 = 수량 × 현재가. 종목 통화 단위")
    unrealized_pnl: float = Field(description="평가손익 = 평가금액 − (평균단가 × 수량). 종목 통화 단위")
    weight: float = Field(description="계좌 내 비중(%) = 평가금액 / 계좌 평가자산 × 100")
    currency: str = Field(description="종목 거래 통화")


class HoldingsIn(BaseModel):
    account_id: str | None = Field(
        default=None,
        description="단일 계좌 식별자. 지정 시 그 계좌의 보유종목만, 미지정 시 전체 계좌 합산 조회",
    )
    asset_class: Literal["equity", "etf", "bond", "fund", "cash"] | None = Field(
        default=None,
        description="자산군 필터. 지정 시 해당 자산군만. 미지정 시 전체",
    )
    ticker_keywords: list[str] = Field(
        default_factory=list,
        description="종목명/티커 부분일치 키워드. 빈 리스트면 전체 보유종목",
    )
    min_weight: float | None = Field(
        default=None,
        description="최소 비중(%) 필터. 지정 시 계좌 내 비중이 이 값 이상인 보유분만. 미지정 시 제한 없음",
    )
    base_currency: str = Field(
        default="KRW",
        description="기준통화. total_market_value_in_base 를 이 통화로 환산해 낸다 (예: KRW, USD). 미지정 시 KRW",
    )


class HoldingsOut(BaseModel):
    holdings: list[HoldingLine] = Field(description="보유종목 목록. 평가금액 내림차순 정렬")
    holding_count: int = Field(description="조회된 보유종목 수")
    total_market_value_by_currency: dict[str, float] = Field(
        description="통화별 평가금액 합계(환율 환산 없음). 통화가 섞인 결과도 통화별로 분리돼 합산이 무의미해지지 않는다"
    )
    base_currency: str = Field(default="KRW", description="total_market_value_in_base 환산 기준통화")
    total_market_value_in_base: float = Field(
        default=0.0,
        description="기준통화로 환산 합산한 평가금액. unconverted_currencies 통화는 환율이 없어 제외됨",
    )
    fx_rates_used: dict[str, FxRate] = Field(
        default_factory=dict, description="환산에 쓴 통화쌍별 환율 근거 {pair: {rate, asof}}"
    )
    unconverted_currencies: list[str] = Field(
        default_factory=list,
        description="환율이 없어 total_market_value_in_base 에서 제외된 통화 목록(지어내지 않음)",
    )
    accounts: list[str] = Field(description="결과에 포함된 계좌 식별자 목록")


class TransactionLine(BaseModel):
    account_id: str = Field(description="거래가 속한 계좌 식별자")
    trade_date: str = Field(description="거래(체결)일. 형식 YYYY-MM-DD")
    tx_type: str = Field(
        description="거래 유형: buy(매수), sell(매도), deposit(입금), withdraw(출금), dividend(배당), fee(수수료/세금)"
    )
    ticker: str = Field(default="", description="종목 티커. 입출금·수수료 등 종목 무관 거래는 빈 문자열")
    name: str = Field(default="", description="종목명. 종목 무관 거래는 빈 문자열")
    quantity: float = Field(default=0.0, description="수량. 입출금·수수료 등은 0")
    price: float = Field(default=0.0, description="체결 단가. 입출금 등은 0")
    amount: float = Field(description="거래 금액(부호 포함). 매수·출금·수수료는 음수, 매도·입금·배당은 양수")
    currency: str = Field(description="거래 통화")


class SearchTransactionsIn(BaseModel):
    account_id: str | None = Field(
        default=None,
        description="단일 계좌 식별자. 미지정 시 전체 계좌 거래 검색",
    )
    tx_type: Literal["buy", "sell", "deposit", "withdraw", "dividend", "fee"] | None = Field(
        default=None,
        description="거래 유형 필터. 미지정 시 전체 유형",
    )
    ticker_keywords: list[str] = Field(
        default_factory=list,
        description="종목명/티커 부분일치 키워드. 빈 리스트면 종목 필터 없음",
    )
    since: str | None = Field(
        default=None,
        description="시작일. ISO 8601 또는 YYYY-MM-DD. 미지정 시 최근 30일",
    )
    until: str | None = Field(
        default=None,
        description="종료일. ISO 8601 또는 YYYY-MM-DD. 미지정 시 현재 시각",
    )
    base_currency: str = Field(
        default="KRW",
        description="기준통화. net_amount_in_base 를 이 통화로 환산해 낸다 (예: KRW, USD). 미지정 시 KRW",
    )


class SearchTransactionsOut(BaseModel):
    transactions: list[TransactionLine] = Field(description="거래 목록. 시간순(오래된→최신)")
    transaction_count: int = Field(description="조회된 거래 수")
    truncated: bool = Field(description="250건 초과로 결과가 잘렸는지")
    period: str = Field(description="검색 기간. 형식 YYYY-MM-DD ~ YYYY-MM-DD")
    net_amount_by_currency: dict[str, float] = Field(
        description="통화별 거래 금액 부호합(환율 환산 없음). 순현금흐름 추정용 — 통화가 섞여도 통화별로 분리"
    )
    base_currency: str = Field(default="KRW", description="net_amount_in_base 환산 기준통화")
    net_amount_in_base: float = Field(
        default=0.0,
        description="기준통화로 환산한 순현금흐름 부호합. unconverted_currencies 통화는 환율이 없어 제외됨",
    )
    fx_rates_used: dict[str, FxRate] = Field(
        default_factory=dict, description="환산에 쓴 통화쌍별 환율 근거 {pair: {rate, asof}}"
    )
    unconverted_currencies: list[str] = Field(
        default_factory=list,
        description="환율이 없어 net_amount_in_base 에서 제외된 통화 목록(지어내지 않음)",
    )
    accounts: list[str] = Field(description="결과에 포함된 계좌 식별자 목록")


class OrderLine(BaseModel):
    account_id: str = Field(description="주문이 속한 계좌 식별자")
    order_id: str = Field(description="주문 식별자")
    ticker: str = Field(description="종목 티커")
    name: str = Field(description="종목명")
    side: str = Field(description="매매 구분: buy(매수), sell(매도)")
    order_type: str = Field(description="주문 유형: limit(지정가), market(시장가)")
    status: str = Field(
        description="주문 상태: filled(체결), partial(부분체결), open(미체결), canceled(취소), rejected(거부)"
    )
    quantity: float = Field(description="주문 수량")
    filled_quantity: float = Field(description="체결 수량")
    price: float = Field(description="주문 가격(지정가). 시장가는 0")
    avg_fill_price: float = Field(description="평균 체결가. 미체결 시 0")
    placed_at: str = Field(description="주문 접수일. 형식 YYYY-MM-DD")
    currency: str = Field(description="주문 통화")


class SearchOrdersIn(BaseModel):
    account_id: str | None = Field(
        default=None,
        description="단일 계좌 식별자. 미지정 시 전체 계좌 주문 검색",
    )
    status: Literal["filled", "partial", "open", "canceled", "rejected"] | None = Field(
        default=None,
        description="주문 상태 필터 ('미체결'=open, '취소'=canceled). 미지정 시 전체 상태",
    )
    side: Literal["buy", "sell"] | None = Field(
        default=None,
        description="매매 구분 필터: buy 또는 sell. 미지정 시 전체",
    )
    ticker_keywords: list[str] = Field(
        default_factory=list,
        description="종목명/티커 부분일치 키워드. 빈 리스트면 종목 필터 없음",
    )
    since: str | None = Field(
        default=None,
        description="시작일 (주문 접수일 기준). ISO 8601 또는 YYYY-MM-DD. 미지정 시 최근 30일",
    )
    until: str | None = Field(
        default=None,
        description="종료일. ISO 8601 또는 YYYY-MM-DD. 미지정 시 현재 시각",
    )


class SearchOrdersOut(BaseModel):
    orders: list[OrderLine] = Field(description="주문 목록. 최신 접수순, 최대 250건")
    order_count: int = Field(description="조회된 주문 수")
    truncated: bool = Field(description="250건 초과로 결과가 잘렸는지")
    period: str = Field(description="검색 기간. 형식 YYYY-MM-DD ~ YYYY-MM-DD")
    accounts: list[str] = Field(description="결과에 포함된 계좌 식별자 목록")


class ActivityLine(BaseModel):
    date: str = Field(description="활동 날짜. 형식 YYYY-MM-DD")
    action: str = Field(description="활동 유형: trade(체결), order(주문), cash(입출금), dividend(배당), fee(수수료) 등")
    detail: str = Field(description="활동 요약 한 줄 (종목·수량·금액 등). 계좌번호 등 민감정보는 마스킹된 상태")
    amount: float = Field(default=0.0, description="관련 금액(부호 포함). 해당 없으면 0")


class AccountActivityIn(BaseModel):
    account_id: str = Field(
        description="계좌 식별자 (정확일치). 계좌를 모르면 먼저 portfolio_list_accounts 로 account_id 를 확정",
    )
    since: str | None = Field(
        default=None,
        description="시작일. ISO 8601 또는 YYYY-MM-DD. 미지정 시 최근 30일",
    )
    until: str | None = Field(
        default=None,
        description="종료일. ISO 8601 또는 YYYY-MM-DD. 미지정 시 현재 시각",
    )


class AccountActivityOut(BaseModel):
    account_id: str = Field(description="조회 대상 계좌 식별자")
    events: list[ActivityLine] = Field(description="활동 이벤트 목록 (체결·주문·입출금·배당 통합, 최신순, 최대 250건)")
    count: int = Field(description="조회된 이벤트 수")
    truncated: bool = Field(
        default=False,
        description="250건 초과로 결과가 잘렸는지",
    )
    found: bool = Field(
        description="계좌(account_id)를 찾았는지. False 이면 계좌 미존재 — '활동 0건'과 구분 필요",
    )
    period: str = Field(description="조회 기간. 형식 YYYY-MM-DD ~ YYYY-MM-DD")
