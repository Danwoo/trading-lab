"""#160 슬라이스 A — 청킹 순수함수(chunk_text/chunk_pages) 경계·불변식 검증.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_chunking.py
pytest 가 도입되면 test_* 함수가 그대로 수집된다.

검증 대상은 순수함수(IO·부수효과 없음)라 env·인프라 없이 단독으로 돈다.
"""

from __future__ import annotations

import sys
from pathlib import Path

# app 소스 루트(utils.ingest 절대 import)를 import 전에 준비한다.
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from utils.ingest.chunking import chunk_pages, chunk_text  # noqa: E402


def test_empty_and_blank_input_yield_no_chunks() -> str:
    """빈/공백 입력은 빈 리스트 — 색인할 청크가 없다."""
    assert chunk_text("") == [], "빈 문자열은 빈 리스트여야 함"
    assert chunk_text("   \n\t  \n  ") == [], "공백만 있는 입력은 빈 리스트여야 함"
    assert chunk_pages([(1, ""), (2, "   ")]) == [], "모든 페이지가 공백이면 빈 리스트여야 함"
    return "test_empty_and_blank_input_yield_no_chunks"


def test_short_input_single_chunk_preserves_page_and_idx() -> str:
    """chunk_size 이하 짧은 입력은 단일 청크 — page·chunk_idx 스탬프가 보존된다."""
    chunks = chunk_text("hello world", chunk_size=1024, overlap=150, page=7)
    assert len(chunks) == 1, f"단일 청크여야 함: {chunks}"
    assert chunks[0].text == "hello world", f"본문 보존: {chunks[0].text!r}"
    assert chunks[0].chunk_idx == 0, f"chunk_idx 0: {chunks[0].chunk_idx}"
    assert chunks[0].page == 7, f"page 스탬프 보존: {chunks[0].page}"
    return "test_short_input_single_chunk_preserves_page_and_idx"


def test_all_chunks_within_size_invariant() -> str:
    """불변식 — 어떤 입력·파라미터에서도 모든 청크 길이가 chunk_size 이하다."""
    cases = [
        ("aaaa. bbbb. cccc. dddd. eeee. ffff. gggg.", 12, 5),  # 문장 경계 다수
        ("x" * 137, 10, 0),  # 경계 없는 하드컷
        ("문단 하나입니다.\n\n다른 문단.\n\n" + ("가" * 60), 25, 8),  # 문단·한글 혼합
        ("word " * 200, 40, 10),  # 공백 다수
    ]
    for text, size, overlap in cases:
        chunks = chunk_text(text, chunk_size=size, overlap=overlap)
        assert chunks, f"청크가 생성돼야 함: size={size}"
        oversized = [c for c in chunks if len(c.text) > size]
        assert not oversized, f"chunk_size({size}) 초과 청크 존재: {[len(c.text) for c in oversized]}"
    return "test_all_chunks_within_size_invariant"


def test_hardcut_lossless_when_no_overlap() -> str:
    """하드컷 무손실 — overlap=0 이면 경계 없는 원문이 청크 이어붙임으로 정확히 복원된다."""
    original = "x" * 25
    chunks = chunk_text(original, chunk_size=10, overlap=0)
    assert len(chunks) == 3, f"25/10 → 3 청크: {[len(c.text) for c in chunks]}"
    assert "".join(c.text for c in chunks) == original, "overlap=0 하드컷은 원문을 무손실 복원해야 함"
    return "test_hardcut_lossless_when_no_overlap"


def test_overlap_ge_size_is_clamped_no_infinite_loop() -> str:
    """overlap >= chunk_size 클램프 — 무한 겹침/루프 없이 종료하고 불변식을 지킨다.

    이 테스트가 종료된다는 사실 자체가 무한루프 부재의 증거다.
    """
    chunks = chunk_text("word " * 100, chunk_size=20, overlap=999)
    assert chunks, "클램프 후에도 청크가 생성돼야 함"
    assert all(len(c.text) <= 20 for c in chunks), "클램프 후에도 chunk_size 이하 불변식 유지"
    return "test_overlap_ge_size_is_clamped_no_infinite_loop"


def test_overlap_tail_shared_between_chunks() -> str:
    """overlap 꼬리 겹침 — 직전 청크의 끝 문맥이 다음 청크 앞에 실제로 겹쳐 들어간다."""
    # 문장 5개(각 "aaaa." 형태, 길이 5). chunk_size=12 → 2문장씩, overlap=5 로 꼬리 문장 1개 겹침.
    chunks = chunk_text("aaaa. bbbb. cccc. dddd. eeee.", chunk_size=12, overlap=5)
    texts = [c.text for c in chunks]
    assert texts == ["aaaa. bbbb.", "bbbb. cccc.", "cccc. dddd.", "dddd. eeee."], f"경계·겹침 불일치: {texts}"
    return "test_overlap_tail_shared_between_chunks"


def test_chunk_pages_global_idx_and_page_stamp() -> str:
    """chunk_pages — 페이지 경계를 넘지 않으면서 문서 전역 chunk_idx 를 0..N 연속 부여하고 page 를 스탬프한다."""
    pages = [
        (1, "aaaa. bbbb. cccc. dddd. eeee."),  # chunk_size=12 → 4 청크 (page 1)
        (2, "short only"),  # 1 청크 (page 2)
        (None, "loose"),  # 1 청크 (page None — 파서가 페이지 정보를 못 준 경우)
    ]
    chunks = chunk_pages(pages, chunk_size=12, overlap=5)
    assert [c.chunk_idx for c in chunks] == list(range(len(chunks))), (
        f"전역 idx 연속이 아님: {[c.chunk_idx for c in chunks]}"
    )
    assert [c.page for c in chunks] == [1, 1, 1, 1, 2, None], f"page 스탬프 불일치: {[c.page for c in chunks]}"
    return "test_chunk_pages_global_idx_and_page_stamp"


def _main() -> int:
    tests = [
        test_empty_and_blank_input_yield_no_chunks,
        test_short_input_single_chunk_preserves_page_and_idx,
        test_all_chunks_within_size_invariant,
        test_hardcut_lossless_when_no_overlap,
        test_overlap_ge_size_is_clamped_no_infinite_loop,
        test_overlap_tail_shared_between_chunks,
        test_chunk_pages_global_idx_and_page_stamp,
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
