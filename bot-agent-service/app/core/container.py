"""DI 등록 — config 가 유일한 settings 경계. 그 아래 service, 마지막에 wiring."""

from core.config import settings
from dependency_injector import containers, providers
from services.bot_agent.bot_agent_service import BotAgentService


class Container(containers.DeclarativeContainer):
    # Config
    config = providers.Object(settings)

    # Service — 에이전트 옵션은 매 턴 새로 만든다(상태 없음). 그래서 Factory 로 충분하다.
    bot_agent_service = providers.Factory(BotAgentService, config=config)

    wiring_config = containers.WiringConfiguration(modules=["routers.bot_agent.bot_agent_router"])
