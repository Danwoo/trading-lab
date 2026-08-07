"""문서 청킹 — 순수함수(IO·부수효과 없음). 파서가 낸 텍스트를 임베딩 단위 청크로 자른다.

전략: 문단(빈 줄) → 문장(문장부호) → 하드컷 순으로 경계를 우선하며 `chunk_size` 를 넘지 않게 채우고,
청크 사이에 `overlap` 만큼의 꼬리 문맥을 겹쳐 검색 시 경계에서 맥락이 끊기지 않게 한다.
(인덱싱 파이프라인 기준 ~1024자 / overlap 150 답습 — design-160 §9-B.)
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

# 문단 경계(빈 줄) / 문장 경계(종결부호·개행) — 한글 종결(다./요.)도 마침표로 포착된다.
_PARAGRAPH_RE = re.compile(r"\n\s*\n")
_SENTENCE_RE = re.compile(r"(?<=[.!?。？！])\s+|\n")


@dataclass
class Chunk:
    text: str
    chunk_idx: int
    page: int | None = None


def _atomic_pieces(text: str, max_len: int) -> list[str]:
    """텍스트를 각 길이 <= max_len 인 원자 조각으로 분해 (문단 → 문장 → 하드컷 순 경계 우선)."""
    pieces: list[str] = []
    for para in _PARAGRAPH_RE.split(text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_len:
            pieces.append(para)
            continue
        for sentence in _SENTENCE_RE.split(para):
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(sentence) <= max_len:
                pieces.append(sentence)
            else:  # 한 문장이 max_len 초과 — 경계 없이 하드컷
                pieces.extend(sentence[i : i + max_len] for i in range(0, len(sentence), max_len))
    return pieces


def _overlap_tail(text: str, overlap: int) -> str:
    """직전 청크의 끝 overlap 자 정도를 단어 경계에 맞춰 잘라 다음 청크의 겹침 문맥으로 쓴다."""
    if overlap <= 0 or not text:
        return ""
    tail = text[-overlap:]
    space = tail.find(" ")
    if space != -1:  # 앞쪽 잘린 단어 조각 제거
        tail = tail[space + 1 :]
    return tail.strip()


def chunk_text(text: str, chunk_size: int = 1024, overlap: int = 150, page: int | None = None) -> list[Chunk]:
    """텍스트 한 덩이를 경계 우선으로 청킹. 빈/공백 입력은 빈 리스트. chunk_idx 는 0-based(이 호출 내 지역)."""
    text = (text or "").strip()
    if not text:
        return []
    overlap = max(0, min(overlap, chunk_size // 2))  # overlap >= chunk_size 로 인한 무한 겹침 방지

    chunks: list[str] = []
    buffer = ""
    for piece in _atomic_pieces(text, chunk_size):
        if buffer and len(buffer) + 1 + len(piece) > chunk_size:
            chunks.append(buffer)
            tail = _overlap_tail(buffer, overlap)
            buffer = f"{tail} {piece}".strip() if tail and len(tail) + 1 + len(piece) <= chunk_size else piece
        else:
            buffer = f"{buffer} {piece}".strip() if buffer else piece
    if buffer:
        chunks.append(buffer)

    return [Chunk(text=c, chunk_idx=i, page=page) for i, c in enumerate(chunks)]


def chunk_pages(pages: Iterable[tuple[int | None, str]], chunk_size: int = 1024, overlap: int = 150) -> list[Chunk]:
    """페이지별 (page_no, text) 를 청킹하고 문서 전역 chunk_idx 를 부여 — 페이지 경계를 넘지 않는다."""
    result: list[Chunk] = []
    for page_no, page_text in pages:
        for local in chunk_text(page_text, chunk_size, overlap, page=page_no):
            result.append(Chunk(text=local.text, chunk_idx=len(result), page=page_no))
    return result
