from clients.disclosure.disclosure_client import DisclosureClient
from core.config import settings
from dependency_injector import containers, providers
from repositories.disclosure.disclosure_repository import DisclosureRepository
from services.disclosure.disclosure_service import DisclosureService


class Container(containers.DeclarativeContainer):
    # Config
    config = providers.Object(settings)

    # Client (외부 연결 — DART 전자공시 OpenAPI / mock 폴백)
    disclosure_client = providers.Singleton(DisclosureClient, config)

    # Repository (disclosure = 외부 공시·재무 데이터 store, 연결 주입)
    disclosure_repository = providers.Factory(DisclosureRepository, disclosure_client=disclosure_client)

    # Service (repository 주입)
    disclosure_service = providers.Factory(DisclosureService, disclosure_repository=disclosure_repository)

    wiring_config = containers.WiringConfiguration(modules=["routers.disclosure.disclosure_router"])
