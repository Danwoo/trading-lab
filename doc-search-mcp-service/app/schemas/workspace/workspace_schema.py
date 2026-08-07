"""워크스페이스 인제스트 입출력 스키마. (검색 tool 은 vector_search_schema 의 TopicSearchIn/Out 을 재사용한다.)"""

from typing import Literal

from pydantic import BaseModel, Field


class IngestOut(BaseModel):
    job_ref: str = Field(description="인제스트 참조 키 (원본 첨부 그룹 atch_file_id)")
    chunk_count: int = Field(description="색인된 청크 수")
    status: Literal["indexed", "mock-indexed", "empty", "failed"] = Field(
        description="처리 상태 — indexed(청크 색인 완료) / mock-indexed(MOCK 모드: 파싱·청킹만, pg 미색인이라 검색 불가) "
        "/ empty(텍스트 추출 0건: 스캔 PDF·빈 문서, 구조 파서 필요) / failed"
    )


class WorkspaceDeleteOut(BaseModel):
    atch_file_id: str = Field(description="회수 대상 첨부 그룹 ID")
    deleted_count: int = Field(description="삭제된 청크 수 (MOCK 모드·미색인 파일은 0)")
