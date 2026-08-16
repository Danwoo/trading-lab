"""봇 만들기 대화 — Agent SDK 를 태워 이벤트를 낸다.

**키가 없으면 시작하지 않는다.** 조용히 빈 응답을 흘리면 「대화가 안 붙었다」와 「모델이 할 말이
없다」가 구분되지 않는다 — 이유를 담은 이벤트 하나를 내고 끝낸다. 이 레포의 「소스 없는 패널은
이유와 함께 빔」과 같은 규율이다.
"""

from collections.abc import AsyncIterator
from pathlib import Path

from agents.bot_agent import build_options
from core.exceptions import BadRequestError
from core.logger import logger


class BotAgentService:
    def __init__(self, config):
        self.config = config
        # 신원 → 최근 세션 id. **클라이언트가 세션 id 를 못 정하게** 서버가 들고 있는다 —
        # id 를 받으면 남의 것을 넣어 남의 대화를 이어받을 수 있다. 로컬 배포 모드 전용
        # 단일 프로세스라 메모리로 충분하고, 프로세스가 죽으면 대화가 새로 시작될 뿐이다.
        self._sessions: dict[str, str] = {}

    def strategies_dir(self) -> Path:
        """설정이 비면 레포 루트의 `strategies/` — 전략 규약 §1 의 기본값과 같다."""
        if self.config.STRATEGIES_DIR:
            return Path(self.config.STRATEGIES_DIR)
        return Path(__file__).resolve().parents[3].parent / "strategies"

    def readiness(self) -> dict:
        """대화를 걸 수 있는 상태인지 — 화면이 「왜 안 되는지」를 보여줄 재료."""
        directory = self.strategies_dir()
        reasons = []
        # 공백만 든 값은 「설정됨」이 아니다 — truthy 라 그냥 통과하면 화면이 「쓸 수 있다」고
        # 답하는데 실제로는 인증 수단이 없다.
        if not self.config.ANTHROPIC_API_KEY.strip():
            reasons.append("ANTHROPIC_API_KEY 가 설정되지 않았습니다 (.env 의 프로세스 환경변수).")
        if not directory.is_dir():
            reasons.append(f"전략 디렉터리가 없습니다: {directory}")
        return {"ready": not reasons, "reasons": reasons, "strategies_dir": str(directory)}

    @staticmethod
    def _with_form_state(message: str, form) -> str:
        """지금 폼 상태를 말머리에 붙인다.

        붙이는 이유: 에이전트는 자기가 제안한 값만 기억하고 **사용자가 손으로 고친 값은 모른다.**
        모르면 「나머지는 그대로 뒀습니다」 같은 문장이 사실과 어긋난다(실측으로 겪었다).
        폼이 진실이고 대화는 그것을 읽는다.
        """
        if form is None:
            return message
        parts = []
        if form.strategy_key:
            parts.append(f"전략={form.strategy_key}")
        parts.extend(f"{name}={value}" for name, value in form.params.items())
        if not parts:
            return message
        return f"[지금 폼에 들어 있는 값 — 사용자가 직접 고친 것이 포함돼 있다: {', '.join(parts)}]\n\n{message}"

    async def stream(
        self, message: str, *, caller: str | None = None, reset: bool = False, form=None
    ) -> AsyncIterator[dict]:
        """대화 한 턴의 이벤트를 낸다. SSE 프레이밍은 라우터 몫이다.

        `caller` 가 있으면 그 신원의 직전 세션을 이어간다 — 「그럼 손절은 5%로」가 통하려면
        이전 턴을 알아야 한다. `reset` 이면 기억을 버리고 새로 시작한다.
        """
        if not message.strip():
            raise BadRequestError("메시지가 비어 있습니다.")

        key = caller or "anonymous"
        if reset:
            self._sessions.pop(key, None)

        state = self.readiness()
        if not state["ready"]:
            # 이유를 담은 이벤트 하나 — 화면이 빈 대화창 대신 원인을 보여준다.
            yield {"type": "unavailable", "reasons": state["reasons"]}
            return

        async for event in self._run(self._with_form_state(message, form), Path(state["strategies_dir"]), key):
            yield event

    async def _run(self, message: str, directory: Path, key: str) -> AsyncIterator[dict]:
        # import 를 여기서 하는 이유: 키가 없는 환경(CI·호스팅 모드)에서도 앱이 뜨고
        # readiness 가 답할 수 있어야 한다 — SDK 부재가 기동 실패가 되면 안 된다.
        from agents.proposal_tool import build_proposal_server
        from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, query

        # 도구가 부른 제안을 담아 두고 메시지 사이사이에 흘린다 — 도구 호출은 SDK 안에서
        # 일어나므로 이 큐가 그것을 스트림으로 옮기는 유일한 통로다.
        proposals: list[dict] = []
        options = build_options(
            strategies_dir=directory,
            max_turns=self.config.AGENT_MAX_TURNS,
            api_key=self.config.ANTHROPIC_API_KEY,
            proposal_server=build_proposal_server(proposals.append),
            resume=self._sessions.get(key),
        )
        try:
            async for reply in query(prompt=message, options=options):
                while proposals:
                    yield proposals.pop(0)
                if isinstance(reply, AssistantMessage):
                    for block in reply.content:
                        if isinstance(block, TextBlock):
                            yield {"type": "text", "text": block.text}
                        elif getattr(block, "name", None):
                            # 무엇을 했는지 화면에 보인다 — 판단의 근거가 숨지 않게.
                            yield {"type": "tool", "name": block.name}
                elif isinstance(reply, ResultMessage):
                    while proposals:
                        yield proposals.pop(0)
                    # 다음 턴이 이어붙을 자리 — 세션 id 는 **밖으로 내보내지 않는다**(남이 이어받는 손잡이가 된다).
                    if getattr(reply, "session_id", None):
                        self._sessions[key] = reply.session_id
                    yield {"type": "result", "subtype": reply.subtype}
        except Exception:  # noqa: BLE001 — 남의 런타임이라 무엇이 터질지 모른다
            # 이어가기가 실패의 원인일 수 있다(세션 파일이 사라졌거나 손상). 기억을 버려
            # 다음 턴이 새 대화로 되살아나게 한다 — 안 그러면 영영 같은 오류가 반복된다.
            self._sessions.pop(key, None)
            # 원본은 서버 로그에만 — 클라이언트엔 마스킹한다 (내부 경로·키가 새지 않게)
            logger.exception("봇 만들기 대화가 실패했습니다")
            yield {"type": "error", "message": "대화 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."}
