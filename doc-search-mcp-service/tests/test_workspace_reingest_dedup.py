"""#1 — 동일 atch_file_id 재인제스트 시 청크 중복 방지(삽입 전 삭제, 멱등 재색인).

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_workspace_reingest_dedup.py

검증 대상 불변식:
- 실모드: 같은 atch_file_id 를 두 번 ingest 하면, 두 번째 insert_chunks 전에 delete_by_file 이
  같은 (atch_file_id, workspace_id) 로 호출된다 — pg 에 이전 청크와 새 청크가 함께 남지 않는다.
- 삭제·삽입 순서: delete_by_file 이 insert_chunks 보다 먼저 호출된다 (삽입 후 삭제면 새로 넣은
  청크까지 지워질 위험).
- MOCK 모드: pg 를 전혀 건드리지 않으므로 delete_by_file 도 호출되지 않는다 (기존 계약 불변).
- 텍스트 0건(empty): pg 접근이 아예 없으므로 delete_by_file 도 호출되지 않는다 (기존 계약 불변).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

os.environ["APP_ENV"] = "reingest-dedup-test"
os.environ.setdefault("JWT_SECRET", "test-secret")

_TESTS_DIR = Path(__file__).resolve().parent
_APP_DIR = _TESTS_DIR.parent / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from clients.parser.parser import OpenSourceParser  # noqa: E402
from services.workspace.workspace_service import WorkspaceService  # noqa: E402

_SAMPLE_TEXT = ("리서치 문서 본문 예시 문장입니다. " * 200).encode("utf-8")


class _RecordingEmbedding:
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


class _RecordingRepository:
    """pg 접근 순서를 기록하는 대역 — delete_by_file 호출 여부·순서를 이 기록으로 판정."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def ensure_table(self) -> None:
        self.calls.append("ensure_table")

    async def insert_chunks(self, rows: list[dict]) -> int:
        self.calls.append(f"insert_chunks({len(rows)})")
        return len(rows)

    async def delete_by_file(self, atch_file_id: str, workspace_id: int) -> int:
        self.calls.append(f"delete_by_file({atch_file_id}, {workspace_id})")
        return 0


def _make_service(use_real_api: bool) -> tuple[WorkspaceService, _RecordingRepository]:
    repository = _RecordingRepository()
    service = WorkspaceService(repository, _RecordingEmbedding(), OpenSourceParser(), use_real_api=use_real_api)
    return service, repository


async def _ingest_once(service: WorkspaceService, file_bytes: bytes = _SAMPLE_TEXT):
    return await service.ingest(
        file_bytes=file_bytes,
        filename="research.txt",
        workspace_id=1,
        user_id="tester",
        atch_file_id="ATCH000001",
        file_sn=0,
        doc_title="research.txt",
    )


def test_reingest_deletes_before_insert() -> str:
    """실모드에서 같은 atch_file_id 를 두 번 ingest 하면 매번 delete_by_file 이 insert_chunks 보다 먼저 온다."""
    service, repository = _make_service(use_real_api=True)
    asyncio.run(_ingest_once(service))
    asyncio.run(_ingest_once(service))

    delete_calls = [c for c in repository.calls if c.startswith("delete_by_file")]
    insert_calls = [c for c in repository.calls if c.startswith("insert_chunks")]
    assert len(delete_calls) == 2, f"delete_by_file 호출 횟수 기대 2, 실제 {len(delete_calls)} — {repository.calls}"
    assert len(insert_calls) == 2, f"insert_chunks 호출 횟수 기대 2, 실제 {len(insert_calls)} — {repository.calls}"
    assert all(c == "delete_by_file(ATCH000001, 1)" for c in delete_calls), delete_calls

    # 매 라운드에서 delete 가 insert 보다 앞선다 (삽입 후 삭제 시 새 청크까지 지워질 위험 회귀 가드) —
    # calls 전체에서 각 delete_by_file 위치가 그 다음 insert_chunks 위치보다 앞선지 확인.
    idx = 0
    for _ in range(2):
        d_idx = repository.calls.index("delete_by_file(ATCH000001, 1)", idx)
        i_idx = next(i for i, c in enumerate(repository.calls) if c.startswith("insert_chunks") and i > d_idx)
        assert d_idx < i_idx, f"delete 가 insert 보다 뒤에 옴: {repository.calls}"
        idx = i_idx + 1
    return "test_reingest_deletes_before_insert"


def test_mock_mode_never_calls_delete() -> str:
    """MOCK 모드는 pg 를 전혀 안 건드린다 — delete_by_file 도 호출되면 안 된다 (기존 계약 불변)."""
    service, repository = _make_service(use_real_api=False)
    asyncio.run(_ingest_once(service))
    assert repository.calls == [], f"MOCK 인데 pg 접근 발생: {repository.calls}"
    return "test_mock_mode_never_calls_delete"


def test_empty_document_never_calls_delete() -> str:
    """텍스트 0건은 pg 접근 자체가 없다 — delete_by_file 도 호출되면 안 된다 (기존 계약 불변)."""
    service, repository = _make_service(use_real_api=True)
    asyncio.run(_ingest_once(service, file_bytes=b"   \n  "))
    assert repository.calls == [], f"빈 문서인데 pg 접근 발생: {repository.calls}"
    return "test_empty_document_never_calls_delete"


def _main() -> int:
    tests = [
        test_reingest_deletes_before_insert,
        test_mock_mode_never_calls_delete,
        test_empty_document_never_calls_delete,
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
