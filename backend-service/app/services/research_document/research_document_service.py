"""리서치 문서 업로드→인덱싱 오케스트레이션.

흐름(POST): 잡행 INSERT(status=uploaded) → file 모듈에서 실물 bytes 조회 → doc-search 인제스트
호출 → 결과 status(indexed|mock-indexed|empty|failed)·chunk_count 로 잡행 UPDATE → 생성된 research_doc_id 반환
(create 컨벤션 CreateOut(data={pk}) — 클라이언트는 이후 GET/{id} 로 status·chunk_count 를 조회한다).
인제스트가 실패하면 잡행을 failed 로 남기고(민감정보 마스킹) 도메인 예외(502)로 올린다.
doc-search 응답은 신뢰 경계 밖이라 잡행에 쓰기 전 IngestResultIn 으로 좁힌다 — 계약 밖 응답은
failed 로 낮추고 원문은 로그에만 남긴다(그대로 저장하면 뒤이은 GET 이 응답 스키마 검증에서 500).

DELETE: doc-search 청크 회수 → file 모듈 파일 삭제 → 잡행 삭제 순. 외부 삭제가 먼저라 하나라도
실패하면 잡행이 남아 재시도 가능(부분실패 안전 — 예외는 자연 전파해 exception_handler 가 매핑).

테넌트 격리: 모든 경로가 require_workspace_id() 로 스코프하고, 인제스트/삭제도 그 workspace_id 를
doc-search 로 넘겨 양쪽에서 fail-closed.
"""

from core.auth_context import get_email, get_user_id, require_workspace_id
from core.exceptions import BadGatewayError, HTTPError, NotFoundError
from core.logger import logger
from pydantic import ValidationError
from schemas.research_document.research_document_schema import IngestResultIn

# 잡 상태 전이는 사용자 편집이 아니라 인제스트 파이프라인이 유발하는 시스템 이벤트다 (감사컬럼 규약 룰5).
_SYSTEM_ACTOR = "system"
# 업스트림 응답 원문은 사용자에게 노출하지 않는다 (error_msg 마스킹 — 상세는 로그로).
_UNEXPECTED_RESULT_MSG = "ingest_failed:UnexpectedResult"


class ResearchDocumentService:
    def __init__(self, research_document_repository, file_service, doc_search_client):
        self.repository = research_document_repository
        self.file_service = file_service
        self.doc_search_client = doc_search_client

    def select_research_document_list(self, args: dict) -> tuple[list, int]:
        args["workspace_id"] = require_workspace_id()
        return self.repository.select_research_document_list(args)

    def select_research_document(self, args: dict) -> dict:
        args["workspace_id"] = require_workspace_id()
        document = self.repository.select_research_document(args)
        if not document:
            raise NotFoundError("데이터를 찾을 수 없습니다.")
        return document

    async def create_research_document(self, args: dict) -> int:
        workspace_id = require_workspace_id()

        # 1) 잡행 INSERT (status=uploaded) — 이후 단계의 진행 상태를 이 행에 남긴다.
        insert_args = {
            "workspace_id": workspace_id,
            "user_id": get_user_id(),
            "atch_file_id": args["atch_file_id"],
            "file_sn": args["file_sn"],
            "doc_title": args.get("doc_title"),
            "status": "uploaded",
            "reg_id": get_email(),
        }
        keys = self.repository.insert_research_document(insert_args)
        research_doc_id = keys[0]

        # 2) file 모듈에서 실물 bytes 조회 (잘못된 참조면 자연 전파 → 404, 잡행은 uploaded 로 남아 정직).
        file_args = {"atch_file_id": args["atch_file_id"], "file_sn": args["file_sn"]}
        file_bytes, orignl_file_nm = await self.file_service.read_file_content(file_args)
        doc_title = args.get("doc_title") or orignl_file_nm

        # 3) doc-search 인제스트 (파싱·청킹·임베딩·색인). 업스트림 실패는 잡행을 failed 로 남기고 502.
        try:
            result = await self.doc_search_client.ingest(
                file_bytes=file_bytes,
                filename=orignl_file_nm,
                workspace_id=workspace_id,
                user_id=get_user_id(),
                atch_file_id=args["atch_file_id"],
                file_sn=args["file_sn"],
                doc_title=doc_title,
            )
        except Exception as exc:
            # 전체 상세는 내부 로그로만, 잡행 error_msg 는 마스킹(예외 유형만 — 메시지 본문 미저장)
            logger.error("리서치 문서 인제스트 실패 research_doc_id=%s: %r", research_doc_id, exc)
            self._apply_status(
                research_doc_id,
                workspace_id,
                status="failed",
                chunk_count=None,
                error_msg=f"ingest_failed:{type(exc).__name__}",
            )
            raise BadGatewayError("문서 인덱싱 처리에 실패했습니다.") from exc

        # 4) 결과 status(indexed|mock-indexed|empty|failed)·chunk_count 로 잡행 UPDATE.
        #    업스트림 응답은 신뢰 경계 밖이라 잡행에 쓰기 전에 계약 값으로 좁힌다.
        try:
            ingest = IngestResultIn.model_validate(result)
        except ValidationError as exc:
            # 원문은 로그로만 — 상태를 못 믿으면 그 상태가 딸고 온 청크 수도 못 믿으므로 함께 버린다.
            # 계약 밖 응답은 크기도 계약 밖이라(에러 페이지 등) 로그 한 줄이 부풀지 않게 잘라 남긴다.
            logger.error(
                "doc-search 인제스트 응답이 계약 밖 research_doc_id=%s payload=%.500r 오류=%.500s",
                research_doc_id,
                result,
                exc,
            )
            self._apply_status(
                research_doc_id, workspace_id, status="failed", chunk_count=None, error_msg=_UNEXPECTED_RESULT_MSG
            )
        else:
            self._apply_status(
                research_doc_id,
                workspace_id,
                status=ingest.status,
                chunk_count=ingest.chunk_count,
                error_msg=None,
            )

        return research_doc_id

    async def delete_research_document(self, args: dict) -> None:
        workspace_id = require_workspace_id()
        args["workspace_id"] = workspace_id
        document = self.repository.select_research_document(args)
        if not document:
            raise NotFoundError("데이터를 찾을 수 없습니다.")

        # 외부 리소스를 먼저 회수하고 잡행은 마지막에 삭제한다 — 외부 삭제가 실패하면 예외가 전파돼
        # 잡행이 남으므로 재시도 가능(부분실패 안전). doc-search·file 삭제는 멱등에 가깝다.
        #
        # **상류 실패를 도메인 예외로 바꾼다** (#441 B-24). `delete_by_file` 의 `raise_for_status()`
        # 가 던지는 `httpx.HTTPStatusError` 는 도메인 예외가 아니라, 일반 핸들러가 「서버 내부
        # 오류가 발생했습니다」 500 으로 뭉갠다 — 화면은 거기서 「잠시 후 다시 시도」로 떨어지는데
        # 상류가 죽어 있으면 **다시 해도 안 된다**(실측: 세 번 다 500, 행은 그대로). 적재 경로는
        # 이미 같은 자리를 `BadGatewayError` 로 바꾸고 있다 — 삭제 경로에만 그 층이 없었다.
        try:
            await self.doc_search_client.delete_by_file(document["atch_file_id"], workspace_id)
        except HTTPError:
            raise  # 우리가 만든 예외는 이미 한국어이고 다음 행동을 담고 있다
        except Exception as exc:
            logger.error("리서치 문서 색인 회수 실패 research_doc_id=%s: %r", args.get("research_doc_id"), exc)
            raise BadGatewayError(
                "문서 색인을 회수하지 못해 삭제를 멈췄습니다 — 문서는 그대로 남아 있습니다. "
                "검색 서비스가 응답하면 다시 지울 수 있습니다."
            ) from exc

        try:
            await self.file_service.delete_file_detail(
                {"atch_file_id": document["atch_file_id"], "file_sn": document["file_sn"]}
            )
        except HTTPError:
            raise
        except Exception as exc:
            logger.error("리서치 문서 파일 회수 실패 research_doc_id=%s: %r", args.get("research_doc_id"), exc)
            raise BadGatewayError(
                "문서 파일을 회수하지 못해 삭제를 멈췄습니다 — 문서는 그대로 남아 있습니다. "
                "파일 저장소가 응답하면 다시 지울 수 있습니다."
            ) from exc
        self.repository.delete_research_document(args)

    def _apply_status(
        self, research_doc_id: int, workspace_id: int, *, status: str, chunk_count: int | None, error_msg: str | None
    ) -> None:
        self.repository.update_research_document_status(
            {
                "research_doc_id": research_doc_id,
                "workspace_id": workspace_id,
                "status": status,
                "chunk_count": chunk_count,
                "error_msg": error_msg,
                "mod_id": _SYSTEM_ACTOR,
            }
        )
