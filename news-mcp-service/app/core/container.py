from clients.news.news_client import NewsClient
from core.config import settings
from dependency_injector import containers, providers
from repositories.news.news_repository import NewsRepository
from services.news.news_service import NewsService


class Container(containers.DeclarativeContainer):
    # Config
    config = providers.Object(settings)

    # Client (외부 연결 — 금융 뉴스 데이터 소스, 기본 인메모리 목업)
    news_client = providers.Singleton(NewsClient, config)

    # Repository (news = 외부 검색 store, 연결 주입)
    news_repository = providers.Factory(NewsRepository, news_client=news_client)

    # Service (repository 주입)
    news_service = providers.Factory(NewsService, news_repository=news_repository)

    router_modules = ["routers.news.news_router"]
    wiring_config = containers.WiringConfiguration(modules=router_modules)
