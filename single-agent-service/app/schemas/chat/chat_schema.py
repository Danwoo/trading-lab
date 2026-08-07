# ── [가이드 8/9] schemas/chat/chat_schema.py — 요청 본문 스키마 ──
# 무엇: /chat 요청 body. 단일턴 교본이라 question 하나뿐(멀티턴/history 는 졸업 경로 — README 참고).
# 복사 후: 도메인 입력 필드. Field(description) 로 의도를 남긴다.
# 함정: SSE 응답은 StreamingResponse 라 Pydantic Out 모델로 못 감싼다 — 이벤트 형태는 라우터 SSE 계약(주석)으로.

from pydantic import BaseModel, Field


class ChatIn(BaseModel):
    question: str = Field(description="사용자 질문 (예: 판소리가 뭐야?)")
