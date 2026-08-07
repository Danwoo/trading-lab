"""#191 — MOCK 인제스트 status 가 실색인과 구분되는지 검증.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_workspace_ingest_status.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

검증 대상 불변식:
- MOCK 모드: 임베딩·pg 를 한 번도 건드리지 않고 status="mock-indexed" (검색 불가를 정직하게 표기).
- 실모드: 청크를 pg 에 쓰고 status="indexed" — 두 값이 섞이지 않는다.
- 텍스트 0건은 여전히 "empty" (기존 구분 회귀 방지).
- 크로스서비스 계약: doc-search 가 낼 수 있는 status 가 backend-service Literal·프론트 라벨 맵에
  전부 있는지 소스 수준으로 대조한다 — 하나라도 빠지면 GET 응답 검증 실패·화면 라벨 공백이 된다.

파서는 실물(OpenSourceParser, .txt 는 오프라인 동작)을 쓰고 외부 의존(임베딩·pg)만 기록용 대역으로 둔다.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path
from typing import get_args

# import 사슬이 core.config(settings)까지 닿는다 — 존재하지 않는 APP_ENV 로 .env 간섭을 끊고
# 비-dev 필수인 JWT_SECRET 만 채운다 (test_workspace_real_api_toggle.py 와 같은 방식).
os.environ["APP_ENV"] = "ingest-status-test"
os.environ.setdefault("JWT_SECRET", "test-secret")

_TESTS_DIR = Path(__file__).resolve().parent
_APP_DIR = _TESTS_DIR.parent / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from clients.parser.parser import OpenSourceParser  # noqa: E402
from schemas.workspace.workspace_schema import IngestOut  # noqa: E402
from services.workspace.workspace_service import WorkspaceService  # noqa: E402

_REPO_ROOT = _TESTS_DIR.parents[1]
_BACKEND_SCHEMA = (
    _REPO_ROOT / "backend-service" / "app" / "schemas" / "research_document" / "research_document_schema.py"
)
_FRONTEND_SCHEMA = _REPO_ROOT / "frontend" / "schemas" / "researchDocument" / "researchDocument.ts"

_SAMPLE_TEXT = ("리서치 문서 본문 예시 문장입니다. " * 200).encode("utf-8")


class _RecordingEmbedding:
    """임베딩 호출을 기록만 하는 대역 — MOCK 경로가 이걸 부르면 테스트가 잡는다."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(f"embed_documents({len(texts)})")
        return [[0.1, 0.2, 0.3] for _ in texts]


class _RecordingRepository:
    """pg 접근을 기록만 하는 대역 — MOCK 경로가 이걸 부르면 테스트가 잡는다."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def ensure_table(self) -> None:
        self.calls.append("ensure_table")

    async def delete_by_file(self, atch_file_id: str, workspace_id: int) -> int:
        self.calls.append(f"delete_by_file({atch_file_id}, {workspace_id})")
        return 0

    async def insert_chunks(self, rows: list[dict]) -> None:
        self.calls.append(f"insert_chunks({len(rows)})")


def _ingest(
    use_real_api: bool, file_bytes: bytes = _SAMPLE_TEXT
) -> tuple[IngestOut, _RecordingRepository, _RecordingEmbedding]:
    repository = _RecordingRepository()
    embedding = _RecordingEmbedding()
    service = WorkspaceService(repository, embedding, OpenSourceParser(), use_real_api=use_real_api)
    result = asyncio.run(
        service.ingest(
            file_bytes=file_bytes,
            filename="research.txt",
            workspace_id=1,
            user_id="tester",
            atch_file_id="ATCH000001",
            file_sn=0,
            doc_title="research.txt",
        )
    )
    return result, repository, embedding


def test_mock_mode_reports_mock_indexed() -> str:
    """MOCK 모드 — pg·임베딩 미접촉인데 'indexed' 로 보고하던 거짓 표기(#191)의 회귀 가드."""
    result, repository, embedding = _ingest(use_real_api=False)
    assert result.status == "mock-indexed", f"MOCK 모드 status 가 {result.status!r} — 실색인과 구분되지 않는다"
    assert result.chunk_count > 0, "청킹 결과가 리포트되지 않음"
    assert repository.calls == [], f"MOCK 인데 pg 접근 발생: {repository.calls}"
    assert embedding.calls == [], f"MOCK 인데 임베딩 호출 발생: {embedding.calls}"
    return "test_mock_mode_reports_mock_indexed"


def test_real_mode_reports_indexed_after_write() -> str:
    """실모드 — 실제로 pg 에 쓴 뒤에만 'indexed'."""
    result, repository, embedding = _ingest(use_real_api=True)
    assert result.status == "indexed", f"실모드 status 가 {result.status!r}"
    assert repository.calls == [
        "ensure_table",
        "delete_by_file(ATCH000001, 1)",
        f"insert_chunks({result.chunk_count})",
    ], f"실모드 pg 쓰기 누락·불일치: {repository.calls}"
    assert embedding.calls == [f"embed_documents({result.chunk_count})"], f"임베딩 호출 불일치: {embedding.calls}"
    return "test_real_mode_reports_indexed_after_write"


def test_empty_document_still_reports_empty() -> str:
    """텍스트 0건 구분은 그대로 — mock-indexed 도입이 empty 를 덮지 않는다."""
    for use_real_api in (False, True):
        result, repository, _ = _ingest(use_real_api=use_real_api, file_bytes=b"   \n  ")
        assert result.status == "empty", f"use_real_api={use_real_api} 에서 status 가 {result.status!r}"
        assert result.chunk_count == 0, "빈 문서인데 청크 수가 0 이 아님"
        assert repository.calls == [], f"빈 문서인데 pg 접근 발생: {repository.calls}"
    return "test_empty_document_still_reports_empty"


def test_status_values_reach_backend_and_frontend() -> str:
    """크로스서비스 드리프트 가드 — doc-search 의 status 가 backend Literal·프론트 라벨 맵에 전부 있나."""
    if not (_BACKEND_SCHEMA.exists() and _FRONTEND_SCHEMA.exists()):
        print("SKIP test_status_values_reach_backend_and_frontend (doc-search 단독 체크아웃 — 소비처 소스 없음)")
        return "test_status_values_reach_backend_and_frontend"

    statuses = get_args(IngestOut.model_fields["status"].annotation)
    assert "mock-indexed" in statuses, "IngestOut 에 mock-indexed 가 없다"

    backend_literal = next(
        line
        for line in _BACKEND_SCHEMA.read_text(encoding="utf-8").splitlines()
        if line.startswith("ResearchDocStatus")
    )
    frontend_source = _FRONTEND_SCHEMA.read_text(encoding="utf-8")
    labels_block = frontend_source.split("RESEARCH_DOCUMENT_STATUS_LABELS", 1)[1].split("};", 1)[0]

    for status in statuses:
        assert f'"{status}"' in backend_literal, f"backend ResearchDocStatus 에 {status} 누락 — GET 응답 검증이 깨진다"
        assert re.search(rf'(?m)^\s*"?{re.escape(status)}"?\s*:', labels_block), (
            f"프론트 라벨 맵에 {status} 누락 — 화면에 원문 코드가 그대로 노출된다"
        )
    return "test_status_values_reach_backend_and_frontend"


def _main() -> int:
    tests = [
        test_mock_mode_reports_mock_indexed,
        test_real_mode_reports_indexed_after_write,
        test_empty_document_still_reports_empty,
        test_status_values_reach_backend_and_frontend,
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
