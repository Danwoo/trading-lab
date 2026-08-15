from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints


class FormStateIn(BaseModel):
    """지금 폼에 들어 있는 값. **에이전트가 자기 기억이 아니라 이것을 읽어야** 사용자가 손으로
    고친 값을 안다 (스펙 §8.6.1 「폼이 대화를 검증한다」)."""

    strategy_key: str | None = Field(None, max_length=40)
    params: dict[str, Any] = Field(default_factory=dict)


class BotAgentIn(BaseModel):
    # 공백만 담긴 메시지는 **경계에서** 막는다(422). 종전에는 `min_length=1` 을 통과한 뒤
    # 서비스가 던졌는데, 그 예외는 이미 시작된 SSE 제너레이터 안에서 나 exception_handler 가
    # 못 잡고 라우터가 삼켜 **200 + 제너릭 에러**가 됐다 (PR #154 독립 리뷰 공격 3).
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)] = Field(...)
    # 새 대화로 시작한다. **이어가기는 서버가 신원으로 판단한다** — 세션 id 를 클라이언트가
    # 보내게 하면 남의 세션 id 를 넣어 남의 대화를 이어받을 수 있다.
    reset: bool = False
    form: FormStateIn | None = None


class ReadinessOut(BaseModel):
    """`ready=false` 면 `reasons` 가 비어 있지 않다 — 화면이 그대로 보여준다."""

    ready: bool
    reasons: list[str]
    strategies_dir: str
