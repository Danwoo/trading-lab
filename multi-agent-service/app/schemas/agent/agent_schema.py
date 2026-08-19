"""에이전트 요청 스키마.

QueryIn — 네이티브 /agent. ExampleAIQueryIn — ai-chatbot 프론트 호환 /agent/example-ai.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryIn(BaseModel):
    question: str = Field(description="사용자 질문")
    gid: int = Field(default=0, description="대화 세션 ID (ai_chat_history 조회 키)")
    enabled_mcps: list[str] | None = Field(default=None, description="활성 MCP 서비스명 목록 (생략=전체)")


class ExampleAIQueryIn(BaseModel):
    """ai-chatbot 백엔드 호환 입력. switch1-5 → enabled_mcps 로 번역."""

    gid: int
    question: str
    switch1: bool = True  # web
    switch2: bool = True  # market-data
    switch3: bool = True  # disclosure
    switch4: bool = True  # news
    switch5: bool = True  # doc-search


class LlmRoleOut(BaseModel):
    """한 역할이 지금 무엇으로 답하는가. **키는 없다** — 주소·모델은 비밀이 아니다."""

    role: str
    provider: str
    provider_name: str
    base_url: str | None = None
    model: str | None = None
    sends_vllm_extra_body: bool = False
    #: 설정이 모자란 이유. **「통하는가」가 아니다** — 그것은 probe 가 답한다.
    reason: str | None = None
    #: 부를 수는 있는데 이상한 상태 (예: 제공자와 BASE_URL 이 다른 곳을 가리킨다).
    warning: str | None = None


class LlmProviderOut(BaseModel):
    id: str
    name: str
    model_example: str
    key_hint: str


class LlmStatusOut(BaseModel):
    roles: list[LlmRoleOut]
    #: 설정 세 칸이 채워졌는가. 키가 **통하는가**는 `POST /agent/llm/probe` 가 답한다.
    configured: bool
    fallbacks: int
    fallback_problems: list[str]
    providers: list[LlmProviderOut]


class LlmProbeOut(BaseModel):
    role: str
    ok: bool
    #: 실제로 물어봤는가 — 설정이 모자라 못 물어본 경우는 `false` 다(「실패」와 다르다).
    checked: bool
    detail: str


class LlmProbeListOut(BaseModel):
    items: list[LlmProbeOut]
    total_count: int
