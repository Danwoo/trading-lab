from pydantic import BaseModel, ConfigDict, Field
from schemas.common_schema import MONEY_MAX, QUANTITY_MAX, CommonEntity, Money, TrimmedBaseModel


# ── Portfolio (master) ─────────────────────────────────────────────────
class Portfolio(TrimmedBaseModel):
    """포트폴리오(마스터). 입력·출력이 이 베이스를 함께 쓴다.

    각 필드의 형식은 **아래 `description` 이 정본**이다 — 그 문장이 OpenAPI 와 422 응답으로
    그대로 나간다 (#292).
    """

    portfolio_nm: str = Field(..., max_length=200, description="포트폴리오 이름 — 200자까지.")
    sort_ordr: int = Field(default=1, description="목록에서의 정렬 순서 (정수). 작을수록 앞에 옵니다.")
    use_at: str = Field(default="Y", max_length=1, description="사용 여부 — 'Y'(사용) 또는 'N'(미사용). 한 글자입니다.")
    description: str | None = Field(None, max_length=1000, description="설명 — 1000자까지. 비워도 됩니다.")


class PortfolioOut(Portfolio, CommonEntity):
    portfolio_id: str


class PortfoliosOut(BaseModel):
    items: list[PortfolioOut]
    total_count: int


class PortfolioCreateIn(Portfolio):
    # 모르는 필드를 조용히 버리지 않는다 — 오타 하나로 값이 사라지고도 저장은 성공했다고 뜬다.
    model_config = ConfigDict(extra="forbid")

    portfolio_id: str = Field(
        ..., max_length=20, description="포트폴리오 id — 직접 정하는 값입니다. 20자까지, 이미 있는 id 면 거부됩니다."
    )


class PortfolioUpdateIn(Portfolio):
    model_config = ConfigDict(extra="forbid")


# ── Holding (detail) ───────────────────────────────────────────────────
class Holding(TrimmedBaseModel):
    """보유종목(디테일). 입력·출력이 이 베이스를 함께 쓴다."""

    holding_nm: str = Field(..., max_length=200, description="종목명 — 200자까지.")
    quantity: int = Field(default=0, ge=0, le=QUANTITY_MAX, description="보유 수량 — 0 이상의 정수. 21억 주까지.")
    avg_price: Money = Field(
        default=0, ge=0, le=MONEY_MAX, description="평균 매입 단가 — 0 이상, 소수점 둘째 자리까지."
    )
    # Watchlist.market 과 대칭(#328) — 기존 행은 백필하지 않아 비어 있을 수 있다.
    market: str | None = Field(
        None,
        max_length=20,
        description="시장 코드 — 공통코드 「관심종목 시장」(KOSPI · KOSDAQ · NASDAQ · NYSE)의 코드값. 20자까지.",
        examples=["KOSPI"],
    )
    use_at: str = Field(default="Y", max_length=1, description="사용 여부 — 'Y'(사용) 또는 'N'(미사용). 한 글자입니다.")
    description: str | None = Field(None, max_length=1000, description="설명 — 1000자까지. 비워도 됩니다.")


class HoldingOut(Holding, CommonEntity):
    portfolio_id: str
    ticker: str
    portfolio_nm: str | None = None


class HoldingsOut(BaseModel):
    items: list[HoldingOut]
    total_count: int


class HoldingCreateIn(Holding):
    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(
        ...,
        max_length=20,
        description="종목 코드 — 20자까지. 시장은 market 에 따로 적습니다. 같은 포트폴리오에 이미 있으면 거부됩니다.",
        examples=["005930"],
    )


class HoldingUpdateIn(Holding):
    model_config = ConfigDict(extra="forbid")
