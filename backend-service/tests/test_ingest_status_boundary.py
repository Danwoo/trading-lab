"""#210 — doc-search 인제스트 응답이 잡행에 저장되기 전에 계약 값으로 좁혀지는지 검증.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_ingest_status_boundary.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

검증 대상 불변식:
- 계약 안 응답은 그대로 저장된다 (좁히기가 정상 경로를 갉아먹지 않는다).
- 계약 밖 응답(모르는 값·타입 오류·키 누락·비-dict)은 어떤 것도 status 로 저장되지 않고 failed 로 낮춰진다.
- 저장된 status 는 항상 GET 응답 스키마(ResearchDocumentOut)를 통과한다 — 이게 #210 의 핵심이다.
  좁히기 전에는 저장이 성공하고 한참 뒤 GET 이 500 으로 터졌다(원인에서 먼 곳에서 나는 실패).
- 업스트림 원문은 error_msg(사용자 노출 필드)에 새지 않는다 — 마스킹된 고정 문구만 저장된다.

외부 의존(repository·file 모듈·doc-search)은 기록용 대역으로 두고 서비스 오케스트레이션만 돌린다.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import get_args

# import 사슬이 core.config(settings)까지 닿는다 — 존재하지 않는 APP_ENV 로 .env 간섭을 끊고
# 필수 설정만 더미로 채운다 (doc-search-mcp-service/tests 와 같은 방식). DB 접속은 하지 않는다.
os.environ["APP_ENV"] = "ingest-boundary-test"
for key, value in {
    "BACKEND_SQL_DB_DRIVER": "postgresql+psycopg",
    "BACKEND_SQL_DB_HOST": "localhost",
    "BACKEND_SQL_DB_PORT": "5432",
    "BACKEND_SQL_DB_NAME": "test",
    "BACKEND_SQL_DB_USER": "test",
    "BACKEND_SQL_DB_PASSWORD": "test",
    "SFTP_HOST": "localhost",
    "SFTP_PORT": "22",
    "SFTP_USERNAME": "test",
    "SFTP_PASSWORD": "test",
    "JWT_SECRET": "test-secret",
}.items():
    os.environ.setdefault(key, value)

_TESTS_DIR = Path(__file__).resolve().parent
_APP_DIR = _TESTS_DIR.parent / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from core.auth_context import set_auth_context  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from schemas.research_document.research_document_schema import (  # noqa: E402
    ResearchDocStatus,
    ResearchDocumentOut,
)
from services.research_document.research_document_service import ResearchDocumentService  # noqa: E402

_WORKSPACE_ID = 7
_RESEARCH_DOC_ID = 42
_UPSTREAM_STATUSES = ("indexed", "mock-indexed", "empty", "failed")


class _RecordingRepository:
    """잡행 쓰기를 기록만 하는 대역 — 무엇이 DB 로 갈 뻔했는지 그대로 붙잡는다."""

    def __init__(self) -> None:
        self.status_updates: list[dict] = []

    def insert_research_document(self, args: dict) -> tuple[int]:
        return (_RESEARCH_DOC_ID,)

    def update_research_document_status(self, args: dict) -> None:
        self.status_updates.append(args)


class _StubFileService:
    async def read_file_content(self, args: dict) -> tuple[bytes, str]:
        return b"research body", "research.txt"


class _StubDocSearchClient:
    """업스트림이 무엇을 내든 그대로 돌려주는 대역 — 계약 밖 응답을 주입하는 자리."""

    def __init__(self, payload) -> None:
        self._payload = payload

    async def ingest(self, **kwargs):
        return self._payload


def _create_with_upstream(payload) -> dict:
    """doc-search 가 payload 를 반환했을 때 잡행에 실제로 쓰인 UPDATE 인자를 돌려준다."""
    set_auth_context(user_id="tester", role="user", workspace_id=_WORKSPACE_ID, email="tester@example.com")
    repository = _RecordingRepository()
    service = ResearchDocumentService(repository, _StubFileService(), _StubDocSearchClient(payload))
    asyncio.run(service.create_research_document({"atch_file_id": "ATCH000001", "file_sn": 0, "doc_title": None}))
    assert len(repository.status_updates) == 1, f"status UPDATE 횟수가 {len(repository.status_updates)} 건"
    return repository.status_updates[0]


def test_contract_statuses_are_stored_as_is() -> str:
    """계약 안 응답은 그대로 저장된다 — 좁히기가 정상 경로를 바꾸지 않는다."""
    for status in _UPSTREAM_STATUSES:
        written = _create_with_upstream({"job_ref": "ATCH000001", "status": status, "chunk_count": 12})
        assert written["status"] == status, f"{status!r} 응답이 {written['status']!r} 로 저장됨"
        assert written["chunk_count"] == 12, f"{status!r} 응답의 chunk_count 가 {written['chunk_count']!r}"
        assert written["error_msg"] is None, f"{status!r} 정상 응답에 error_msg 가 붙음: {written['error_msg']!r}"
    return "test_contract_statuses_are_stored_as_is"


def test_out_of_contract_response_never_reaches_the_row() -> str:
    """계약 밖 응답은 어떤 형태든 status 로 저장되지 않는다 — failed 로 낮춘다."""
    off_contract = [
        {"status": "parsing"},  # 계약에서 뺀 죽은 값 (#211)
        {"status": "PARTIALLY_INDEXED"},  # 업스트림이 새로 늘린 값
        {"status": "Indexed"},  # 대소문자만 다른 값
        {"status": ""},
        {"status": None},
        {"status": 200},
        {"status": ["indexed"]},  # 해시 불가 타입 — 집합 대조였다면 여기서 터진다
        {"status": {"value": "indexed"}},
        {"job_ref": "ATCH000001"},  # status 키 누락
        {},
        [],  # 봉투 자체가 dict 가 아님
        None,
        "indexed",
        {"status": "X" * 2000},  # status 컬럼(String(20))을 넘기는 길이
        {"status": "indexed", "chunk_count": "열두개"},  # status 는 맞고 chunk_count 만 계약 밖
    ]
    for payload in off_contract:
        written = _create_with_upstream(payload)
        assert written["status"] == "failed", f"{payload!r} 응답이 status={written['status']!r} 로 저장됨"
        assert written["chunk_count"] is None, f"{payload!r} 응답인데 chunk_count 가 남음: {written['chunk_count']!r}"
        assert len(written["status"]) <= 20, "status 가 컬럼 길이(String(20))를 넘는다"
    return "test_out_of_contract_response_never_reaches_the_row"


def test_stored_status_always_passes_the_get_response_schema() -> str:
    """#210 의 핵심 — 저장된 값은 언제나 GET 응답 스키마를 통과한다(원인에서 먼 500 이 사라진다)."""
    payloads = [{"status": s, "chunk_count": 3} for s in _UPSTREAM_STATUSES]
    payloads += [{"status": "PARTIALLY_INDEXED"}, {"status": None}, {}, None]
    for payload in payloads:
        written = _create_with_upstream(payload)
        try:
            ResearchDocumentOut(
                research_doc_id=_RESEARCH_DOC_ID,
                workspace_id=_WORKSPACE_ID,
                user_id="tester",
                atch_file_id="ATCH000001",
                status=written["status"],
                chunk_count=written["chunk_count"],
                error_msg=written["error_msg"],
            )
        except ValidationError as exc:
            raise AssertionError(f"{payload!r} 저장 결과가 GET 응답 검증에서 500 을 낸다: {exc}") from exc

    # 좁히기가 없었다면 같은 값이 실제로 응답 검증을 깼다는 대조 — 저장 자체가 문제였음을 보인다.
    assert "PARTIALLY_INDEXED" not in get_args(ResearchDocStatus), "대조 전제가 깨졌다"
    try:
        ResearchDocumentOut(
            research_doc_id=_RESEARCH_DOC_ID,
            workspace_id=_WORKSPACE_ID,
            user_id="tester",
            atch_file_id="ATCH000001",
            status="PARTIALLY_INDEXED",
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("응답 스키마가 계약 밖 status 를 통과시킨다 — 이 테스트의 전제가 무너졌다")
    return "test_stored_status_always_passes_the_get_response_schema"


def test_upstream_payload_does_not_leak_into_error_msg() -> str:
    """원문은 로그로만 — 사용자에게 내려가는 error_msg 에는 마스킹된 고정 문구만 저장된다."""
    secret = "s3cr3t-upstream-detail"
    written = _create_with_upstream({"status": secret, "chunk_count": 5})
    assert written["error_msg"] is not None, "계약 밖 응답인데 error_msg 가 비어 있다 — 실패 이유가 안 남는다"
    assert secret not in written["error_msg"], f"업스트림 원문이 error_msg 로 샜다: {written['error_msg']!r}"
    assert len(written["error_msg"]) <= 1000, "error_msg 가 컬럼 길이(1000)를 넘는다"
    return "test_upstream_payload_does_not_leak_into_error_msg"


def _main() -> int:
    tests = [
        test_contract_statuses_are_stored_as_is,
        test_out_of_contract_response_never_reaches_the_row,
        test_stored_status_always_passes_the_get_response_schema,
        test_upstream_payload_does_not_leak_into_error_msg,
    ]
    passed = 0
    for tc in tests:
        name = tc()
        print(f"PASS {name}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
