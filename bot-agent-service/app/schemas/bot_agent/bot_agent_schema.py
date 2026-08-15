from pydantic import BaseModel, Field


class BotAgentIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class ReadinessOut(BaseModel):
    """`ready=false` 면 `reasons` 가 비어 있지 않다 — 화면이 그대로 보여준다."""

    ready: bool
    reasons: list[str]
    strategies_dir: str
