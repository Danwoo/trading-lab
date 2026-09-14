"""#441 (B-24) — 문서 삭제가 실패할 때 화면이 무엇을 말하는지.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행형으로 쓴다:
    uv run python tests/test_document_delete_speaks.py

실측(Cycle 7): 문서 삭제가 세 번 모두 500 이고 행은 그대로 남았다.

    $ curl -X DELETE .../research-document/14
    {"detail":"서버 내부 오류가 발생했습니다."}   HTTP:500
    화면: 「서버에서 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.」

**「잠시 후 다시 시도」는 틀린 처방이다** — 상류가 죽어 있으면 다시 해도 안 된다(실제로 세 번
다 안 됐다). 뿌리는 `doc_search_client.delete_by_file` 의 `raise_for_status()` 가 던지는
`httpx.HTTPStatusError` 가 도메인 예외가 아니라서, 일반 핸들러가 500 으로 뭉개는 것이다.

같은 서비스의 **적재 경로는 이미 옳게 하고 있다** — `except Exception` 으로 받아
`BadGatewayError("문서 인덱싱 처리에 실패했습니다.")` 로 바꾼다. 삭제 경로에만 그 층이 없었다.

여기서 보는 것은 셋이다:
  (1) 상류가 실패하면 **502 계열 도메인 예외**가 나온다 — 일반 500 이 아니다.
  (2) 사유가 **어느 단계에서 막혔는지**를 말한다 — 「잠시 후 다시 시도」로 끝내지 않는다.
  (3) 그래도 **잡행은 남는다** — 부분실패 안전(이 파일의 기존 설계)이 안 깨졌다.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "app"))


def _seed_env_from_example() -> int:
    """`app/.env.example` 로 필수 환경변수를 채운다 — import 전에 불러야 한다 (워크트리·CI 엔 .env 가 없다)."""
    os.environ.setdefault("APP_ENV", "development")
    example = BACKEND / "app/.env.example"
    assert example.is_file(), f"{example} 가 없다 — 이 테스트의 전제가 사라졌다"
    seeded = 0
    for line in example.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")
            seeded += 1
    assert seeded > 0, ".env.example 에서 채운 키가 0건이다 — 형식이 바뀌었다면 이 그물을 고쳐라"
    return seeded


_SEEDED = _seed_env_from_example()

import httpx  # noqa: E402
from core.auth_context import set_auth_context  # noqa: E402
from core.exceptions import BadGatewayError, HTTPError  # noqa: E402
from services.research_document.research_document_service import ResearchDocumentService  # noqa: E402

WORKSPACE_ID = 7
DOC = {"research_doc_id": 14, "atch_file_id": "AF-1", "file_sn": 1, "doc_title": "c7b-C"}

CHECKED = 0
FAILURES: list[str] = []


def check(name: str, actual, expected) -> None:
    global CHECKED
    CHECKED += 1
    if actual != expected:
        FAILURES.append(f"{name}: 기대 {expected!r} · 실제 {actual!r}")


class FakeRepository:
    def __init__(self) -> None:
        self.deleted: list[dict] = []

    def select_research_document(self, args: dict) -> dict | None:
        return dict(DOC)

    def delete_research_document(self, args: dict) -> None:
        self.deleted.append(dict(args))


class DeadDocSearch:
    """상류가 죽어 있다 — `raise_for_status()` 가 던지는 것과 같은 예외."""

    async def delete_by_file(self, atch_file_id: str, workspace_id: int) -> None:
        request = httpx.Request("DELETE", "http://doc-search.test/doc-search/ingest/AF-1")
        raise httpx.HTTPStatusError("boom", request=request, response=httpx.Response(503, request=request))


class OkDocSearch:
    async def delete_by_file(self, atch_file_id: str, workspace_id: int) -> None:
        return None


class FakeFileService:
    def __init__(self) -> None:
        self.calls = 0

    async def delete_file_detail(self, args: dict) -> None:
        self.calls += 1


def _service(doc_search) -> tuple[ResearchDocumentService, FakeRepository, FakeFileService]:
    set_auth_context(user_id="u", email="u@x", role="operator", workspace_id=WORKSPACE_ID)
    repo, files = FakeRepository(), FakeFileService()
    service = ResearchDocumentService(
        research_document_repository=repo, file_service=files, doc_search_client=doc_search
    )
    return service, repo, files


def main() -> int:
    # ── 상류가 죽었을 때 ────────────────────────────────────────
    service, repo, _ = _service(DeadDocSearch())
    raised: BaseException | None = None
    try:
        asyncio.run(service.delete_research_document({"research_doc_id": 14}))
    except BaseException as exc:  # noqa: BLE001 — 무엇이 나왔는지가 판정 대상이다
        raised = exc

    check("도메인 예외가 나온다 (일반 500 아님)", isinstance(raised, HTTPError), True)
    check("상류 실패는 502 계열이다", isinstance(raised, BadGatewayError), True)
    message = str(raised or "")
    check("사유가 어느 단계인지 말한다", "색인" in message or "검색" in message, True)
    check("「잠시 후 다시 시도」로 끝내지 않는다", "잠시 후" in message, False)
    check("잡행은 남는다 (부분실패 안전)", repo.deleted, [])

    # ── 정상 경로는 종전대로 ────────────────────────────────────
    service, repo, files = _service(OkDocSearch())
    asyncio.run(service.delete_research_document({"research_doc_id": 14}))
    check("정상 경로는 파일도 지운다", files.calls, 1)
    check("정상 경로는 잡행도 지운다", len(repo.deleted), 1)

    for line in FAILURES:
        print(f"FAIL {line}")
    print(f"\n검사한 단언 {CHECKED}건 중 {CHECKED - len(FAILURES)}건 통과")
    print("판정: 삭제 실패가 사유를 말하고, 부분실패 안전은 그대로다")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
