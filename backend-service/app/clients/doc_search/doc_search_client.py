"""HTTP client for doc-search-mcp-service 의 내부 인제스트/청크 회수 엔드포인트.

doc-search 의 검색은 MCP tool 표면(챗이 소비)이고, 쓰기(인제스트·삭제)는 서비스 토큰 전용
REST 내부 엔드포인트다(design-160 AD-1 — LLM tool 표면에 쓰기 능력을 두지 않음). 이 클라이언트는
backend-service 오케스트레이터가 그 내부 엔드포인트를 호출하는 프록시로, 서비스 토큰
(create_access_token)·httpx·*_SERVICE_URL config 패턴을 따른다.

테넌트 격리: 서비스 토큰에는 workspace_id 가 없으므로(레포 규약), 대상 테넌트 workspace_id 를 명시
인자로 넘긴다. doc-search 는 이 값으로 청크 메타를 박고/스코프하며, 없으면 fail-closed 로 거부한다.
"""

import httpx
from core.security import create_access_token
from utils.common.retry_utils import is_http_retryable, retry


class DocSearchClient:
    """doc-search-mcp-service 내부 인제스트/삭제 엔드포인트 HTTP 클라이언트."""

    def __init__(self, config, timeout: float = 120.0, connect_timeout: float = 5.0):
        # 인제스트는 파싱·임베딩·색인까지라 느릴 수 있어 read timeout 을 넉넉히 둔다.
        self.base_url = config.DOC_SEARCH_SERVICE_URL.rstrip("/")
        self.timeout = httpx.Timeout(timeout, connect=connect_timeout)

    def _headers(self) -> dict:
        token = create_access_token()
        return {"Authorization": f"Bearer {token}"}

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
    ) -> dict:
        """문서 bytes 를 doc-search 로 보내 파싱·청킹·임베딩·색인시키고 결과(IngestOut)를 반환.

        반환 dict: {job_ref, chunk_count, status(indexed|mock-indexed|empty|failed)}.
        """
        files = {"file": (filename, file_bytes, "application/octet-stream")}
        data = {
            "workspace_id": str(workspace_id),
            "user_id": user_id,
            "atch_file_id": atch_file_id,
            "file_sn": str(file_sn),
            "doc_title": doc_title,
        }

        async def _do() -> httpx.Response:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/doc-search/ingest",
                    files=files,
                    data=data,
                    headers=self._headers(),
                )
            if response.status_code in (502, 503, 504):
                response.raise_for_status()
            return response

        response = await retry(_do, base_delay=0.5, retryable=is_http_retryable)
        response.raise_for_status()
        return response.json()

    async def delete_by_file(self, atch_file_id: str, workspace_id: int) -> None:
        """색인된 청크를 파일(첨부 그룹) 단위로 회수. workspace_id 로 테넌트 스코프(fail-closed)."""

        async def _do() -> httpx.Response:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(
                    f"{self.base_url}/doc-search/ingest/{atch_file_id}",
                    params={"workspace_id": workspace_id},
                    headers=self._headers(),
                )
            if response.status_code in (502, 503, 504):
                response.raise_for_status()
            return response

        response = await retry(_do, base_delay=0.5, retryable=is_http_retryable)
        response.raise_for_status()
