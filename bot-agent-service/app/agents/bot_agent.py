"""봇 만들기 대화의 에이전트 — Claude Agent SDK 옵션을 한 곳에서 만든다.

**이 파일이 「에이전트에게 무엇을 허용하는가」의 정본이다.** 이슈 #150 B2 의 완료 조건 중
「그 턴이 무엇을 할 수 있는지 경계가 문서에 적힌다」가 여기와 `tests/test_agent_boundary.py`
두 곳으로 고정된다 — 글로만 적으면 코드가 조용히 넓어진다.

권한이 평가되는 순서는 여섯 단계다 (훅 → deny → ask → 권한 모드 → allow → `can_use_tool`).
여기서 틀리기 쉬운 셋:

- `allowed_tools` 는 **제한이 아니라 자동승인 목록**이다. 목록에 없는 도구도 여전히 존재하고
  권한 모드로 흘러간다 — 그래서 `dontAsk` 와 짝을 지어야 「목록 밖 = 거부」가 된다.
- `bypassPermissions` 는 `allowed_tools` 로 못 좁힌다(전부 승인). 이 서비스는 쓰지 않는다.
- 자동승인된 도구는 `can_use_tool` 콜백에 오지 않는다 — 사람 게이트를 콜백으로 짜면 조용히
  우회된다.
"""

from functools import partial
from pathlib import Path

from agents.proposal_tool import PROPOSAL_TOOL_NAME
from agents.tool_scope import scope_hook
from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

# 이 목록은 **자동승인**이고 경로를 좁히지 않는다 — 경로 스코프는 `tool_scope.py` 의 PreToolUse
# 훅이 건다. 둘을 함께 봐야 경계가 완성된다 (PR #154 독립 리뷰가 잡은 결함: bare name 허용은
# `cwd` 와 무관하게 절대경로·`..` 로 밖을 읽는다).
# 지금 범위(M2)에서 에이전트가 하는 일은 **대화가 폼을 채우는 것**이다. 값을 내놓는 일이라
# 파일 쓰기도 셸도 필요 없다 — 전략 파일 생성(봇-전략-모델 §6)은 백테스트에 물려 있어 다음 베팅이다.
ALLOWED_TOOLS = ["Read", "Glob", "Grep"]

# 폼을 채우는 통로 하나 — in-process MCP 도구다(`proposal_tool.py`). 이름이 `mcp__<서버>__<도구>`
# 로 붙으므로 허용 목록에도 그 이름으로 적는다. 경로 스코프 대상이 아니다(파일을 안 만진다).
PROPOSAL_TOOL_FULL_NAME = f"mcp__bot_form__{PROPOSAL_TOOL_NAME}"

# bare name 으로 적으면 도구 정의가 요청에서 **제거**돼 모델이 시도조차 못 한다.
DISALLOWED_TOOLS = ["Bash", "Write", "Edit", "NotebookEdit", "WebSearch", "WebFetch", "Task"]

# 미승인은 프롬프트가 아니라 **거부**. 헤드리스에 맞고, 실수가 통과되지 않는다.
PERMISSION_MODE = "dontAsk"

# 사용자·프로젝트 설정을 안 읽는다 — 안 그러면 리드의 `~/.claude` 와 레포 `.claude/` 의
# 훅·플러그인·MCP 서버가 딸려 들어와 이 파일이 선언한 경계 밖이 열린다.
SETTING_SOURCES: list = []

SYSTEM_PROMPT = """\
당신은 투자 봇을 함께 만드는 조력자입니다. 사용자의 말을 봇 설정으로 옮기는 것이 일입니다.

지킬 것 넷 (실험대 스펙 §8.6.3):

1. 제안에는 그 결과를 함께 적습니다. "-7%를 권합니다" 가 아니라 "-7%면 후보가 몇 종목이 되고
   매매가 얼마나 잦아집니다" 로 말합니다.
2. 판정하지 않습니다. "이게 좋습니다" 가 아니라 "이렇게 하면 이렇게 됩니다" 입니다.
   무엇을 고를지는 사용자가 정합니다.
3. 성과 숫자를 지어내지 않습니다. 백테스트 엔진이 아직 없어 과거 수익률·낙폭·승률을 말할 수
   없습니다. 모르면 "아직 검증 단계가 없어 그 숫자는 못 드립니다" 라고 말합니다.
4. 값을 채울 때는 그 값이 어느 파라미터의 것인지 이름으로 밝힙니다.
5. **값을 정했으면 `propose_settings` 도구를 부릅니다.** 사용자의 폼은 그 호출로만 채워지고,
   말로만 적은 값은 화면에 반영되지 않습니다. 도구를 부른 뒤에는 무엇을 채웠는지 한 줄로 알립니다.

전략은 파일로 선언돼 있고, 각 전략이 조절 가능한 파라미터와 그 범위를 스스로 선언합니다.
범위 밖의 값을 제안하지 마십시오.\
"""


def build_options(*, strategies_dir: Path | str, max_turns: int, proposal_server=None) -> ClaudeAgentOptions:
    """봇 만들기 대화 한 번에 쓸 옵션.

    경계는 **셋이 겹쳐** 만들어진다:

    1. `disallowed_tools` — 쓰기·실행 도구는 정의 자체가 요청에서 빠진다(모델이 시도조차 못 한다).
    2. `permission_mode="dontAsk"` — 자동승인 목록 밖은 프롬프트가 아니라 거부다.
    3. **PreToolUse 훅** — 허용된 읽기 도구가 전략 디렉터리 밖을 가리키면 거부한다.

    `cwd` 는 3번의 기준점일 뿐이다. `cwd` 만으로는 접근 범위가 안 좁혀진다 — SDK 가
    *"Filesystem read restrictions: Use Read deny rules"* 라고 적는 이유다.
    """
    root = Path(strategies_dir).resolve()
    return ClaudeAgentOptions(
        allowed_tools=[*ALLOWED_TOOLS, PROPOSAL_TOOL_FULL_NAME],
        mcp_servers={"bot_form": proposal_server} if proposal_server is not None else {},
        disallowed_tools=list(DISALLOWED_TOOLS),
        permission_mode=PERMISSION_MODE,
        setting_sources=list(SETTING_SOURCES),
        system_prompt=SYSTEM_PROMPT,
        cwd=str(root),
        max_turns=max_turns,
        hooks={"PreToolUse": [HookMatcher(hooks=[partial(scope_hook, root=root)])]},
    )
