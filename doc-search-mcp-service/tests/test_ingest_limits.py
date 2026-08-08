"""#1 — 인제스트 하드닝: 임베딩 서브배치 + 추출량 상한(텍스트·페이지 폭탄) 회귀 그물.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_ingest_limits.py

검증 대상 불변식:
- 임베딩: 청크가 아무리 많아도 요청 1건의 입력 수가 `_EMBED_BATCH_SIZE`(32)를 넘지 않는다.
  경계(32·33)에서 요청 수가 정확히 갈리고, 배치를 넘나들어도 반환 순서는 입력 순서다
  (프로바이더가 data 를 뒤섞어 돌려줘도 index 로 되돌린다). 입력 0건이면 요청 0건.
- 추출량 상한: 페이지 수 > MAX_PDF_PAGES 면 한 장도 추출하기 전에 413,
  누적 추출 문자 > MAX_EXTRACTED_CHARS 면 그 자리에서 413 (.pdf·.txt 양쪽).
- 경계 정리: 아카이브(.zip)는 파싱 대상이 아니라 415 — 압축 해제 경로가 없어 zip-bomb 표면이 없다.
- 서비스 경로: 상한에 걸린 문서는 임베딩·pg 를 한 번도 건드리지 않고 실패한다(비용 발생 전 차단).

PDF 는 외부 생성 도구 없이 이 파일 안에서 최소 구조로 직접 만든다(_make_pdf) — 픽스처 파일을
저장소에 두지 않고도 페이지 수·페이지별 텍스트 길이를 원하는 대로 만들 수 있다.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
from pathlib import Path

os.environ["APP_ENV"] = "ingest-limits-test"
os.environ.setdefault("JWT_SECRET", "test-secret")

_TESTS_DIR = Path(__file__).resolve().parent
_APP_DIR = _TESTS_DIR.parent / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import httpx  # noqa: E402
from clients.embedding.embedding_client import _EMBED_BATCH_SIZE, EmbeddingClient  # noqa: E402
from clients.parser.parser import MAX_EXTRACTED_CHARS, MAX_PDF_PAGES, OpenSourceParser  # noqa: E402
from core.exceptions import RequestEntityTooLargeError, UnsupportedMediaTypeError  # noqa: E402
from services.workspace.workspace_service import WorkspaceService  # noqa: E402


class _Config:
    OPENAI_EMBEDDING_URL = "http://embedding.invalid/v1"
    OPENAI_EMBEDDING_MODEL_NAME = "BAAI/bge-m3"
    OPENAI_EMBEDDING_API_KEY = "EMPTY"


def _make_client(shuffle: bool = False) -> tuple[EmbeddingClient, list[list[str]]]:
    """MockTransport 로 임베딩 서버를 대신하는 클라이언트 — 요청마다 받은 input 목록을 기록한다.

    shuffle=True 면 OpenAI 호환 응답의 data 순서 무보장을 재현해 역순으로 돌려준다.
    """
    seen: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        texts = payload["input"]
        seen.append(list(texts))
        # 임베딩 값에 입력 텍스트의 길이를 심어 두어, 반환 순서가 입력 순서인지 값으로 판정한다.
        data = [{"index": i, "embedding": [float(len(t))]} for i, t in enumerate(texts)]
        if shuffle:
            data.reverse()
        return httpx.Response(200, json={"data": data})

    client = EmbeddingClient(_Config())
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client, seen


def _make_pdf(page_texts: list[str]) -> bytes:
    """최소 구조 PDF 생성 — 페이지마다 텍스트 하나를 그리는 content stream 을 둔다(ASCII 전용)."""
    objects: list[bytes] = []
    page_ids = [4 + 2 * i for i in range(len(page_texts))]
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = b" ".join(b"%d 0 R" % pid for pid in page_ids)
    objects.append(b"<< /Type /Pages /Kids [" + kids + b"] /Count %d >>" % len(page_texts))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, text in enumerate(page_texts):
        contents_id = page_ids[i] + 1
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>" % contents_id
        )
        stream = b"BT /F1 12 Tf 72 720 Td (" + text.encode("ascii") + b") Tj ET"
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets: list[int] = []
    for idx, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % idx + body + b"\nendobj\n")
    xref_offset = out.tell()
    out.write(b"xref\n0 %d\n" % (len(objects) + 1))
    out.write(b"0000000000 65535 f \n")
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref_offset))
    return out.getvalue()


# ── 임베딩 서브배치 ──────────────────────────────────────────────────────────


def test_embed_documents_splits_into_batches() -> str:
    """청크 100개는 요청 4건(32·32·32·4)으로 나뉜다 — 어떤 요청도 상한을 넘지 않는다."""
    client, seen = _make_client()
    texts = [f"chunk-{i}" for i in range(100)]
    asyncio.run(client.embed_documents(texts))

    sizes = [len(batch) for batch in seen]
    assert sizes == [32, 32, 32, 4], f"배치 크기 기대 [32,32,32,4], 실제 {sizes}"
    assert all(size <= _EMBED_BATCH_SIZE for size in sizes), sizes
    # 나눠 보내도 전체 입력이 빠짐없이 정확히 한 번씩 실린다.
    assert [t for batch in seen for t in batch] == texts, "배치 분할에서 입력이 유실·중복됐다"
    return "test_embed_documents_splits_into_batches"


def test_embed_documents_batch_boundary() -> str:
    """경계: 정확히 32개는 요청 1건, 33개는 2건(32+1)."""
    client, seen = _make_client()
    asyncio.run(client.embed_documents([f"c{i}" for i in range(_EMBED_BATCH_SIZE)]))
    assert [len(b) for b in seen] == [_EMBED_BATCH_SIZE], seen

    client, seen = _make_client()
    asyncio.run(client.embed_documents([f"c{i}" for i in range(_EMBED_BATCH_SIZE + 1)]))
    assert [len(b) for b in seen] == [_EMBED_BATCH_SIZE, 1], [len(b) for b in seen]
    return "test_embed_documents_batch_boundary"


def test_embed_documents_preserves_order_across_batches() -> str:
    """프로바이더가 data 를 뒤섞어 돌려줘도 반환은 입력 순서 — 배치 경계를 넘어도 어긋나지 않는다.

    각 청크 길이를 서로 다르게 만들고 임베딩 값에 그 길이를 심어, 순서가 밀리면 값이 어긋난다.
    """
    client, seen = _make_client(shuffle=True)
    texts = ["x" * (i + 1) for i in range(70)]  # 길이 1..70 (배치 3건에 걸침)
    embeddings = asyncio.run(client.embed_documents(texts))

    assert len(seen) == 3, f"요청 수 기대 3, 실제 {len(seen)}"
    assert len(embeddings) == len(texts), f"임베딩 수 {len(embeddings)} != 입력 수 {len(texts)}"
    got = [vec[0] for vec in embeddings]
    expected = [float(len(t)) for t in texts]
    assert got == expected, f"순서 어긋남 — 앞 5개 기대 {expected[:5]}, 실제 {got[:5]}"
    return "test_embed_documents_preserves_order_across_batches"


def test_embed_documents_empty_makes_no_request() -> str:
    """입력 0건은 요청 0건 (기존 계약 불변 — 빈 문서로 임베딩 서버를 두드리지 않는다)."""
    client, seen = _make_client()
    result = asyncio.run(client.embed_documents([]))
    assert result == [], result
    assert seen == [], f"입력 0건인데 요청 발생: {seen}"
    return "test_embed_documents_empty_makes_no_request"


# ── 추출량 상한 (텍스트 폭탄 · 페이지 폭탄) ──────────────────────────────────


def test_pdf_page_bomb_rejected() -> str:
    """페이지 수가 상한을 넘으면 413 — 텍스트를 한 장도 추출하지 않는다."""
    parser = OpenSourceParser()
    over = _make_pdf(["p"] * (MAX_PDF_PAGES + 1))
    try:
        parser.parse(over, "bomb.pdf")
    except RequestEntityTooLargeError as exc:
        assert str(MAX_PDF_PAGES) in str(exc), str(exc)
    else:
        raise AssertionError(f"페이지 {MAX_PDF_PAGES + 1}쪽인데 통과했다")
    return "test_pdf_page_bomb_rejected"


def test_pdf_at_page_limit_passes() -> str:
    """경계: 정확히 상한 쪽수는 통과한다 (정상 문서를 오탐 거절하지 않는다)."""
    parser = OpenSourceParser()
    parsed = parser.parse(_make_pdf(["page text"] * MAX_PDF_PAGES), "big.pdf")
    assert len(parsed.pages) == MAX_PDF_PAGES, len(parsed.pages)
    return "test_pdf_at_page_limit_passes"


def test_pdf_text_bomb_rejected() -> str:
    """페이지 수는 적어도 추출 텍스트 누적이 상한을 넘으면 413 (압축 스트림 팽창 방어)."""
    parser = OpenSourceParser()
    per_page = MAX_EXTRACTED_CHARS // 4
    bomb = _make_pdf(["A" * per_page] * 5)  # 총 ~1.25배
    try:
        parser.parse(bomb, "bomb.pdf")
    except RequestEntityTooLargeError as exc:
        assert str(MAX_EXTRACTED_CHARS) in str(exc), str(exc)
    else:
        raise AssertionError("추출 텍스트가 상한을 넘었는데 통과했다")
    return "test_pdf_text_bomb_rejected"


def test_text_file_bomb_rejected() -> str:
    """.txt 도 같은 상한 — 상한+1자는 413, 상한 정확히는 통과."""
    parser = OpenSourceParser()
    try:
        parser.parse(b"A" * (MAX_EXTRACTED_CHARS + 1), "bomb.txt")
    except RequestEntityTooLargeError as exc:
        assert str(MAX_EXTRACTED_CHARS) in str(exc), str(exc)
    else:
        raise AssertionError("상한 초과 .txt 가 통과했다")

    parsed = parser.parse(b"A" * MAX_EXTRACTED_CHARS, "ok.txt")
    assert len(parsed.text) == MAX_EXTRACTED_CHARS, len(parsed.text)
    return "test_text_file_bomb_rejected"


def test_archive_is_not_parsed() -> str:
    """아카이브는 파싱 대상이 아니다 — 415 로 끝나므로 압축 해제(zip-bomb) 표면이 없다."""
    parser = OpenSourceParser()
    # PK 시그니처로 시작하는 진짜 zip 컨테이너(빈 아카이브)를 준다 — 확장자만 바꾼 게 아니다.
    empty_zip = b"PK\x05\x06" + b"\x00" * 18
    for filename in ("payload.zip", "payload.gz", "payload.tar"):
        try:
            parser.parse(empty_zip, filename)
        except UnsupportedMediaTypeError:
            continue
        raise AssertionError(f"{filename} 이 파싱 경로에 들어갔다")
    return "test_archive_is_not_parsed"


# ── 서비스 경로 (비용 발생 전 차단) ──────────────────────────────────────────


class _RecordingEmbedding:
    def __init__(self) -> None:
        self.calls: list[int] = []

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(len(texts))
        return [[0.1] for _ in texts]


class _RecordingRepository:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def ensure_table(self) -> None:
        self.calls.append("ensure_table")

    async def insert_chunks(self, rows: list[dict]) -> int:
        self.calls.append(f"insert_chunks({len(rows)})")
        return len(rows)

    async def delete_by_file(self, atch_file_id: str, workspace_id: int) -> int:
        self.calls.append("delete_by_file")
        return 0


def test_oversized_document_never_reaches_embedding_or_pg() -> str:
    """상한 초과 문서는 임베딩·pg 를 한 번도 건드리지 않고 413 으로 끝난다(비용 발생 전 차단)."""
    embedding, repository = _RecordingEmbedding(), _RecordingRepository()
    service = WorkspaceService(repository, embedding, OpenSourceParser(), use_real_api=True)
    try:
        asyncio.run(
            service.ingest(
                file_bytes=b"A" * (MAX_EXTRACTED_CHARS + 1),
                filename="bomb.txt",
                workspace_id=1,
                user_id="tester",
                atch_file_id="ATCH000009",
                file_sn=0,
                doc_title="bomb.txt",
            )
        )
    except RequestEntityTooLargeError:
        pass
    else:
        raise AssertionError("상한 초과 문서가 인제스트를 통과했다")

    assert embedding.calls == [], f"임베딩 호출 발생: {embedding.calls}"
    assert repository.calls == [], f"pg 접근 발생: {repository.calls}"
    return "test_oversized_document_never_reaches_embedding_or_pg"


def test_normal_document_still_indexes() -> str:
    """정상 크기 문서는 그대로 색인된다 — 상한이 정상 경로를 막지 않는다(오탐 가드)."""
    embedding, repository = _RecordingEmbedding(), _RecordingRepository()
    service = WorkspaceService(repository, embedding, OpenSourceParser(), use_real_api=True)
    result = asyncio.run(
        service.ingest(
            file_bytes=("리서치 문서 본문 예시 문장입니다. " * 500).encode("utf-8"),
            filename="research.txt",
            workspace_id=1,
            user_id="tester",
            atch_file_id="ATCH000010",
            file_sn=0,
            doc_title="research.txt",
        )
    )
    assert result.status == "indexed", result
    assert result.chunk_count > 0, result
    assert any(call.startswith("insert_chunks") for call in repository.calls), repository.calls
    return "test_normal_document_still_indexes"


def _main() -> int:
    tests = [
        test_embed_documents_splits_into_batches,
        test_embed_documents_batch_boundary,
        test_embed_documents_preserves_order_across_batches,
        test_embed_documents_empty_makes_no_request,
        test_pdf_page_bomb_rejected,
        test_pdf_at_page_limit_passes,
        test_pdf_text_bomb_rejected,
        test_text_file_bomb_rejected,
        test_archive_is_not_parsed,
        test_oversized_document_never_reaches_embedding_or_pg,
        test_normal_document_still_indexes,
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
