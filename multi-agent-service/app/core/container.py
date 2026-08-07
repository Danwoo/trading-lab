from clients.llm.llm_client import get_evaluator_llm, get_generator_llm, get_planner_llm, get_router_llm
from clients.mcp.mcp_client import get_mcp_client
from core.config import settings
from core.database import get_multi_agent_sql_client
from dependency_injector import containers, providers
from repositories.chat_history.chat_history_repository import ChatHistoryRepository
from services.agent.agent_service import AgentService
from services.agent.rate_limit import RateLimiter, StreamSemaphore
from services.agent.response_cache import ResponseCache


class Container(containers.DeclarativeContainer):
    # Config
    config = providers.Object(settings)

    # Client
    mcp_client = providers.Singleton(get_mcp_client, config)
    router_llm = providers.Singleton(get_router_llm, config)
    planner_llm = providers.Singleton(get_planner_llm, config)
    generator_llm = providers.Singleton(get_generator_llm, config)
    evaluator_llm = providers.Singleton(get_evaluator_llm, config)
    sql_client = providers.Singleton(get_multi_agent_sql_client, config)

    # Repository
    chat_history_repository = providers.Factory(
        ChatHistoryRepository, sql_client=sql_client, max_turns=settings.MA_HISTORY_MAX_TURNS
    )

    # Service — 그래프 상태 보유(initialize 1회) + 레이트리밋/캐시도 프로세스 단일 상태라 Singleton
    response_cache = providers.Singleton(ResponseCache, config)
    rate_limiter = providers.Singleton(RateLimiter, config)
    stream_semaphore = providers.Singleton(StreamSemaphore, config)
    agent_service = providers.Singleton(
        AgentService,
        config=config,
        mcp_client=mcp_client,
        router_llm=router_llm,
        planner_llm=planner_llm,
        generator_llm=generator_llm,
        evaluator_llm=evaluator_llm,
        chat_history_repository=chat_history_repository,
        response_cache=response_cache,
    )

    wiring_config = containers.WiringConfiguration(modules=["routers.agent.agent_router"])
