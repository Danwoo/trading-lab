"""문서 텍스트 추출 파서 추상화 — 오픈소스(pypdf) 구현 + config 토글 팩토리.

인제스트 파이프라인의 첫 단계. 파일 bytes → `ParsedDoc`(전체 텍스트 + 페이지별 텍스트)로 정규화해
청킹 단계가 파일 포맷을 몰라도 되게 한다. Upstage Document Parse 등 상용 파서는 후속 슬라이스에서
같은 인터페이스로 붙인다(`get_parser` 의 "upstage" 분기).

pypdf 추출은 CPU 블로킹이므로 호출 측(Service)이 `run_in_threadpool` 로 오프로드한다(anti-pattern 13).
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from core.exceptions import RequestEntityTooLargeError, UnsupportedMediaTypeError
from pypdf import PdfReader

_TEXT_EXTENSIONS = {".txt", ".md"}

# 인제스트 추출량 상한 — **파일이 문 앞에서 통과한 뒤에 부풀어 오르는 축**만 여기서 막는다.
# 바이트 크기·파일 개수·위험 확장자는 file 모듈(backend-service)이 업로드 시점에 이미 판정하므로
# (MAX_UPLOAD_SIZE_MB=20MB · MAX_UPLOAD_FILES=100 · DANGEROUS_EXTENSIONS, #106·#144) 여기서 다시
# 재지 않는다 — 같은 축에 상한을 둘로 두면 나중에 갈라진다. 반대로 아래 두 축은 파일 바이트만 보는
# file 모듈이 알 수 없는 것이라 소유자가 여기밖에 없다:
#
# - 텍스트 폭탄: 압축 스트림으로 이뤄진 작은 PDF 가 추출 시 수백 MB 텍스트로 부푸는 경우.
# - 페이지 폭탄: 텍스트는 희박한데 페이지 수만 수십만인 PDF (추출 시간이 페이지 수에 비례).
#
# 값의 유래는 인제스트 1건이 끝나야 하는 시간 예산이다 — backend 오케스트레이터의 doc-search read
# timeout 120초(`backend-service/app/clients/doc_search/doc_search_client.py`).
# 200만 자 ≈ 청크 약 2,290개(chunk_size 1024 / overlap 150 → 청크당 신규 ~874자) ≈ 임베딩 요청
# 약 72건(배치 32) 이라, 요청당 1초로 잡아도 파싱·색인 몫을 남기고 예산 안이다.
# 페이지 상한 2,000쪽은 조밀한 텍스트 페이지(~3,000자)면 문자 상한이 먼저 걸리는 수준의 3배 —
# 즉 정상 문서는 건드리지 않고 "페이지만 많은" 폭탄 모양에만 걸린다.
MAX_EXTRACTED_CHARS = 2_000_000
MAX_PDF_PAGES = 2_000


@dataclass
class ParsedPage:
    page_no: int  # 1-based 페이지 번호 (txt/md 는 1)
    text: str


@dataclass
class ParsedDoc:
    text: str  # 전체 텍스트 (페이지 연결)
    pages: list[ParsedPage] = field(default_factory=list)


def _extension(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


class OpenSourceParser:
    """오픈소스 파서 — .pdf 는 pypdf 로 페이지별, .txt/.md 는 utf-8 단일 페이지. 이미지는 다루지 않는다(텍스트 전용).

    확장자 allowlist 라 아카이브(.zip 등)는 파싱 자체를 하지 않는다 — 압축 해제 경로가 없으므로
    zip-bomb 표면이 없다. PDF 내부 스트림 압축(같은 부류의 팽창)은 아래 추출량 상한이 맡는다.
    """

    def parse(self, file_bytes: bytes, filename: str) -> ParsedDoc:
        ext = _extension(filename)
        if ext == ".pdf":
            return self._parse_pdf(file_bytes)
        if ext in _TEXT_EXTENSIONS:
            return self._parse_text(file_bytes)
        raise UnsupportedMediaTypeError(f"지원하지 않는 파일 형식입니다: {ext or '(확장자 없음)'}")

    def _parse_pdf(self, file_bytes: bytes) -> ParsedDoc:
        reader = PdfReader(io.BytesIO(file_bytes))
        page_count = len(reader.pages)
        if page_count > MAX_PDF_PAGES:
            # 페이지를 한 장도 추출하기 전에 거절 — 추출 비용은 페이지 수에 비례한다.
            raise RequestEntityTooLargeError(
                f"문서 페이지 수가 색인 한도({MAX_PDF_PAGES}쪽)를 초과했습니다: {page_count}쪽"
            )

        pages: list[ParsedPage] = []
        extracted_chars = 0
        for idx, page in enumerate(reader.pages, start=1):
            page_text = (page.extract_text() or "").strip()
            extracted_chars += len(page_text)
            # 페이지마다 누적 검사 — 폭탄이면 문서 끝까지 가지 않고 그 자리에서 멈춘다.
            if extracted_chars > MAX_EXTRACTED_CHARS:
                raise RequestEntityTooLargeError(
                    f"문서에서 추출한 텍스트가 색인 한도({MAX_EXTRACTED_CHARS}자)를 초과했습니다"
                )
            if page_text:
                pages.append(ParsedPage(page_no=idx, text=page_text))
        full_text = "\n\n".join(p.text for p in pages)
        return ParsedDoc(text=full_text, pages=pages)

    def _parse_text(self, file_bytes: bytes) -> ParsedDoc:
        text = file_bytes.decode("utf-8", errors="replace").strip()
        if len(text) > MAX_EXTRACTED_CHARS:
            raise RequestEntityTooLargeError(
                f"문서에서 추출한 텍스트가 색인 한도({MAX_EXTRACTED_CHARS}자)를 초과했습니다: {len(text)}자"
            )
        pages = [ParsedPage(page_no=1, text=text)] if text else []
        return ParsedDoc(text=text, pages=pages)


def get_parser(config):
    """config.DOC_PARSER 로 파서 구현을 고른다 (외부타입 get_* 팩토리 규약).

    - "opensource"(기본): pypdf 기반 OpenSourceParser
    - "upstage": 후속 슬라이스 — 아직 미구현이라 선택 시 기동/사용 지점에서 명확히 실패시킨다.
    """
    parser_kind = config.DOC_PARSER
    if parser_kind == "opensource":
        return OpenSourceParser()
    if parser_kind == "upstage":
        raise NotImplementedError("Upstage 파서는 후속 슬라이스에서 구현됩니다 (DOC_PARSER=opensource 사용).")
    raise ValueError(f"알 수 없는 DOC_PARSER 값입니다: {parser_kind}")
