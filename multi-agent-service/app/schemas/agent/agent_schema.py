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
