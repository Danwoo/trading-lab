from typing import Any, Literal

from pydantic import BaseModel, Field
from schemas.common_schema import WEIGHT_MAX, CommonEntity, Money, TrimmedBaseModel

CombineRule = Literal["AND", "OR", "SCORE"]
UniverseKind = Literal["POOL", "WATCHLIST", "LIST"]
BotRole = Literal["READONLY", "PROPOSE", "EXECUTE"]
ParamSource = Literal["USER", "AI_SUGGESTED"]


class BotStrategyIn(BaseModel):
    """봇에 싣는 전략 하나. `params` 는 전략 선언에 대해 서비스가 검증한다."""

    strategy_key: str = Field(
        ...,
        max_length=40,
        description="전략 id — 등록된 전략의 키만 받습니다. 무엇이 지금 있는지는 GET /bot/strategy-catalog 가 답합니다.",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="전략 파라미터 — 이름 → 값. 그 전략이 선언한 이름만 받습니다. 비우면 전략의 기본값.",
    )
    # 설정별 출처 — 실험대 스펙 §8.6.3 「출처가 남는다」
    param_sources: dict[str, ParamSource] = Field(
        default_factory=dict,
        description="설정별 출처 — 설정 이름 → 'USER' 또는 'AI_SUGGESTED'.",
    )
    weight: Money | None = Field(
        None,
        ge=0,
        le=WEIGHT_MAX,
        description="combine_rule 이 SCORE 일 때의 가중치 — 0 이상 9999.99 까지, 소수점 둘째 자리까지.",
    )


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
    """봇의 「굴리는 규칙」. 입력·출력이 이 베이스를 함께 쓴다.

    각 필드의 형식은 **아래 `description` 이 정본**이다 — 그 문장이 OpenAPI 와 422 응답으로
    그대로 나간다 (#292).
    """

    bot_desc: str | None = Field(None, max_length=500, description="봇 설명 — 500자까지. 비워도 됩니다.")
    combine_rule: CombineRule = Field(
        default="AND",
        description="전략을 여럿 실었을 때 조건을 합치는 방법 — AND(모두 만족) · OR(하나라도 만족) · "
        "SCORE(가중합) 중 하나.",
    )
    universe_kind: UniverseKind = Field(
        default="WATCHLIST",
        description="봇이 볼 종목의 출처 — POOL(스크리너 풀 전체) · WATCHLIST(관심종목만) · "
        "LIST(universe_ref 에 적은 목록) 중 하나.",
    )
    universe_ref: dict[str, Any] | None = Field(
        default=None,
        description="universe_kind 가 LIST 일 때 볼 종목 목록을 담는 객체. 나머지 종류에서는 비웁니다.",
    )
    alloc_per_symbol: float | None = Field(
        None, ge=0, description="종목당 비중 (%, 0 이상). 비우면 배분을 정하지 않은 것으로 둡니다."
    )
    max_positions: int | None = Field(None, gt=0, description="동시에 들고 갈 최대 종목 수 (1 이상). 비우면 제한 없음.")
    stop_loss_pct: float | None = Field(None, ge=0, le=100, description="손절선 (%, 0~100). 비우면 손절하지 않습니다.")
    take_profit_pct: float | None = Field(None, ge=0, description="익절선 (%, 0 이상). 비우면 익절하지 않습니다.")
    max_trades_per_day: int | None = Field(None, gt=0, description="하루 최대 매매 횟수 (1 이상). 비우면 제한 없음.")
    bot_role: BotRole = Field(
        default="READONLY",
        description="봇이 하는 일 — READONLY(보기만) · PROPOSE(제안) · EXECUTE(실행) 중 하나. "
        "실주문은 아직 없어 지금 뜻이 있는 것은 READONLY·PROPOSE 입니다.",
    )
    use_at: str = Field("Y", max_length=1, description="사용 여부 — 'Y'(켜짐) 또는 'N'(꺼짐). 한 글자입니다.")
    param_sources: dict[str, ParamSource] = Field(
        default_factory=dict,
        description="설정별 출처 — 설정 이름 → 'USER'(사람이 정함) 또는 'AI_SUGGESTED'(대화가 제안함). "
        "안 적은 설정은 출처가 남지 않습니다.",
    )


class BotOut(Bot, CommonEntity):
    bot_id: int
    bot_nm: str


class BotDetailOut(BotOut):
    strategies: list[BotStrategyOut] = Field(default_factory=list)


class BotsOut(BaseModel):
    items: list[BotOut]
    total_count: int


class BotCreateIn(Bot):
    bot_nm: str = Field(..., min_length=1, max_length=100, description="봇 이름 — 1~100자, 빈 문자열은 안 됩니다.")
    # 전략 없는 봇은 아무 판정도 못 한다 — 서비스가 빈 목록을 거부한다.
    strategies: list[BotStrategyIn] = Field(
        default_factory=list,
        description="실을 전략 목록 — 최소 하나는 있어야 합니다(전략 없는 봇은 아무 판정도 못 합니다). "
        "항목마다 strategy_key(GET /bot/strategy-catalog 의 키)와 params 를 적습니다.",
    )


class BotUpdateIn(Bot):
    bot_nm: str = Field(..., min_length=1, max_length=100, description="봇 이름 — 1~100자, 빈 문자열은 안 됩니다.")
    # None 이면 전략 목록을 건드리지 않는다. 목록이 오면 통째로 갈아 끼운다.
    strategies: list[BotStrategyIn] | None = Field(
        default=None,
        description="전략 목록을 통째로 갈아 끼웁니다. 아예 비우면(null) 지금 전략을 그대로 둡니다 — "
        "빈 목록([])은 「전략을 다 지운다」는 뜻이라 거부됩니다.",
    )


class StrategyFieldOut(BaseModel):
    """폼 필드 하나. `control` 로 그리고 나머지는 그대로 흘려 넣는다 (규약 §5)."""

    name: str
    label: str
    control: Literal["number", "select", "toggle"]
    default: Any
    # `int | float` 순서가 중요하다 — `float` 만 선언하면 로더가 int 로 내보낸 경계를 다시
    # float 으로 강제해 폼에 `5.0~120.0` 이 나간다 (실측으로 잡힌 회귀).
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None
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
