"""`alembic upgrade head` 전에 체크아웃이 origin/main 만큼 최신인지 검사 (#387).

배경: `head` 는 **"이 체크아웃의 `alembic/versions/` 안에서 가장 끝"** 이지 "레포의 최신"이
아니다. 낡은 트리에서 `upgrade head` 를 돌리면 **오류 없이 종료 코드 0** 으로 덜 적용되고,
`alembic current` 도 그 트리 기준으로는 "현재 head" 라고 정직하게 보고한다. 코드만 최신이고 DB 가
뒤처지면 한참 뒤 런타임에서 `column does not exist` 로 터진다 (#370 의 증상).

정본을 정한다: **마이그레이션의 정본은 `origin/main`** 이다. 이 스크립트는 체크아웃의 리비전
그래프가 origin/main 의 head 리비전을 **포함**하는지 본다.

  - 포함한다 → 통과. 그 위에 새 리비전을 얹은 기능 브랜치도 통과한다(정본보다 앞선 것은 정상).
  - 포함하지 않는다 → 실패. 이 트리에서 `upgrade head` 를 돌리면 origin/main 이 이미 가진
    리비전이 **조용히 빠진 채** 성공으로 끝난다.

`--fetch` 는 검사 전에 `git fetch origin main` 으로 원격 참조를 갱신한다(process-compose 의
db-migrate 가 그렇게 부른다). 네트워크·인증 실패 시에는 **경고를 크게 찍고 이미 있는
`origin/main` 참조로 검사를 계속한다** — 오프라인에서 개발 기동 자체를 막지 않기 위해서다.
`origin` 원격이 걸린 트리에서 참조가 아예 없으면 검사할 정본이 없으므로 실패한다.

**fail-closed**: 리비전을 0건 수집하면 통과가 아니라 실패다. `origin` 원격이 있는데
`origin/main` 참조가 없어도 실패다.

**예외 — 원격이 아예 없는 트리는 건너뛴다** (#399). 릴리스 tarball·GitHub ZIP 다운로드처럼
`.git` 이 없거나 `origin` 이 안 걸린 트리에서는 대조할 정본이 **존재할 수 없다.** 여기서
실패하면 이 검사가 `db-migrate` 의 첫 줄이라 `prisma db push` 도 `alembic upgrade head` 도
못 돌고, 새로 받은 사람은 스키마 없는 DB 앞에서 멈춘다(실측: #399). 그래서 이 경우에만
경고 후 0 으로 끝낸다 — 다만 **조용히 넘기지 않는다**: 무엇을 확인했고 무엇을 못 봤는지,
대조를 켜려면 무엇을 해야 하는지 출력에 남긴다. 원격이 있는 트리(=개발자)의 엄격함은 그대로다.

stdlib 전용 (AST 파싱 + git CLI): `python3 scripts/verify_alembic_head_freshness.py [--fetch]`.
"""

from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSIONS_DIR = "backend-service/alembic/versions"
ORIGIN_REF = "origin/main"
ORIGIN_REMOTE = "origin"
FETCH_TIMEOUT_SECONDS = 20

# 트리가 정본과 대조할 수 있는 상태인가.
NO_REPO = "no-repo"  # .git 이 없다 — tarball·ZIP 다운로드·git archive
NO_REMOTE = "no-remote"  # git 저장소이긴 한데 origin 원격이 없다
HAS_REMOTE = "has-remote"  # origin 이 걸려 있다 — 여기서는 엄격히 본다

# 원격 없는 트리에 낼 문구: (무엇이 없나, 대조를 켜려면)
SKIP_GUIDANCE: dict[str, tuple[str, str]] = {
    NO_REPO: (
        "이 트리가 git 저장소의 루트가 아니다 (.git 이 없다 — 릴리스 tarball·ZIP 다운로드·git archive; "
        "남의 저장소 안에 풀어 놓은 경우도 여기다)",
        "원격이 걸린 클론에서 받아라: `git clone <레포 URL>` "
        "(이 트리를 그대로 쓰려면 `git init && git remote add origin <레포 URL> && git fetch origin main`)",
    ),
    NO_REMOTE: (
        f"이 트리에 `{ORIGIN_REMOTE}` 원격이 없다",
        f"`git remote add {ORIGIN_REMOTE} <레포 URL> && git fetch {ORIGIN_REMOTE} main`",
    ),
}


def _git(*args: str, check: bool = True, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    # 자격증명 프롬프트로 멈추지 않게 한다 — 인증이 필요한 원격이면 물어보지 말고 실패해야 한다
    # (기동 스크립트 안에서 도는 검사라 사람 입력을 기다리면 그대로 멈춘다).
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        check=check,
        timeout=timeout,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


def parse_revision(source: str, label: str) -> tuple[str | None, tuple[str, ...]]:
    """리비전 파일 소스에서 (revision, down_revision 들)을 뽑는다 (AST — import 없음)."""
    try:
        tree = ast.parse(source, filename=label)
    except SyntaxError:
        return None, ()
    revision: str | None = None
    downs: tuple[str, ...] = ()
    for node in tree.body:
        target = None
        value = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target, value = node.target.id, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target, value = node.targets[0].id, node.value
        if target == "revision" and isinstance(value, ast.Constant) and isinstance(value.value, str):
            revision = value.value
        elif target == "down_revision":
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                downs = (value.value,)
            elif isinstance(value, (ast.Tuple, ast.List)):
                downs = tuple(e.value for e in value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str))
    return revision, downs


def build_graph(sources: dict[str, str]) -> dict[str, tuple[str, ...]]:
    """{파일 라벨: 소스} → {revision: (down_revision …)}."""
    graph: dict[str, tuple[str, ...]] = {}
    for label, source in sources.items():
        revision, downs = parse_revision(source, label)
        if revision is not None:
            graph[revision] = downs
    return graph


def heads(graph: dict[str, tuple[str, ...]]) -> list[str]:
    """누구의 down_revision 도 아닌 리비전 = head."""
    referenced = {down for downs in graph.values() for down in downs}
    return sorted(set(graph) - referenced)


def stale_problems(local: dict[str, tuple[str, ...]], origin: dict[str, tuple[str, ...]]) -> list[str]:
    """체크아웃이 origin/main 의 head 리비전을 포함하지 않으면 위반."""
    problems: list[str] = []
    for origin_head in heads(origin):
        if origin_head not in local:
            problems.append(
                f"체크아웃에 {ORIGIN_REF} 의 head 리비전 `{origin_head}` 이 없다 — 이 트리에서 "
                "`alembic upgrade head` 를 돌리면 그 리비전이 조용히 빠진 채 성공한다. "
                "최신 main 을 받은 뒤(`git fetch origin main && git merge origin/main`) 다시 돌릴 것"
            )
    return problems


def _local_sources() -> dict[str, str]:
    directory = REPO_ROOT / VERSIONS_DIR
    if not directory.is_dir():
        return {}
    return {str(p.relative_to(REPO_ROOT)): p.read_text() for p in sorted(directory.glob("*.py"))}


def _origin_sources() -> dict[str, str] | None:
    """origin/main 의 versions/ 소스 (참조가 없으면 None).

    `remote_state()` 가 HAS_REMOTE 를 돌려준 뒤에만 부른다 — `.git` 없는 트리에서 git 은 상위
    디렉터리의 조상 저장소를 찾아 성공하므로, 그 조상의 `origin/main` 을 정본으로 읽어 버린다.
    """
    if _git("rev-parse", "--verify", "--quiet", ORIGIN_REF, check=False).returncode != 0:
        return None
    listed = _git("ls-tree", "-r", "--name-only", ORIGIN_REF, "--", VERSIONS_DIR)
    sources: dict[str, str] = {}
    for path in listed.stdout.split():
        if path.endswith(".py"):
            sources[path] = _git("show", f"{ORIGIN_REF}:{path}").stdout
    return sources


def remote_state() -> str:
    """이 트리가 `origin` 과 대조할 수 있는 상태인지 — NO_REPO / NO_REMOTE / HAS_REMOTE.

    `--show-toplevel` 이 REPO_ROOT 와 같은지까지 본다: tarball 을 **다른 git 저장소 안**
    (예: 홈 디렉터리가 dotfiles 레포)에 풀면 `--git-dir` 은 남의 저장소로 성공하고, 그 남의
    `origin` 을 정본으로 삼아 엉뚱한 대조를 하게 된다.
    """
    toplevel = _git("rev-parse", "--show-toplevel", check=False)
    if toplevel.returncode != 0 or Path(toplevel.stdout.strip() or "/nonexistent").resolve() != REPO_ROOT:
        return NO_REPO
    listed = _git("remote", check=False)
    if listed.returncode != 0:
        return NO_REPO
    return HAS_REMOTE if ORIGIN_REMOTE in listed.stdout.split() else NO_REMOTE


def _fetch() -> None:
    result = _git(
        "fetch",
        "--quiet",
        "--no-tags",
        "origin",
        "main",
        check=False,
        timeout=FETCH_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        print(
            f"  ! `git fetch origin main` 실패 — 이미 있는 {ORIGIN_REF} 참조로 검사한다. "
            "그 참조가 낡았으면 이 검사도 낡은 기준으로 본다 "
            f"(사유: {result.stderr.strip() or '알 수 없음'})"
        )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="검사 전에 origin/main 참조를 갱신한다")
    args = parser.parse_args(argv)

    state = remote_state()

    if args.fetch:
        if state == HAS_REMOTE:
            try:
                _fetch()
            except (subprocess.SubprocessError, OSError) as exc:
                print(f"  ! git fetch 실행 자체가 실패했다 (이미 있는 참조로 계속한다): {exc}")
        else:
            print(f"  ! `git fetch {ORIGIN_REMOTE} main` 을 건너뛴다 — {SKIP_GUIDANCE[state][0]}")

    local_sources = _local_sources()
    local = build_graph(local_sources)
    if not local:
        print(
            f"alembic head 검사 실패: {VERSIONS_DIR} 에서 리비전을 0건 수집했다 "
            "(경로가 옮겨졌거나 파일 형식이 바뀌었다 — 검사가 헛돌고 있다)"
        )
        return 1

    if state != HAS_REMOTE:
        missing, how_to = SKIP_GUIDANCE[state]
        print(
            f"alembic head 검사 건너뜀 — {missing}. 대조할 정본이 없다.\n"
            f"  · 확인한 것: {VERSIONS_DIR} 에서 리비전 {len(local)}개를 수집했다 "
            f"(head: {', '.join(heads(local))}).\n"
            f"  · 못 본 것: 이 트리가 정본({ORIGIN_REF})보다 낡았는지. 낡은 트리의 "
            "`alembic upgrade head` 는 리비전을 조용히 빠뜨리고도 종료 코드 0 으로 끝난다 (#387).\n"
            f"  · 대조를 켜려면: {how_to}"
        )
        return 0

    origin_sources = _origin_sources()
    if origin_sources is None:
        print(
            f"alembic head 검사 실패: {ORIGIN_REF} 참조가 없어 정본과 대조할 수 없다. "
            f"`git fetch {ORIGIN_REMOTE} main` 후 다시 실행할 것"
        )
        return 1
    origin = build_graph(origin_sources)
    if not origin:
        print(
            f"alembic head 검사 실패: {ORIGIN_REF} 의 {VERSIONS_DIR} 에서 리비전을 0건 수집했다 "
            "(그쪽 경로가 옮겨졌다면 이 스크립트의 VERSIONS_DIR 을 함께 고칠 것)"
        )
        return 1

    problems = stale_problems(local, origin)
    if problems:
        print("alembic head 신선도 위반:")
        for p in problems:
            print(f"  - {p}")
        return 1

    origin_commit = _git("rev-parse", "--short", ORIGIN_REF).stdout.strip()
    print(
        f"alembic head 신선도 OK — 체크아웃 리비전 {len(local)}개(head: {', '.join(heads(local))}) 가 "
        f"{ORIGIN_REF}({origin_commit}) 의 리비전 {len(origin)}개(head: {', '.join(heads(origin))})를 포함"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
