"""리서치 문서 잡 스토어 입출력 스키마.

Create 입력은 클라이언트가 넘기는 파일 참조(atch_file_id/file_sn/doc_title)만 받는다 —
workspace_id/user_id 는 인증 토큰 컨텍스트에서 채우고 클라이언트 입력을 신뢰하지 않는다(테넌트 격리).
status/chunk_count/error_msg 는 인제스트 결과로 서버가 채우는 잡 상태 필드다.
IngestResultIn 만 클라이언트 계약이 아니라 doc-search 응답을 저장 전에 좁히는 신뢰 경계다.
"""

from typing import Literal

from pydantic import BaseModel, Field
from schemas.common_schema import CommonEntity, TrimmedBaseModel

# mock-indexed 는 doc-search MOCK 모드 결과 — 파싱·청킹만 하고 pg 미색인이라 검색되지 않는다.
ResearchDocStatus = Literal["uploaded", "indexed", "mock-indexed", "empty", "failed"]


class ResearchDocumentCreateIn(TrimmedBaseModel):
    atch_file_id: str = Field(..., max_length=20, description="file 모듈 첨부 그룹 ID")
    file_sn: int = Field(..., ge=0, description="첨부 그룹 내 파일 순번(file 모듈 0-기반 채번)")
    doc_title: str | None = Field(None, max_length=500, description="원본 파일명(근거 표시명)")


class ResearchDocumentOut(CommonEntity):
    research_doc_id: int
    workspace_id: int
    user_id: str
    atch_file_id: str
    file_sn: int | None = None
    doc_title: str | None = None
    status: ResearchDocStatus
    chunk_count: int | None = None
    error_msg: str | None = None


class ResearchDocumentsOut(BaseModel):
    items: list[ResearchDocumentOut]
    total_count: int


class IngestResultIn(BaseModel):
    """doc-search 인제스트 응답 — 잡행에 쓰기 전 좁히는 신뢰 경계 (클라이언트 계약 아님).

    업스트림이 계약 밖 값을 내면 저장은 성공하고 뒤이은 GET 이 ResearchDocumentOut 검증에서
    500 이 된다 — 원인에서 먼 곳에서 터지는 실패다. 여기서 걸러 실패 상태로 낮춘다.
    """

    status: ResearchDocStatus
    chunk_count: int | None = None
