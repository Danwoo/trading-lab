from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


class BotAgentIn(BaseModel):
    # 공백만 담긴 메시지는 **경계에서** 막는다(422). 종전에는 `min_length=1` 을 통과한 뒤
    # 서비스가 던졌는데, 그 예외는 이미 시작된 SSE 제너레이터 안에서 나 exception_handler 가
    # 못 잡고 라우터가 삼켜 **200 + 제너릭 에러**가 됐다 (PR #154 독립 리뷰 공격 3).
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)] = Field(...)


class ReadinessOut(BaseModel):
    """`ready=false` 면 `reasons` 가 비어 있지 않다 — 화면이 그대로 보여준다."""

    ready: bool
    reasons: list[str]
    strategies_dir: str
