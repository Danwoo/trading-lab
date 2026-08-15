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

    def strategies_dir(self) -> Path:
        """설정이 비면 레포 루트의 `strategies/` — 전략 규약 §1 의 기본값과 같다."""
        if self.config.STRATEGIES_DIR:
            return Path(self.config.STRATEGIES_DIR)
        return Path(__file__).resolve().parents[3].parent / "strategies"

    def readiness(self) -> dict:
        """대화를 걸 수 있는 상태인지 — 화면이 「왜 안 되는지」를 보여줄 재료."""
        directory = self.strategies_dir()
        reasons = []
        if not self.config.ANTHROPIC_API_KEY:
            reasons.append("ANTHROPIC_API_KEY 가 설정되지 않았습니다 (.env 의 프로세스 환경변수).")
        if not directory.is_dir():
            reasons.append(f"전략 디렉터리가 없습니다: {directory}")
        return {"ready": not reasons, "reasons": reasons, "strategies_dir": str(directory)}

    async def stream(self, message: str) -> AsyncIterator[dict]:
        """대화 한 턴의 이벤트를 낸다. SSE 프레이밍은 라우터 몫이다."""
        if not message.strip():
            raise BadRequestError("메시지가 비어 있습니다.")

        state = self.readiness()
        if not state["ready"]:
            # 이유를 담은 이벤트 하나 — 화면이 빈 대화창 대신 원인을 보여준다.
            yield {"type": "unavailable", "reasons": state["reasons"]}
            return

        async for event in self._run(message, Path(state["strategies_dir"])):
            yield event

    async def _run(self, message: str, directory: Path) -> AsyncIterator[dict]:
        # import 를 여기서 하는 이유: 키가 없는 환경(CI·호스팅 모드)에서도 앱이 뜨고
        # readiness 가 답할 수 있어야 한다 — SDK 부재가 기동 실패가 되면 안 된다.
        from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, query

        options = build_options(strategies_dir=directory, max_turns=self.config.AGENT_MAX_TURNS)
        try:
            async for reply in query(prompt=message, options=options):
                if isinstance(reply, AssistantMessage):
                    for block in reply.content:
                        if isinstance(block, TextBlock):
                            yield {"type": "text", "text": block.text}
                        elif getattr(block, "name", None):
                            # 무엇을 했는지 화면에 보인다 — 판단의 근거가 숨지 않게.
                            yield {"type": "tool", "name": block.name}
                elif isinstance(reply, ResultMessage):
                    yield {"type": "result", "subtype": reply.subtype}
        except Exception:  # noqa: BLE001 — 남의 런타임이라 무엇이 터질지 모른다
            # 원본은 서버 로그에만 — 클라이언트엔 마스킹한다 (내부 경로·키가 새지 않게)
            logger.exception("봇 만들기 대화가 실패했습니다")
            yield {"type": "error", "message": "대화 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."}
