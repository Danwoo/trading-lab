"""#387 — 체크아웃이 origin/main 보다 뒤처졌을 때 alembic head 검사가 시끄럽게 실패하는지.

이 레포는 아직 pytest 를 도입하지 않았으므로(전 서비스 공통) standalone 실행 겸용으로 작성한다:
    uv run python tests/test_alembic_head_freshness.py

`scripts/verify_alembic_head_freshness.py` 의 **순수 함수**(리비전 파싱·head 계산·뒤처짐 판정)를
합성 리비전 그래프로 검증한다 — git·DB 없이 돈다. 스크립트 전체(원격 참조 조회)는 개발 기동
경로(process-compose 의 db-migrate)에서 실제로 돌고, 여기서는 그 판정 로직이 다음을 지키는지 본다:

  (1) 체크아웃이 origin/main 의 head 를 **가지고 있으면** 통과 (같거나 앞서 있는 상태).
  (2) 체크아웃에 origin/main 의 head 가 **없으면** 위반 — 이것이 #387 의 조용한 부분 적용이다.
  (3) 실제 레포의 versions/ 를 파싱해 head 가 정확히 1개인지 — 여러 개면 `upgrade head` 자체가
      모호해진다(파싱 형식이 바뀌어 0건이 되는 경우도 여기서 걸린다, fail-closed).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from verify_alembic_head_freshness import (  # noqa: E402
    build_graph,
    heads,
    parse_revision,
    stale_problems,
)

_TEMPLATE = '''"""d"""

revision: str = "{rev}"
down_revision: str | Sequence[str] | None = {down}
'''


def _sources(*chain: str) -> dict[str, str]:
    """0001 → 0002 → … 선형 체인을 리비전 파일 소스 묶음으로."""
    out: dict[str, str] = {}
    previous = "None"
    for rev in chain:
        out[f"{rev}.py"] = _TEMPLATE.format(rev=rev, down=previous)
        previous = f'"{rev}"'
    return out


def test_parse_and_heads() -> str:
    revision, downs = parse_revision(_TEMPLATE.format(rev="0002_b", down='"0001_a"'), "0002_b.py")
    assert revision == "0002_b", revision
    assert downs == ("0001_a",), downs
    graph = build_graph(_sources("0001_a", "0002_b", "0003_c"))
    assert heads(graph) == ["0003_c"], heads(graph)
    return "test_parse_and_heads"


def test_checkout_containing_origin_head_passes() -> str:
    origin = build_graph(_sources("0001_a", "0002_b"))
    same = build_graph(_sources("0001_a", "0002_b"))
    ahead = build_graph(_sources("0001_a", "0002_b", "0003_c"))  # 새 리비전을 얹은 기능 브랜치
    assert stale_problems(same, origin) == [], stale_problems(same, origin)
    assert stale_problems(ahead, origin) == [], stale_problems(ahead, origin)
    return "test_checkout_containing_origin_head_passes"


def test_stale_checkout_is_reported() -> str:
    origin = build_graph(_sources("0001_a", "0002_b", "0003_c"))
    stale = build_graph(_sources("0001_a", "0002_b"))  # #387 상황 — 최신 리비전이 없는 트리
    problems = stale_problems(stale, origin)
    assert len(problems) == 1, problems
    assert "0003_c" in problems[0], problems[0]
    return "test_stale_checkout_is_reported"


def test_repo_versions_have_exactly_one_head() -> str:
    versions = _REPO_ROOT / "backend-service" / "alembic" / "versions"
    sources = {p.name: p.read_text() for p in sorted(versions.glob("*.py"))}
    graph = build_graph(sources)
    assert len(graph) >= 1, f"{versions} 에서 리비전을 0건 파싱했다 — 파일 형식이 바뀌었거나 경로가 옮겨졌다"
    assert len(heads(graph)) == 1, (
        f"head 가 여러 개다 {heads(graph)} — `alembic upgrade head` 가 모호해진다 (merge 리비전 필요)"
    )
    print(f"  실제 versions/ 리비전 {len(graph)}개, head={heads(graph)[0]}")
    return "test_repo_versions_have_exactly_one_head"


def _main() -> int:
    tests = [
        test_parse_and_heads,
        test_checkout_containing_origin_head_passes,
        test_stale_checkout_is_reported,
        test_repo_versions_have_exactly_one_head,
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
