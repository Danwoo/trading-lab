"""워크스페이스 문서 인제스트·검색 오케스트레이션 — parse→chunk→embed→pgvector 색인, 그리고 dense 검색.

WORKSPACE_REAL_API=false(기본 — 미설정 시 USE_REAL_API 상속, #190)면 pg·임베딩 없이 단독 동작한다:
- 인제스트: 파서·청킹(오프라인 동작)까지 수행하고 pg 색인은 건너뛴 뒤 status="mock-indexed" 로 청크 수를 리포트한다.
- 검색: MOCK 금융 문서 스냅샷을 반환한다(mock_data).

테넌트 격리(fail-closed): 실검색 경로는 workspace_id 가 없으면 어떤 임베딩·쿼리도 하기 전에 거부한다.
인제스트/임베딩 블로킹은 run_in_threadpool 로 오프로드한다(anti-pattern 13).
"""

from clients.embedding.embedding_client import EmbeddingClient
from clients.parser.parser import ParsedDoc
from core.exceptions import UnauthorizedError
from fastapi.concurrency import run_in_threadpool
from repositories.workspace.workspace_chunk_repository import WorkspaceChunkRepository
from schemas.vector_search.vector_search_schema import TopicSearchIn, TopicSearchItem, TopicSearchOut
from schemas.workspace.workspace_schema import IngestOut, WorkspaceDeleteOut
from utils.ingest.chunking import Chunk, chunk_pages
from utils.vector_search.mock_data import mock_topic_out

_WORKSPACE_COLLECTION = "topic_workspace"  # MOCK 픽스처 조회 키 (기본 픽스처로 폴백)
_TEXT_PREVIEW_CHARS = 800


class WorkspaceService:
    def __init__(
        self,
        workspace_repository: WorkspaceChunkRepository,
        embedding_client: EmbeddingClient,
        parser,
        use_real_api: bool = False,
    ):
        self.repository = workspace_repository
        self.embedding = embedding_client
        self.parser = parser
        self.use_real_api = use_real_api

    async def ingest(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        workspace_id: int,
        user_id: str,
        atch_file_id: str,
        file_sn: int,
        doc_title: str,
    ) -> IngestOut:
        # 파싱(블로킹)·청킹(CPU) 오프로드 — 이벤트 루프 보호
        parsed: ParsedDoc = await run_in_threadpool(self.parser.parse, file_bytes, filename)
        chunks: list[Chunk] = await run_in_threadpool(chunk_pages, [(page.page_no, page.text) for page in parsed.pages])
        if not chunks:
            # 텍스트 추출 0건(스캔 PDF·빈 문서) — "indexed" 와 구분해 호출자(슬라이스 B)가
            # 추출 실패(구조 파서 필요)를 색인 성공과 오인하지 않게 한다.
            return IngestOut(job_ref=atch_file_id, chunk_count=0, status="empty")

        if not self.use_real_api:
            # MOCK: 임베딩·pg 없이 파싱/청킹 결과만 리포트 (단독 동작). 검색 가능한 색인이 아니므로
            # "indexed" 와 구분해, 화면·호출자가 실색인으로 오인하지 않게 한다.
            return IngestOut(job_ref=atch_file_id, chunk_count=len(chunks), status="mock-indexed")

        embeddings = await self.embedding.embed_documents([chunk.text for chunk in chunks])
        rows = [
            {
                "workspace_id": workspace_id,
                "user_id": user_id,
                "atch_file_id": atch_file_id,
                "file_sn": file_sn,
                "file_nm": doc_title,
                "page": chunk.page,
                "chunk_idx": chunk.chunk_idx,
                "header_chain": None,
                "source": "html",
                "text": chunk.text,
                "embedding": embedding,
            }
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        await self.repository.ensure_table()
        # 삽입 전 삭제 — 동일 atch_file_id 재인제스트 시 이전 청크가 남아 검색 결과가 중복되는
        # 문제의 멱등 재색인 (#173). insert 뒤 삭제하면 방금 넣은 청크까지 지워질 위험이 있어 순서 고정.
        await self.repository.delete_by_file(atch_file_id, workspace_id)
        await self.repository.insert_chunks(rows)
        return IngestOut(job_ref=atch_file_id, chunk_count=len(rows), status="indexed")

    async def delete_by_file(self, atch_file_id: str, workspace_id: int) -> WorkspaceDeleteOut:
        """파일(첨부 그룹) 단위 청크 회수 — 통합 앱 file 모듈의 파일 삭제에 맞춘 크로스서비스 연쇄.

        MOCK 모드(use_real_api=false)는 색인 자체가 없으므로 no-op(0)로 응답한다. 실모드는 repository 가
        workspace_id 로 스코프하며(fail-closed), atch_file_id 그룹의 청크를 회수한다.
        """
        if not self.use_real_api:
            return WorkspaceDeleteOut(atch_file_id=atch_file_id, deleted_count=0)
        deleted = await self.repository.delete_by_file(atch_file_id, workspace_id)
        return WorkspaceDeleteOut(atch_file_id=atch_file_id, deleted_count=deleted)

    async def search_topic(self, params: TopicSearchIn, workspace_id: int | None) -> TopicSearchOut:
        if not self.use_real_api:
            return mock_topic_out(_WORKSPACE_COLLECTION, params.source, params.top_k)
        if workspace_id is None:  # fail-closed — 어떤 작업 전에도 테넌트 스코프 없으면 거부
            raise UnauthorizedError()
        query_vec = await self.embedding.embed_query(params.query)
        hits = await self.repository.search_dense(workspace_id, query_vec, params.top_k)
        items = [self._to_topic_item(hit) for hit in hits]
        return TopicSearchOut(data=items, total_count=len(items))

    @staticmethod
    def _to_topic_item(hit: dict) -> TopicSearchItem:
        # cosine distance(<=>, 0~2) → 유사도(1 - distance). 챗 근거는 기존 TopicSearchOut 형태 그대로.
        similarity = round(1.0 - float(hit.get("distance") or 0.0), 4)
        return TopicSearchItem(
            score=similarity,
            rerank=None,
            hybrid=similarity,
            dense=similarity,
            doc_sparse_score=0.0,
            meta_sparse_score=0.0,
            source="html",
            file_nm=hit.get("file_nm"),
            header_chain=hit.get("header_chain"),
            text=(hit.get("text") or "")[:_TEXT_PREVIEW_CHARS],
        )
