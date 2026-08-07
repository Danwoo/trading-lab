"""워크스페이스(사용자 업로드) 문서 — 검색 MCP tool 1개 + 내부 인제스트 엔드포인트 1개.

- `/topic-workspace` (operation_id 有): MCP tool. 챗이 근거로 쓴다. 출력은 기존 TopicSearchOut 재사용 →
  근거 추출(_extract_doc)·게이팅이 무변경. workspace_id 는 on-behalf JWT 에서 읽어 테넌트 스코프를 강제한다.
- `/ingest`(POST)·`/ingest/{atch_file_id}`(DELETE) (operation_id 無): MCP tool 로 노출하지 않는다(main.py
  route_maps 가 EXCLUDE). 프롬프트 인젝션으로 LLM 이 근거 코퍼스를 쓰기(색인)·지우기(회수)로 오염·훼손하는
  것을 막기 위해 쓰기 경로는 REST 내부(서비스 토큰) 전용으로 둔다(design-160 AD-1).
"""

from core.auth_context import get_workspace_id
from core.container import Container
from core.security import verify_access_token
from core.service_guard import require_service_token
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from schemas.vector_search.vector_search_schema import TopicSearchIn, TopicSearchOut
from schemas.workspace.workspace_schema import IngestOut, WorkspaceDeleteOut
from services.workspace.workspace_service import WorkspaceService
from utils.common.few_shot import few_shot

router = APIRouter(prefix="/doc-search", dependencies=[Depends(verify_access_token)])


@router.post(
    "/topic-workspace",
    operation_id="doc_search_topic_workspace",
    openapi_extra=few_shot([{"질문": "내가 올린 리포트에서 목표주가 근거", "호출": {"query": "목표주가 산정 근거"}}]),
)
@inject
async def topic_search_workspace(
    body: TopicSearchIn,
    workspace_service: WorkspaceService = Depends(Provide[Container.workspace_service]),
) -> TopicSearchOut:
    """내 워크스페이스(사용자 업로드) 문서 텍스트 검색 (pgvector dense 최근접). 사용자가 올린 리포트·문서를 청크로 색인한 개인/워크스페이스 전용 코퍼스에서 관련 청크를 반환한다 — 큐레이션 공용 자료가 아니라 요청자 워크스페이스(workspace_id)로 격리된 자료다. data[].text(청크 본문)·file_nm(원본 파일명, 출처 표시)·header_chain 으로 근거를 제시하라. score 는 cosine 유사도(1 에 가까울수록 관련). 결과가 0건이거나 score 가 낮으면 지어내지 말고 근거 없음을 밝혀라. 수치는 업로드 원문에 근거할 때만 인용한다."""
    return await workspace_service.search_topic(body, get_workspace_id())


@router.post("/ingest", dependencies=[Depends(require_service_token)])
@inject
async def ingest_document(
    file: UploadFile = File(description="원본 문서 파일 (pdf/txt/md)"),
    workspace_id: int = Form(description="테넌트 워크스페이스 ID"),
    user_id: str = Form(description="업로더 사용자 ID"),
    atch_file_id: str = Form(description="통합 앱 file 모듈 첨부 그룹 ID"),
    file_sn: int = Form(description="첨부 그룹 내 파일 순번"),
    doc_title: str = Form(description="원본 파일명 (근거 표시명 = file_nm)"),
    workspace_service: WorkspaceService = Depends(Provide[Container.workspace_service]),
) -> IngestOut:
    """내부 전용 — 문서 bytes 를 받아 파싱·청킹·임베딩 후 pgvector 에 색인.

    require_service_token 게이트로 서비스 토큰(typ=service) 전용 — 유효 JWT 라도 일반 사용자·에이전트는
    403. 서비스 토큰만 도달하므로 workspace_id(Form)는 backend 오케스트레이터가 넘긴 대상 테넌트로 신뢰한다.
    MCP tool 아님(operation_id 없음 + main.py route_maps EXCLUDE). backend 오케스트레이터만 호출한다.
    """
    file_bytes = await file.read()
    return await workspace_service.ingest(
        file_bytes=file_bytes,
        filename=file.filename or doc_title,
        workspace_id=workspace_id,
        user_id=user_id,
        atch_file_id=atch_file_id,
        file_sn=file_sn,
        doc_title=doc_title,
    )


@router.delete("/ingest/{atch_file_id}", dependencies=[Depends(require_service_token)])
@inject
async def delete_ingested_document(
    atch_file_id: str,
    workspace_id: int = Query(
        description="테넌트 워크스페이스 ID (서비스 호출자가 명시 — 서비스 토큰엔 workspace_id 가 없음)"
    ),
    workspace_service: WorkspaceService = Depends(Provide[Container.workspace_service]),
) -> WorkspaceDeleteOut:
    """내부 전용 — 파일(첨부 그룹) 단위로 색인된 청크를 회수. 통합 앱 file 모듈의 파일 삭제와 짝이 되는 연쇄다.

    require_service_token 게이트로 서비스 토큰(typ=service) 전용 — 일반 사용자·에이전트는 403. workspace_id 는
    필수 쿼리 파라미터로 fail-closed(누락 시 422)이며, repository 도 workspace_id 없으면 쿼리를 거부한다(2중).
    MCP tool 아님(operation_id 없음 + main.py route_maps EXCLUDE). backend 오케스트레이터만 호출한다.
    """
    return await workspace_service.delete_by_file(atch_file_id, workspace_id)
