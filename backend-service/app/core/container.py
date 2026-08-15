from clients.doc_search.doc_search_client import DocSearchClient
from clients.file.sftp_client import SftpClient
from clients.llm.llm_client import get_chat_client, get_llm_client
from clients.mail.mail_client import MailClient
from clients.mcp.mcp_client import get_mcp_client
from core.config import settings
from core.database import get_backend_sql_client
from dependency_injector import containers, providers
from modules import WIRING_MODULES

# Repository
from repositories.bar.bar_repository import BarRepository
from repositories.bot.bot_repository import BotRepository
from repositories.file.file_repository import FileRepository
from repositories.file.sftp_file_repository import SftpFileRepository
from repositories.ingest.ingest_repository import IngestRepository
from repositories.message_queue.message_queue_repository import MessageQueueRepository
from repositories.nav.nav_repository import NavRepository
from repositories.portfolio.portfolio_repository import PortfolioRepository
from repositories.research_document.research_document_repository import ResearchDocumentRepository
from repositories.scheduler.scheduler_repository import SchedulerRepository
from repositories.watchlist.watchlist_repository import WatchlistRepository

# Service
from services.bar.bar_service import BarService
from services.bot.bot_service import BotService
from services.capability.capability_service import CapabilityService
from services.chat.portfolio_chat_service import PortfolioChatService
from services.data_key.data_key_service import DataKeyService
from services.file.file_service import FileService
from services.ingest.ingest_service import IngestService
from services.message_queue.message_queue_service import MessageQueueService
from services.nav.nav_service import NavService
from services.portfolio.portfolio_service import PortfolioService
from services.quote.quote_batch_service import QuoteBatchService
from services.report.activity_report_service import ActivityReportService
from services.research_document.research_document_service import ResearchDocumentService
from services.scheduler.scheduler_service import SchedulerService
from services.watchlist.watchlist_service import WatchlistService


class Container(containers.DeclarativeContainer):
    # Config
    config = providers.Object(settings)

    # Database
    backend_sql_client = providers.Singleton(get_backend_sql_client, config)

    # Client
    doc_search_client = providers.Singleton(DocSearchClient, config)
    sftp_client = providers.Singleton(SftpClient, config)
    mcp_client = providers.Singleton(get_mcp_client, config)
    chat_client = providers.Singleton(get_chat_client, config)
    llm_client = providers.Singleton(get_llm_client, config)
    mail_client = providers.Singleton(MailClient, config)

    # Repository
    portfolio_repository = providers.Factory(PortfolioRepository, sql_client=backend_sql_client)
    watchlist_repository = providers.Factory(WatchlistRepository, sql_client=backend_sql_client)
    nav_repository = providers.Factory(NavRepository, sql_client=backend_sql_client)
    message_queue_repository = providers.Factory(MessageQueueRepository, sql_client=backend_sql_client)
    research_document_repository = providers.Factory(ResearchDocumentRepository, sql_client=backend_sql_client)
    file_repository = providers.Factory(FileRepository, sql_client=backend_sql_client)
    sftp_file_repository = providers.Factory(SftpFileRepository, sftp_client=sftp_client)
    scheduler_repository = providers.Factory(SchedulerRepository, sql_client=backend_sql_client)
    # 시세 — 캔들 조회(갈래 1)와 적재. 둘 다 workspace 스코프가 없다 (시세는 전역 공용, M2-AD-10).
    bar_repository = providers.Factory(BarRepository, sql_client=backend_sql_client)
    ingest_repository = providers.Factory(IngestRepository, sql_client=backend_sql_client)
    bot_repository = providers.Factory(BotRepository, sql_client=backend_sql_client)

    # Service
    file_service = providers.Factory(FileService, file_repository=file_repository, file_store=sftp_file_repository)
    portfolio_service = providers.Factory(PortfolioService, portfolio_repository=portfolio_repository)
    watchlist_service = providers.Factory(WatchlistService, watchlist_repository=watchlist_repository)
    bot_service = providers.Factory(BotService, bot_repository=bot_repository)
    nav_service = providers.Factory(NavService, nav_repository=nav_repository)
    message_queue_service = providers.Factory(
        MessageQueueService, message_queue_repository=message_queue_repository, nav_service=nav_service
    )
    research_document_service = providers.Factory(
        ResearchDocumentService,
        research_document_repository=research_document_repository,
        file_service=file_service,
        doc_search_client=doc_search_client,
    )
    activity_report_service = providers.Factory(
        ActivityReportService,
        mcp_client=mcp_client,
        summarize_client=llm_client,
        mail_client=mail_client,
    )
    scheduler_service = providers.Factory(
        SchedulerService,
        scheduler_repository=scheduler_repository,
        activity_report_service=activity_report_service,
        mcp_client=mcp_client,
    )
    # 데이터 소스 키 — `.env` 를 읽어 어댑터에 넘기는 유일한 자리 (2026-08-07 리드 결정).
    data_key_service = providers.Factory(DataKeyService, config=config)
    capability_service = providers.Factory(CapabilityService, data_key_service=data_key_service)
    # 갈래 1 — 차트·백테스트·봇이 쓰는 적재본 읽기. **provider 가 이 배선에 없다** (MD-AD-19):
    # 차트가 소스를 직접 부를 통로가 생성자에 존재하지 않는다.
    bar_service = providers.Factory(BarService, bar_repository=bar_repository, capability_service=capability_service)
    ingest_service = providers.Factory(
        IngestService, ingest_repository=ingest_repository, data_key_service=data_key_service
    )
    # 갈래 3 — 일괄 조회 + TTL 캐시. 구독 API 를 갖지 않는다 (MD-AD-19).
    quote_batch_service = providers.Singleton(QuoteBatchService, data_key_service=data_key_service)
    portfolio_chat_service = providers.Factory(
        PortfolioChatService,
        mcp_client=mcp_client,
        chat_client=chat_client,
    )

    # Wiring — 라우터·매니저 목록의 SoT 는 app/modules.py
    wiring_config = containers.WiringConfiguration(modules=WIRING_MODULES)
