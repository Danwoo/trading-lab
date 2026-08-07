# ── [가이드 (DI)] core/container.py — DI 등록 (config→client→service→wiring) ──
# 무엇: config 가 유일 settings 경계. 그 아래 mcp_client·llm(외부타입 → get_* 팩토리), chat_service.
# 복사 후: 도메인 service provider + wiring 모듈 경로.
# 함정: chat_service 는 에이전트 상태(tool·agent)를 보유하므로 Singleton(요청마다 재빌드 방지) ·
#   외부타입(MultiServerMCPClient·ChatOpenAI)은 get_* 팩토리로 등록 · 새 라우터는 wiring modules 에 추가
#   (누락 시 @inject 가 Provide 마커를 실제 객체로 못 바꾼다). 상세: CLAUDE.md "DI 등록".

from clients.llm.llm_client import get_chat_client
from clients.mcp.mcp_client import get_mcp_client
from core.config import settings
from dependency_injector import containers, providers
from services.chat.chat_service import ChatService


class Container(containers.DeclarativeContainer):
    # Config
    config = providers.Object(settings)

    # Client (외부타입 → get_* 팩토리)
    mcp_client = providers.Singleton(get_mcp_client, config)
    llm = providers.Singleton(get_chat_client, config)

    # Service (에이전트 상태 보유 → Singleton)
    chat_service = providers.Singleton(ChatService, mcp_client=mcp_client, llm=llm)

    wiring_config = containers.WiringConfiguration(modules=["routers.chat.chat_router"])
