"""DI 등록 — config 가 유일한 settings 경계. 그 아래 service, 마지막에 wiring."""

from core.config import settings
from dependency_injector import containers, providers
from services.bot_agent.bot_agent_service import BotAgentService


class Container(containers.DeclarativeContainer):
    # Config
    config = providers.Object(settings)

    # Service — **Singleton 이어야 한다.** 이 서비스는 신원별 최근 세션 id 를 인스턴스 상태로
    # 들고 있어서(`_sessions`), Factory 면 요청마다 새 인스턴스가 생겨 그 기억이 매번 사라진다.
    # 그러면 `resume` 이 항상 None 이 되어 대화 이어가기가 조용히 죽는다 — 화면에는 폼 상태
    # 주입 덕에 정답이 나와 **버그가 안 보인다.** 요청 간 상태를 드는 서비스를 Singleton 으로
    # 두는 것은 이 레포의 기존 관행이다(single-agent-service·backend-service).
    bot_agent_service = providers.Singleton(BotAgentService, config=config)

    wiring_config = containers.WiringConfiguration(modules=["routers.bot_agent.bot_agent_router"])
