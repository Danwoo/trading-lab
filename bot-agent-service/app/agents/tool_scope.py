"""읽기 도구의 **경로 스코프** — 전략 디렉터리 밖을 읽지 못하게 막는다.

왜 이 파일이 필요한가 (PR #154 독립 리뷰가 잡은 결함):

`allowed_tools=["Read","Glob","Grep"]` 처럼 **bare name** 으로 적은 허용은 경로와 무관한 전체
자동승인이다. `cwd` 는 상대경로의 해석 기준이자 scoped rule 의 앵커일 뿐, 허용된 도구의 접근
범위를 좁히지 않는다 — SDK 자신도 `SandboxSettings` 주석에서 *"Filesystem read restrictions:
Use Read deny rules"* 라고 적는다. 즉 `cwd` 만 걸어 두면 대화 한 턴으로
`../../backend-service/.env.production` 을 읽어 SSE 로 돌려받을 수 있다.

그래서 **PreToolUse 훅**으로 막는다. 권한 평가 순서(훅 → deny → ask → 권한 모드 → allow →
`can_use_tool`)에서 훅이 맨 앞이라, 자동승인보다 먼저 판정된다. 자동승인된 도구는
`can_use_tool` 콜백에 아예 오지 않으므로 그 자리로는 못 막는다.

판정은 **fail-closed** 다 — 인자 모양을 모르면 거부한다. 모르는 모양을 통과시키면 도구 인자가
바뀌는 날 조용히 열린다.
"""

from __future__ import annotations

from pathlib import Path

# 경로 인자를 갖는 읽기 도구와, 그 도구에서 **경로로 해석되는** 인자 이름.
# `Grep`/`Glob` 의 `pattern` 도 포함한다 — `../../**/.env` 같은 패턴이 곧 경로 탈출이다.
PATH_ARGS: dict[str, tuple[str, ...]] = {
    "Read": ("file_path", "notebook_path"),
    "Glob": ("path", "pattern"),
    "Grep": ("path", "pattern", "glob"),
}


def _escapes(candidate: str, root: Path) -> bool:
    """이 문자열이 `root` 밖을 가리키는가."""
    text = candidate.strip()
    if not text:
        return False  # 빈 값은 도구 기본값(cwd) — 그 자체로는 탈출이 아니다
    path = Path(text)
    if path.is_absolute():
        # 절대경로는 root 아래일 때만 허용한다 (root 자신도 허용).
        try:
            resolved = path.resolve()
        except (OSError, ValueError):
            # 널바이트가 섞이면 `ValueError` 다 — 모양을 모르면 거부한다 (fail-closed).
            return True
        return not _inside(resolved, root)
    if ".." in path.parts:
        # 상대경로의 `..` 는 해석 전에 자른다 — 존재하지 않는 경로도 막아야 하고,
        # `resolve()` 는 없는 경로에서 심링크를 못 따라가 판정이 환경에 따라 갈린다.
        return True
    try:
        resolved = (root / path).resolve()
    except (OSError, ValueError):
        return True
    # 심링크가 밖을 가리키면 resolve 결과가 root 밖으로 나간다 — 그때도 거부다.
    return not _inside(resolved, root)


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def check_tool_scope(tool_name: str, tool_input: dict, root: Path) -> str | None:
    """거부 사유를 돌려준다. `None` 이면 통과.

    스코프 대상이 아닌 도구는 통과시킨다 — 이 함수는 **경로 스코프만** 본다. 도구 자체의
    허용·차단은 `bot_agent.py` 의 목록이 정한다 (두 경계를 한 곳에 섞으면 둘 다 흐려진다).
    """
    arg_names = PATH_ARGS.get(tool_name)
    if arg_names is None:
        return None

    try:
        root = Path(root).resolve()
    except (OSError, ValueError):
        return "전략 디렉터리를 확인할 수 없습니다"

    if not isinstance(tool_input, dict):
        return f"{tool_name} 의 인자를 읽을 수 없어 거부했습니다"

    for name in arg_names:
        value = tool_input.get(name)
        if value is None:
            continue
        if not isinstance(value, str):
            # 모양이 다르면 통과시키지 않는다 — fail-closed.
            return f"{tool_name}.{name} 의 값이 문자열이 아니어서 거부했습니다"
        if _escapes(value, root):
            return f"전략 디렉터리 밖은 읽지 않습니다: {tool_name}.{name}"
    return None


async def scope_hook(input_data, tool_use_id, context, *, root: Path):  # noqa: ARG001
    """PreToolUse 훅 — `check_tool_scope` 의 판정을 SDK 형식으로 옮긴다.

    `bot_agent.build_options` 가 `functools.partial` 로 `root` 를 묶어 넘긴다.
    """
    reason = check_tool_scope(input_data.get("tool_name", ""), input_data.get("tool_input") or {}, root)
    if reason is None:
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
