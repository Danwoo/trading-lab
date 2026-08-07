"""ai-chatbot 프론트 호환 SSE 이벤트 빌더 (순수함수).

ai-chatbot 프론트는 newline-delimited JSON(`json.dumps(ev)+"\\n"`, data: prefix 없음)을 파싱하며
type 별 z.union 멤버를 케이스 민감하게 맞춰야 한다. 이 모듈은 그 dict 만 생성한다 (IO 없음).
stream_query_example_ai 가 내부 Plan-Execute 이벤트를 이 빌더들로 변환해 흘린다.

이벤트 순서:
    start → step(routing) → routing → (tool_parameters) → step(tools) → media
    → step(response) → response_chunk×N → title → follow_up_question → workflow_complete
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Any


def start_event(query: str, message: str = "요청을 처리하고 있습니다...") -> dict:
    return {"type": "start", "message": message, "query": query}


def step_event(step: str, message: str, tools: list[str] | None = None) -> dict:
    payload: dict[str, Any] = {"type": "step", "step": step, "message": message}
    if tools is not None:
        payload["tools"] = tools
    return payload


def routing_event(
    selected_tools: list[str],
    tool_info: list[dict[str, str]],
    *,
    is_fiber_related: bool = True,
) -> dict:
    return {
        "type": "routing",
        "is_fiber_related": is_fiber_related,
        "selected_tools": selected_tools,
        "tool_info": tool_info,
    }


def tool_parameters_event(message: str, tools_with_keywords: list[dict[str, str]]) -> dict:
    return {
        "type": "tool_parameters",
        "message": message,
        "tools_with_keywords": tools_with_keywords,
    }


def media_event(
    images: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    tool_results_summary: dict[str, Any],
) -> dict:
    return {
        "type": "media",
        "images": images,
        "sources": sources,
        "tool_results_summary": tool_results_summary,
    }


def response_chunk_event(content: str, chunk_id: int, accumulated_length: int) -> dict:
    return {
        "type": "response_chunk",
        "content": content,
        "chunk_id": chunk_id,
        "accumulated_length": accumulated_length,
    }


def title_event(content: str) -> dict:
    return {"type": "title", "content": content}


def follow_up_question_event(content: str) -> dict:
    """content 는 후속질문 list 의 JSON 문자열 (예: '["q1","q2","q3"]')."""
    return {"type": "follow_up_question", "content": content}


def workflow_complete_event(message: str = "완료되었습니다.") -> dict:
    return {"type": "workflow_complete", "message": message}


def error_event(message: str) -> dict:
    return {"type": "error", "message": message}


# ─────────────────────────────────────────────────────────
# media 추출 — tool_calls(trace) 의 stringified output 에서 sources/images 파싱
# ─────────────────────────────────────────────────────────


def _try_json(text: str) -> Any:
    """tool output 문자열을 JSON 으로 파싱. 잘린 output(저장 한도 초과)은 마지막 완전 객체까지 복구 시도."""
    text = text.strip()
    if not text or text[0] not in "{[":
        return None
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    # 잘린 tool output 복구 — 마지막 완전한 객체(`},`)까지 살리고 배열·객체를 닫는다.
    cut = text.rfind("},")
    if cut <= 0:
        return None
    head = text[: cut + 1]
    for tail in ("]}", "}]}", "]", "}", "]}}"):
        try:
            return json.loads(head + tail)
        except (ValueError, TypeError):
            continue
    return None


def _domain_of(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url or "")
    return m.group(1) if m else ""


def _clean(s: Any) -> str:
    """HTML 엔티티·태그 제거(뉴스/공시 본문의 <span>·&lt;br&gt; 등) + 공백 정리."""
    text = html.unescape(str(s))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _mk_source(*, title: str, url: str, kind: str, content: str, tool: str) -> dict:
    """프론트 sources 스키마. kind=출처 유형(web 은 도메인, 그 외 'DART 공시'·'시세' 등 라벨)."""
    return {
        "title": _clean(title)[:200],
        "tool": tool,
        "url": url,
        "domain": kind,
        "content": _clean(content)[:500],
        "thumbnail": "",
        "favicon": "",
    }


# ─────────────────────────────────────────────────────────
# 출처 url 패턴 — example-ai-agent backend(tools/configs/*_config.py)의 공식 패턴을 포팅.
# tool_name → {id 필드, title 필드, content 필드, url 템플릿, 출처유형, favicon}.
# url 은 공식 직링크만 (추측 금지). 내 MCP tool 이름·output 필드에 맞춰 매핑.
# 새 소스 추가 = 여기에 한 줄 등록.
# ─────────────────────────────────────────────────────────

# DART 공시뷰어(접수번호 rcept_no 직링크), 시장 시세 벤더 페이지, 뉴스 기사 URL 패턴.
# mock 데이터의 식별자(접수번호·티커)로 공개 직링크를 구성 (추측 금지 — 공식 endpoint 만).
_DART_VIEWER = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={id}"
_DART_COMPANY = "https://dart.fss.or.kr/dsab007/main.do?textCrpNm={id}"
_MARKET_VENDOR = "https://finance.naver.com/item/main.naver?code={id}"
_MARKET_INDEX = "https://finance.naver.com/sise/sise_index.naver?code={id}"
_DART_FAVICON = "https://dart.fss.or.kr/favicon.ico"
_MARKET_FAVICON = "https://www.google.com/s2/favicons?domain=finance.naver.com&sz=32"


@dataclass(slots=True)
class _Pat:
    """소스별 출처 추출 패턴. id_f 가 결과 항목에 없으면 그 항목은 출처 미생성.

    id_f: 식별자 필드명 / title_f: 제목 필드(tuple 이면 중첩 예 ('company','name')) /
    url: {id} 치환 템플릿 / kind: 출처 유형 라벨 / content_f: 본문 필드 /
    strip_dashes: id 의 '-' 제거(티커 정규화).
    """

    id_f: str
    title_f: str | tuple[str, str]
    url: str
    kind: str
    content_f: str | None = None
    favicon: str = ""
    strip_dashes: bool = False


_DART = dict(url=_DART_VIEWER, kind="DART 공시", favicon=_DART_FAVICON)
_MKT = dict(url=_MARKET_VENDOR, kind="시세", favicon=_MARKET_FAVICON, strip_dashes=True)
_URL_PATTERNS: dict[str, _Pat] = {
    # 공시 (DART) — 접수번호(rcept_no) 기준 공시뷰어 직링크
    "disclosure_list": _Pat("rcept_no", "report_nm", content_f="flr_nm", **_DART),
    "disclosure_detail": _Pat("rcept_no", "report_nm", content_f="summary", **_DART),
    "disclosure_financials": _Pat("rcept_no", "report_nm", content_f="account_nm", **_DART),
    "disclosure_dividend": _Pat("rcept_no", "report_nm", content_f="se", **_DART),
    "disclosure_major_shareholder": _Pat("rcept_no", "report_nm", content_f="repror", **_DART),
    # 시세 (시장 벤더) — 종목코드(symbol) 기준 종목 페이지
    "market_quote": _Pat("symbol", "name", content_f="price", **_MKT),
    "market_ohlc": _Pat("symbol", "name", content_f="close", **_MKT),
    "market_search": _Pat("symbol", "name", content_f="market", **_MKT),
    "market_index": _Pat(
        "index_code", "name", content_f="value", url=_MARKET_INDEX, kind="지수", favicon=_MARKET_FAVICON
    ),
}

# 출처가 없는 tool (집계·메타성 — 직링크 없음). mock 에서도 sources 미생성.
_NO_SOURCE_TOOLS = {
    "disclosure_company",
    "market_fx",
    "news_sentiment",
    "news_disclosure",
    "portfolio_list_accounts",
    "portfolio_list_holdings",
    "portfolio_search_transactions",
    "portfolio_search_orders",
    "portfolio_get_account_activity",
}


def _field(item: dict, spec) -> str:
    """title/content 필드 추출 — spec 이 tuple 이면 중첩(예: ('ProjectTitle','Korean'))."""
    if isinstance(spec, tuple):
        v = item.get(spec[0])
        return v.get(spec[1], "") if isinstance(v, dict) else ""
    return item.get(spec, "") if spec else ""


def _extract_pattern(tool: str, result: dict) -> list[tuple[str, dict]]:
    """url 패턴 기반 출처 추출(공시·시세·지수). id 필드 없으면 그 항목 skip."""
    pat = _URL_PATTERNS[tool]
    out: list[tuple[str, dict]] = []
    for item in result.get("data", []) or []:
        if not isinstance(item, dict):
            continue
        raw = item.get(pat.id_f)
        if not raw:
            continue
        doc_id = str(raw).strip().replace("-", "") if pat.strip_dashes else str(raw).strip()
        if not doc_id:
            continue
        url = pat.url.format(id=doc_id)
        thumb = ""
        out.append(
            (
                f"{tool}:{doc_id}",
                {
                    "url": url,
                    "title": _clean(_field(item, pat.title_f))[:200] or pat.kind,
                    "tool": tool,
                    "domain": _domain_of(url),
                    "content": _clean(_field(item, pat.content_f))[:500],
                    "thumbnail": thumb,
                    "favicon": pat.favicon,
                },
            )
        )
    return out


def _extract_web(result: dict, tool: str) -> tuple[list[tuple[str, dict]], list[tuple[str, dict]]]:
    """web 검색(Tavily) — results[].url 출처 + images. favicon=google s2."""
    imgs: list[tuple[str, dict]] = []
    srcs: list[tuple[str, dict]] = []
    for img in result.get("images", []) or []:
        u = img.get("url") if isinstance(img, dict) else (img if isinstance(img, str) else "")
        if isinstance(u, str) and u.startswith("http"):
            imgs.append((u, {"url": u, "title": "관련 이미지", "source": tool, "thumbnail": u}))
    for item in result.get("results", []) or []:
        if not isinstance(item, dict):
            continue
        url = item.get("url", "")
        if not isinstance(url, str) or not url.startswith("http") or url.endswith(".pdf"):
            continue
        domain = _domain_of(url)
        srcs.append(
            (
                url,
                {
                    "url": url,
                    "title": _clean(item.get("title", ""))[:200],
                    "tool": tool,
                    "domain": domain,
                    "content": _clean(item.get("content", ""))[:500],
                    "thumbnail": "",
                    "favicon": f"https://www.google.com/s2/favicons?domain={domain}&sz=32" if domain else "",
                },
            )
        )
    return imgs, srcs


def _extract_news(result: dict, tool: str) -> tuple[list[tuple[str, dict]], list[tuple[str, dict]]]:
    """뉴스 검색·기업 뉴스·상세 — 응답 기사 항목의 url 을 직접 출처로 사용. favicon=google s2."""
    srcs: list[tuple[str, dict]] = []
    for item in result.get("data", []) or result.get("articles", []) or []:
        if not isinstance(item, dict):
            continue
        url = item.get("url") or item.get("link")
        if not isinstance(url, str) or not url.startswith("http"):
            continue
        domain = _domain_of(url)
        srcs.append(
            (
                url,  # dedup: 기사 링크 기준
                {
                    "url": url,
                    "title": _clean(item.get("title", "관련 뉴스"))[:200],
                    "tool": tool,
                    "domain": _clean(item.get("press") or item.get("source") or domain)[:60],
                    "content": _clean(item.get("summary") or item.get("content", ""))[:500],
                    "thumbnail": "",
                    "favicon": f"https://www.google.com/s2/favicons?domain={domain}&sz=32" if domain else "",
                },
            )
        )
    return [], srcs


def _extract_doc(result: dict, tool: str, is_image: bool) -> tuple[list[tuple[str, dict]], list[tuple[str, dict]]]:
    """사내 문서 검색 — data[].file_url 이미지(image tool) / file_nm 출처(topic tool)."""
    imgs: list[tuple[str, dict]] = []
    srcs: list[tuple[str, dict]] = []
    for item in result.get("data", []) or []:
        if not isinstance(item, dict):
            continue
        fu = item.get("file_url")
        if is_image and isinstance(fu, str) and fu:
            title = item.get("file_nm") or item.get("summary_caption") or ""
            imgs.append((fu, {"url": fu, "title": _clean(title)[:150], "source": tool, "thumbnail": fu}))
            continue
        fnm = item.get("file_nm")
        if isinstance(fnm, str) and fnm:
            content = item.get("answer") or item.get("text") or item.get("detailed_caption") or ""
            srcs.append(
                (
                    f"doc:{item.get('doc_id')}:{fnm}",
                    _mk_source(title=fnm, url="", kind="사내 리서치자료", content=content, tool=tool),
                )
            )
    return imgs, srcs


def extract_media(tool_calls: list[dict]) -> tuple[list[dict], list[dict], dict]:
    """tool_calls trace 에서 (images, sources, tool_results_summary) 추출. tool_name 으로 디스패치.

    출처 url 은 example-ai-agent backend config 의 공식 직링크 패턴만 사용(추측 금지).
    JSON 파싱되는 것만 채움. dedup(소스별 식별자 기준).
    """
    sources: list[dict] = []
    images: list[dict] = []
    seen_img: set[str] = set()
    seen_src: set[str] = set()
    tools_executed: list[str] = []
    successful = 0

    for tc in tool_calls or []:
        tool = tc.get("tool", "") or ""
        if tool and tool not in tools_executed:
            tools_executed.append(tool)
        if tc.get("status") == "ok":
            successful += 1

        result = _try_json(str(tc.get("output", "")))
        if not isinstance(result, dict):
            continue

        if tool == "web_search":
            node_imgs, node_srcs = _extract_web(result, tool)
        elif tool in ("news_search", "news_company", "news_detail"):
            node_imgs, node_srcs = _extract_news(result, tool)
        elif tool.startswith("doc_search_image"):
            node_imgs, node_srcs = _extract_doc(result, tool, is_image=True)
        elif tool.startswith("doc_search_topic"):
            node_imgs, node_srcs = _extract_doc(result, tool, is_image=False)
        elif tool in _NO_SOURCE_TOOLS:
            node_imgs, node_srcs = [], []
        elif tool in _URL_PATTERNS:
            node_imgs, node_srcs = [], _extract_pattern(tool, result)
        else:
            node_imgs, node_srcs = [], []

        for key, img in node_imgs:
            if key not in seen_img:
                seen_img.add(key)
                images.append(img)
        for key, src in node_srcs:
            if key not in seen_src:
                seen_src.add(key)
                sources.append(src)

    summary = {
        "total_tools": len(tool_calls or []),
        "successful_tools": successful,
        "tools_executed": tools_executed,
        "has_results": bool(sources or images),
    }
    return images, sources, summary
