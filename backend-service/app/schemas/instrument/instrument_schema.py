from pydantic import BaseModel, Field


class InstrumentOut(BaseModel):
    """종목 마스터 한 줄. 관심종목 등록에 필요한 것만 낸다 — 상장일·섹터는 고르는 데 안 쓴다."""

    country: str
    market: str
    symbol: str
    issuer_nm: str
    currency: str
    is_active: str = Field(description="상장 상태 — 'Y'(상장) 또는 'N'(폐지).")


class InstrumentsOut(BaseModel):
    items: list[InstrumentOut]
    total_count: int
    unavailable_reason: str | None = Field(
        None,
        description=(
            "0건인 이유. 마스터를 아직 한 번도 안 받았을 때만 채워진다 —"
            " 「그런 종목이 없다」와 「아직 안 받았다」를 화면이 가를 수 있게 하는 값이다."
        ),
    )
