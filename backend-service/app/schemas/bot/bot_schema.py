from typing import Any, Literal

from pydantic import BaseModel, Field
from schemas.common_schema import CommonEntity, TrimmedBaseModel

CombineRule = Literal["AND", "OR", "SCORE"]
UniverseKind = Literal["POOL", "WATCHLIST", "LIST"]
BotRole = Literal["READONLY", "PROPOSE", "EXECUTE"]
ParamSource = Literal["USER", "AI_SUGGESTED"]


class BotStrategyIn(BaseModel):
    """봇에 싣는 전략 하나. `params` 는 전략 선언에 대해 서비스가 검증한다."""

    strategy_key: str = Field(..., max_length=40)
    params: dict[str, Any] = Field(default_factory=dict)
    # 설정별 출처 — 실험대 스펙 §8.6.3 「출처가 남는다」
    param_sources: dict[str, ParamSource] = Field(default_factory=dict)
    weight: float | None = Field(None, ge=0)


class BotStrategyOut(BaseModel):
    bot_strategy_id: int
    strategy_key: str
    params: dict[str, Any]
    param_sources: dict[str, str]
    weight: float | None
    sort_order: int
    # 지금의 전략 선언에서 만든 폼. 전략 파일이 사라졌으면 None 이고 이유가 온다.
    form: dict[str, Any] | None = None
    missing_reason: str | None = None


class Bot(TrimmedBaseModel):
    bot_desc: str | None = Field(None, max_length=500)
    combine_rule: CombineRule = "AND"
    universe_kind: UniverseKind = "WATCHLIST"
    universe_ref: dict[str, Any] | None = None
    alloc_per_symbol: float | None = Field(None, ge=0)
    max_positions: int | None = Field(None, gt=0)
    stop_loss_pct: float | None = Field(None, ge=0, le=100)
    take_profit_pct: float | None = Field(None, ge=0)
    max_trades_per_day: int | None = Field(None, gt=0)
    bot_role: BotRole = "READONLY"
    use_at: str = Field("Y", max_length=1)
    param_sources: dict[str, ParamSource] = Field(default_factory=dict)


class BotOut(Bot, CommonEntity):
    bot_id: int
    bot_nm: str


class BotDetailOut(BotOut):
    strategies: list[BotStrategyOut] = Field(default_factory=list)


class BotsOut(BaseModel):
    items: list[BotOut]
    total_count: int


class BotCreateIn(Bot):
    bot_nm: str = Field(..., min_length=1, max_length=100)
    # 전략 없는 봇은 아무 판정도 못 한다 — 서비스가 빈 목록을 거부한다.
    strategies: list[BotStrategyIn] = Field(default_factory=list)


class BotUpdateIn(Bot):
    bot_nm: str = Field(..., min_length=1, max_length=100)
    # None 이면 전략 목록을 건드리지 않는다. 목록이 오면 통째로 갈아 끼운다.
    strategies: list[BotStrategyIn] | None = None


class StrategyFieldOut(BaseModel):
    """폼 필드 하나. `control` 로 그리고 나머지는 그대로 흘려 넣는다 (규약 §5)."""

    name: str
    label: str
    control: Literal["number", "select", "toggle"]
    default: Any
    min: float | None = None
    max: float | None = None
    step: float | None = None
    unit: str | None = None
    options: list[dict[str, str]] | None = None
    help: str | None = None


class StrategyFormOut(BaseModel):
    key: str
    name: str
    summary: str | None = None
    timeframe: str
    fields: list[StrategyFieldOut]


class StrategyLoadErrorOut(BaseModel):
    source: str
    message: str


class StrategyCatalogOut(BaseModel):
    """읽은 전략과 **못 읽은 이유**를 함께 낸다 — 빈 목록이 「없음」인지 「실패」인지 구분되게."""

    items: list[StrategyFormOut]
    errors: list[StrategyLoadErrorOut]
