"""에이전트 TUI 터미널의 준비·접수를 **화면 내용**으로 판정한다 — I/O 없는 순수 함수 (stdlib 전용).

## 왜 있나

`cross-review.yml` 은 준비·접수를 `orca-ide terminal read` 의 `latestCursor` **성장**으로
판정했다. 그런데 Claude Code TUI 는 화면을 제자리에서 다시 그려 그 값이 **안 움직인다**.
2026-08-08 실측(워크트리 `t2probe-claude`, Claude Code v2.1.226):

  · 갓 뜬 유휴 화면 30초  → `latestCursor` 가 3초 간격 10회 전부 `1`
  · 1KB 프롬프트 전송 후 → 에이전트가 파일을 읽고 답까지 냈는데도 18초 내내 `1`

`now > base` 가 claude 경로에서 영원히 거짓이므로 **타임아웃을 늘려도 무효**다. 반면 kimi 는
같은 실측에서 `16 → 61 → 70 → 108` 로 자랐다 — 그래서 kimi 경로만 살아 있었다.

그래서 판정 근거를 커서 숫자가 아니라 **입력 상자의 내용**으로 옮긴다. 커서는 런타임이 주는
값이라 우리가 못 고치지만, 화면은 두 에이전트 모두 그린다.

## 무엇을 보나 — 입력 상자의 캐럿 줄

두 TUI 모두 화면 맨 아래에 **입력 상자**를 그리고 커서를 그 안에 둔다. 터미널 버퍼의 tail 은
커서 위치에서 끝나므로, **tail 에서 마지막으로 나타나는 캐럿 줄이 곧 입력 상자**다.

    claude  `❯ <입력>`            (위아래를 `────` 자로 두른다)
    kimi    `│ > <입력>        │`  (`╭─╮`/`╰─╯` 상자)

「마지막」이 중요하다 — claude 는 **제출된 프롬프트를 트랜스크립트에도 `❯ …` 로 되울린다**.
캐럿 줄을 앞에서부터 찾으면 그 되울림을 입력 상자로 오인해 접수를 영영 못 본다.

## 판정 셋

  · `agent_ready`    — 캐럿 줄이 있다 = TUI 가 입력 상자를 그렸다 = 입력을 받을 수 있다.
  · `input_pending`  — 캐럿 줄에 우리가 보낸 텍스트가 있다 = 도착했고 **아직 미제출**이다.
  · `prompt_accepted`— 상자는 있는데 우리 텍스트가 캐럿 줄에서 사라졌다 = 제출됐다.

`prompt_accepted` 를 「트랜스크립트에 되울림이 보임」으로 잡을 수는 없다. kimi 는 제출 순간
화면을 통째로 갈아 보낸 텍스트가 tail 에서 **사라진다**(실측). 두 에이전트에 공통인 신호는
「캐럿 줄에서 사라졌다」뿐이다. 그래서 호출부는 반드시 **`input_pending` 을 먼저 확인한 뒤에만**
Enter 를 보내고 `prompt_accepted` 를 묻는다 — 그 순서가 이 판정의 전제다.

상자 자체가 안 보이면 `prompt_accepted` 는 **거짓**이다 (fail-closed). 화면이 재그리기
중간이라 판정할 근거가 없는 상태를 「접수됨」으로 읽지 않는다.

## 캐럿 줄이 아닌 것

맨 셸(`user@host:~/path$`)에는 캐럿 줄이 없어 `agent_ready` 가 거짓이다 — 에이전트 바이너리가
없어 셸만 남은 워크트리를 「준비됨」으로 읽지 않는다. 다만 `❯` 를 쓰는 PS1(starship 류)이면
맨 셸도 준비됨으로 읽힌다. 이 터미널은 에이전트를 **명령으로 지정해** 띄우므로 셸 프롬프트가
보이는 것 자체가 이미 기동 실패이고, 그 경우 이후 접수 판정에서 걸린다.

CLI (bash 호출부용 — `orca-ide terminal read --json` 출력을 stdin 으로 받는다):

    orca-ide terminal read --terminal <handle> --limit 60 --json \\
      | python3 scripts/terminal_state.py ready
    ... | python3 scripts/terminal_state.py pending "<needle>"
    ... | python3 scripts/terminal_state.py accepted "<needle>"

`--agent <이름>` 을 주면 그 에이전트의 줄-중간 캐럿까지 본다 (codex 의 `›`). 안 주면
줄 맨 앞 캐럿만 본다 — 누구의 화면인지 모르는 자리에서 규칙을 넓히지 않는다.

종료코드 0=참 · 1=거짓 · 2=입력을 읽을 수 없음(호출부는 거짓과 구분해 다룬다).
"""

from __future__ import annotations

import json
import sys

# 캐럿 문자 — claude 는 `❯`, kimi 는 `>`. 둘 다 **줄 맨 앞**에 오고, 뒤에 공백이 오거나
# 줄이 거기서 끝난다.
CARET_CHARS = ("❯", ">")
# kimi 는 캐럿 줄을 상자 세로선으로 감싼다. 왼쪽 테두리를 벗겨야 캐럿이 드러난다.
BOX_LEFT_BORDER = "│"

# 줄 **중간**에 오는 캐럿 — 그 에이전트를 아는 호출부만 연다.
#
# codex 의 입력 상자 글리프는 `›`(U+203A)인데, Orca 터미널 API 는 그것을 바로 앞 경고 줄
# **꼬리에 붙여서** 준다(사람 터미널에서는 따로 보인다). 「줄 맨 앞」 규칙으로는 영영 안
# 잡히므로 codex 홉이 매번 `TUI 준비 실패(60s)` 로 죽었다.
#
# **이 규칙을 전 에이전트에 열지 않는다.** `›` 는 이 레포의 실제 문자열에도 있다
# (`시스템관리 › 권한관리` 같은 경로 표기, `DataTablePager` 의 단독 `›`) — 열어 두면 그런 줄이
# 입력 상자로 오인된다. 종전에 그렇게 짰다가 리뷰가 차단급으로 잡았다. 그래서 **누구의
# 화면인지 아는 자리에서만** 연다.
#
# codex 화면 안에도 `›` 를 담은 줄이 섞일 수 있지만, 캐럿 줄은 **마지막** 것을 고르고
# (`caret_index`) 터미널 버퍼의 tail 은 커서에서 끝나므로 입력 상자가 언제나 그 아래다.
INLINE_CARETS = {"codex": ("›",)}


def _strip_box(line: str) -> str:
    """줄 앞의 공백과 상자 왼쪽 테두리를 벗긴다."""
    stripped = line.strip()
    if stripped.startswith(BOX_LEFT_BORDER):
        stripped = stripped[len(BOX_LEFT_BORDER) :].lstrip()
    return stripped


def _has_inline_caret(line: str, caret: str) -> bool:
    """줄 어디에 있든 캐럿 + 공백(또는 줄 끝)인가 — 앞에 무엇이 붙어 와도 본다."""
    index = line.find(caret)
    while index != -1:
        rest = line[index + len(caret) :]
        if rest == "" or rest[:1].isspace():
            return True
        index = line.find(caret, index + 1)
    return False


def is_caret_line(line: str, agent: str | None = None) -> bool:
    """입력 캐럿이 있는 줄인가. `agent` 를 주면 그 에이전트의 줄-중간 캐럿까지 본다.

    캐럿 뒤 공백은 **아무 공백류나** 허용한다. claude 는 입력 상자에서 `❯` 뒤에 U+00A0
    (non-breaking space)을 쓰고 트랜스크립트 되울림에서는 보통 공백을 쓴다 — 보통 공백만
    받으면 정작 상자를 못 알아보고 되울림을 상자로 오인한다(실측으로 잡은 자리다).
    """
    body = _strip_box(line)
    for caret in CARET_CHARS:
        if body == caret:
            return True
        if body.startswith(caret) and body[len(caret) :][:1].isspace():
            return True
    return any(_has_inline_caret(line, caret) for caret in INLINE_CARETS.get(agent or "", ()))


def caret_index(lines: list[str], agent: str | None = None) -> int | None:
    """입력 상자의 캐럿 줄 인덱스 — **마지막** 캐럿 줄. 없으면 None."""
    for i in range(len(lines) - 1, -1, -1):
        if is_caret_line(lines[i], agent):
            return i
    return None


def _normalize(text: str) -> str:
    """연속 공백을 하나로 — 상자가 텍스트를 접을 때 들어가는 정렬 공백을 무시한다."""
    return " ".join(text.split())


def agent_ready(lines: list[str], agent: str | None = None) -> bool:
    """TUI 가 입력 상자를 그렸는가 = 입력을 받을 수 있는가."""
    return caret_index(lines, agent) is not None


def input_pending(lines: list[str], needle: str, agent: str | None = None) -> bool:
    """보낸 텍스트가 입력 상자에 **미제출로** 남아 있는가."""
    i = caret_index(lines, agent)
    if i is None:
        return False
    return _normalize(needle) in _normalize(lines[i])


def prompt_accepted(lines: list[str], needle: str, agent: str | None = None) -> bool:
    """보낸 텍스트가 제출됐는가 — 상자가 보이고, 그 안에 더는 없다."""
    i = caret_index(lines, agent)
    if i is None:
        return False
    return _normalize(needle) not in _normalize(lines[i])


def tail_lines(payload: str) -> list[str] | None:
    """`orca-ide terminal read --json` 출력에서 화면 줄 목록을 꺼낸다. 못 읽으면 None."""
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    tail = data.get("result", {}).get("terminal", {}).get("tail")
    if not isinstance(tail, list) or not all(isinstance(x, str) for x in tail):
        return None
    return tail


def _split_agent(argv: list[str]) -> tuple[list[str], str | None]:
    """`--agent <이름>` 을 어디에 적어도 떼어 낸다 — 나머지는 위치 인자 그대로."""
    rest: list[str] = []
    agent: str | None = None
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--agent" and index + 1 < len(argv):
            agent = argv[index + 1]
            index += 2
            continue
        if token.startswith("--agent="):
            agent = token[len("--agent=") :]
            index += 1
            continue
        rest.append(token)
        index += 1
    return rest, agent


def main(argv: list[str]) -> int:
    positional, agent = _split_agent(argv[1:])
    mode = positional[0] if positional else ""
    needle = positional[1] if len(positional) > 1 else ""
    if mode not in ("ready", "pending", "accepted") or (mode != "ready" and not needle):
        print(
            "usage: terminal_state.py [--agent <이름>] ready|pending <needle>|accepted <needle> < terminal-read.json",
            file=sys.stderr,
        )
        return 2

    lines = tail_lines(sys.stdin.read())
    if lines is None:
        print("터미널 화면을 읽을 수 없습니다 (JSON·tail 없음)", file=sys.stderr)
        return 2

    if mode == "ready":
        verdict = agent_ready(lines, agent)
    elif mode == "pending":
        verdict = input_pending(lines, needle, agent)
    else:
        verdict = prompt_accepted(lines, needle, agent)
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
