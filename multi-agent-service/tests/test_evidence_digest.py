"""#196 — 증거 다이제스트 절단 상한 완화(블록당 500→1500)의 결정론 검증 (E-196 Tier 0, LLM 호출 0회).

수치를 501·1499·1501자 위치에 심은 도구 출력으로 _evidence_digest 를 호출해
1500자 내 생존/초과 탈락·총량 6000 준수·절단 로그 발생을 검증한다.
(writer 의 보존 '행동' 판정은 Tier 1 E-196W — LLM 필요, 예산 승인 후.)

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    APP_ENV=development uv run python tests/test_evidence_digest.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

os.environ.setdefault("APP_ENV", "development")
_APP_DIR = Path(__file__).resolve().parents[1] / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from core.logger import logger  # noqa: E402
from graphs.pipeline_subagent import (  # noqa: E402
    _EVIDENCE_ARGS_HEAD_MAX_CHARS,
    _EVIDENCE_BLOCK_MAX_CHARS,
    _EVIDENCE_TOTAL_MAX_CHARS,
    _evidence_digest,
    _raw_evidence_len,
)
from langchain_core.messages import AIMessage, ToolMessage  # noqa: E402

_MARKER = "128,000원"  # #196 실사례 목표주가


def _tool_pair(
    body: str, call_id: str = "t1", name: str = "doc_search_topic_workspace", args: dict | None = None
) -> list:
    ai = AIMessage(content="", tool_calls=[{"name": name, "args": args or {}, "id": call_id, "type": "tool_call"}])
    tm = ToolMessage(content=body, tool_call_id=call_id, name=name)
    return [ai, tm]


def _body_with_marker_at(index: int, total: int = 2000) -> str:
    """index(0-기준) 위치에 마커를 심은 total 자 도구 출력."""
    tail_len = total - index - len(_MARKER)
    assert tail_len >= 0
    return "x" * index + _MARKER + "y" * tail_len


class _LogCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def test_marker_beyond_old_500_cap_survives() -> str:
    """구 상한(500) 너머 501자 위치의 수치가 새 상한(1500)에서 생존 — #196 유실 구간 해소."""
    digest = _evidence_digest(_tool_pair(_body_with_marker_at(500)))
    assert _MARKER in digest, "501자 위치 수치가 다이제스트에서 유실됨"
    return "test_marker_beyond_old_500_cap_survives"


def test_marker_near_1500_boundary() -> str:
    """1499자에 끝나는 수치는 생존, 1501자에서 시작하는 수치는 탈락 (블록 상한 경계)."""
    end_at_1499 = _body_with_marker_at(1499 - len(_MARKER))
    assert _MARKER in _evidence_digest(_tool_pair(end_at_1499)), "1500자 내 수치가 유실됨"
    start_at_1500 = _body_with_marker_at(1500)
    assert _MARKER not in _evidence_digest(_tool_pair(start_at_1500)), "블록 상한 초과 수치가 생존 (상한 미적용)"
    return "test_marker_near_1500_boundary"


def test_total_cap_6000_preserved() -> str:
    """블록 5개 × 1500자 이상 → 다이제스트 총량 ≤ 6000 유지."""
    messages: list = []
    for i in range(5):
        messages += _tool_pair("z" * 2000, call_id=f"t{i}", name=f"tool_{i}")
    digest = _evidence_digest(messages)
    assert len(digest) <= _EVIDENCE_TOTAL_MAX_CHARS, f"총량 상한 위반: {len(digest)}"
    assert len(digest) == _EVIDENCE_TOTAL_MAX_CHARS, f"5블록이면 총량 상한에 닿아야 함 (검사 유효성): {len(digest)}"
    return "test_total_cap_6000_preserved"


def test_truncation_log_emitted() -> str:
    """블록 절단 발생 시 '[pipeline] evidence 절단: tool=… raw=…→…' 로그 1줄."""
    capture = _LogCapture()
    logger.addHandler(capture)
    try:
        _evidence_digest(_tool_pair("x" * 3000))
    finally:
        logger.removeHandler(capture)
    cut_logs = [m for m in capture.messages if "evidence 절단" in m]
    assert len(cut_logs) == 1, f"절단 로그 기대 1건, 실제 {len(cut_logs)}: {capture.messages}"
    assert "tool=doc_search_topic_workspace" in cut_logs[0] and "raw=3000→1500" in cut_logs[0], cut_logs[0]
    # 절단이 없으면 로그도 없어야 한다 (노이즈 방지)
    capture2 = _LogCapture()
    logger.addHandler(capture2)
    try:
        _evidence_digest(_tool_pair("x" * 100))
    finally:
        logger.removeHandler(capture2)
    assert not [m for m in capture2.messages if "evidence 절단" in m], "무절단인데 절단 로그 발생"
    return "test_truncation_log_emitted"


def test_raw_evidence_len_counts_untruncated() -> str:
    """raw_ev_len 관측값은 절단 전 도구 출력 총 길이 — 절단 기인 판별의 근거."""
    messages = _tool_pair("x" * 3000) + _tool_pair("y" * 200, call_id="t2", name="tool_b")
    assert _raw_evidence_len(messages) == 3200, _raw_evidence_len(messages)
    assert _EVIDENCE_BLOCK_MAX_CHARS == 1500 and _EVIDENCE_TOTAL_MAX_CHARS == 6000
    return "test_raw_evidence_len_counts_untruncated"


def test_head_args_repr_is_capped() -> str:
    """#277 — head("tool(args)") 의 args repr 이 길어도 상한(_EVIDENCE_ARGS_HEAD_MAX_CHARS)을 넘지 않는다."""
    huge_args = {"query": "가" * 5000}
    digest = _evidence_digest(_tool_pair("결과", args=huge_args))
    head_line = digest.splitlines()[0]
    # head_line = "- {name}({capped_args_repr}) → {body}" — args repr 부분만 상한 이내인지 느슨하게 확인
    # (name·괄호·구분자 오버헤드 감안해 상한 + 여유분으로 상단 비교)
    assert len(head_line) < _EVIDENCE_ARGS_HEAD_MAX_CHARS + 100, f"head 가 캡 없이 그대로 부풂: {len(head_line)}자"
    assert "…(생략)" in head_line, "head 절단 마커 없음"
    return "test_head_args_repr_is_capped"


def test_huge_head_does_not_starve_later_block_body() -> str:
    """#277 — 첫 블록의 거대 args 가 총량 상한을 통째로 잠식해 뒤 블록 body 를 밀어내지 않는다."""
    huge_args = {"query": "가" * 50_000}  # 캡 없으면 이 한 블록만으로 총량(6000)을 넘김
    messages = _tool_pair("첫 블록 결과", call_id="t1", name="tool_a", args=huge_args)
    messages += _tool_pair(f"두 번째 블록 결과 — {_MARKER}", call_id="t2", name="tool_b")
    digest = _evidence_digest(messages)
    assert len(digest) <= _EVIDENCE_TOTAL_MAX_CHARS, f"총량 상한 위반: {len(digest)}"
    assert _MARKER in digest, "거대 인자 head 가 총량을 잠식해 뒤 블록 결과가 밀려남 (#277 재발)"
    return "test_huge_head_does_not_starve_later_block_body"


def test_small_args_repr_unchanged() -> str:
    """작은 args 는 절단 마커 없이 그대로 남는다 (회귀 방향)."""
    digest = _evidence_digest(_tool_pair("결과", args={"query": "삼성전자"}))
    assert "doc_search_topic_workspace" in digest and "삼성전자" in digest
    assert "…(생략)" not in digest, "작은 인자인데 절단 마커가 붙음"
    return "test_small_args_repr_unchanged"


def _main() -> int:
    tests = [
        test_marker_beyond_old_500_cap_survives,
        test_marker_near_1500_boundary,
        test_total_cap_6000_preserved,
        test_truncation_log_emitted,
        test_raw_evidence_len_counts_untruncated,
        test_head_args_repr_is_capped,
        test_huge_head_does_not_starve_later_block_body,
        test_small_args_repr_unchanged,
    ]
    passed = 0
    for tc in tests:
        print(f"PASS {tc()}")
        passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(_main())
