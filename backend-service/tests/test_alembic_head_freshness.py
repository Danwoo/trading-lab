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

#399 로 넷이 붙었다. 「원격 없는 트리는 건너뛴다」는 fail-open 예외라 **판정 함수가 아니라
스크립트 전체를 실제로 돌려** 확인해야 한다 — 합성 트리를 임시 디렉터리에 만들고 `.git`·`origin`
유무만 갈아 끼운다 (네트워크·DB 없음):

  (4) `.git` 이 없는 트리(tarball·ZIP 다운로드) → 종료 0, 그리고 **못 본 것을 출력에 남긴다.**
  (5) git 저장소지만 `origin` 원격이 없는 트리 → 종료 0, 같은 고지.
  (6) `origin` 은 있는데 `origin/main` 참조가 없는 트리 → 종전대로 **종료 1** (엄격함 유지).
  (7) 원격이 없어도 리비전 0건이면 **종료 1** — fail-closed 가 예외에 먹히지 않았는지.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
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


_SCRIPT = _REPO_ROOT / "scripts" / "verify_alembic_head_freshness.py"
_GIT_ENV = {
    **os.environ,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def _synthetic_tree(root: Path, *, revisions: tuple[str, ...]) -> None:
    """검사 대상 트리를 만든다 — 스크립트 사본 + versions/ (REPO_ROOT 는 __file__ 기준이다)."""
    (root / "scripts").mkdir(parents=True)
    shutil.copy2(_SCRIPT, root / "scripts" / _SCRIPT.name)
    versions = root / "backend-service" / "alembic" / "versions"
    versions.mkdir(parents=True)
    previous = "None"
    for rev in revisions:
        (versions / f"{rev}.py").write_text(_TEMPLATE.format(rev=rev, down=previous))
        previous = f'"{rev}"'


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, env=_GIT_ENV)


def _run_script(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(root / "scripts" / _SCRIPT.name), "--fetch"],
        capture_output=True,
        text=True,
        env=_GIT_ENV,
    )


def _skip_notice_is_honest(output: str) -> None:
    """건너뛸 때 「무엇을 확인했고 무엇을 못 봤는지」가 출력에 남아야 한다 (조용한 통과 금지)."""
    for needle in ("건너뜀", "확인한 것", "못 본 것", "대조를 켜려면"):
        assert needle in output, f"건너뜀 고지에 `{needle}` 이 없다:\n{output}"


def test_tree_without_git_skips_loudly() -> str:
    """#399 — .git 이 없는 트리(tarball·ZIP)에서 기동이 막히지 않는다."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "fresh"
        _synthetic_tree(root, revisions=("0001_a", "0002_b"))
        result = _run_script(root)
    assert result.returncode == 0, f"exit={result.returncode}\n{result.stdout}{result.stderr}"
    _skip_notice_is_honest(result.stdout)
    assert "0002_b" in result.stdout, result.stdout
    return "test_tree_without_git_skips_loudly"


def test_repo_without_origin_remote_skips_loudly() -> str:
    """#399 — git init 만 한 트리에도 정본이 없다."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "no-remote"
        _synthetic_tree(root, revisions=("0001_a",))
        _git(root, "init", "-q", "-b", "main", ".")
        result = _run_script(root)
    assert result.returncode == 0, f"exit={result.returncode}\n{result.stdout}{result.stderr}"
    _skip_notice_is_honest(result.stdout)
    assert "origin` 원격이 없다" in result.stdout, result.stdout
    return "test_repo_without_origin_remote_skips_loudly"


def test_origin_remote_without_ref_still_fails() -> str:
    """원격이 걸린 트리(=개발자)의 엄격함은 그대로다 — 예외가 여기까지 번지면 #387 이 되살아난다."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "has-remote"
        _synthetic_tree(root, revisions=("0001_a",))
        _git(root, "init", "-q", "-b", "main", ".")
        _git(root, "remote", "add", "origin", "https://example.invalid/x.git")
        result = _run_script(root)
    assert result.returncode == 1, f"exit={result.returncode}\n{result.stdout}{result.stderr}"
    assert "검사 실패" in result.stdout, result.stdout
    return "test_origin_remote_without_ref_still_fails"


def test_no_remote_with_zero_revisions_still_fails() -> str:
    """fail-closed 가 예외에 먹히지 않았는지 — 볼 것이 0건이면 건너뜀이 아니라 실패다."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "empty"
        _synthetic_tree(root, revisions=())
        result = _run_script(root)
    assert result.returncode == 1, f"exit={result.returncode}\n{result.stdout}{result.stderr}"
    assert "0건" in result.stdout, result.stdout
    return "test_no_remote_with_zero_revisions_still_fails"


def _main() -> int:
    tests = [
        test_parse_and_heads,
        test_checkout_containing_origin_head_passes,
        test_stale_checkout_is_reported,
        test_repo_versions_have_exactly_one_head,
        test_tree_without_git_skips_loudly,
        test_repo_without_origin_remote_skips_loudly,
        test_origin_remote_without_ref_still_fails,
        test_no_remote_with_zero_revisions_still_fails,
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
