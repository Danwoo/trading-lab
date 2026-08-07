from clients.mcp.mcp_client import call_mcp_tool
from core.auth_context import require_workspace_id, set_auth_context
from core.exceptions import ConflictError, NotFoundError, ServiceUnavailableError
from core.logger import logger
from langchain_mcp_adapters.client import MultiServerMCPClient
from repositories.scheduler.scheduler_repository import SchedulerRepository
from services.report.activity_report_service import ActivityReportService


class SchedulerService:
    def __init__(
        self,
        scheduler_repository: SchedulerRepository,
        activity_report_service: ActivityReportService,
        mcp_client: MultiServerMCPClient,
    ):
        self.scheduler_repository = scheduler_repository
        self.activity_report_service = activity_report_service
        self.mcp_client = mcp_client

    # ── Scheduler (master) — 요청 경로는 workspace_id 로 테넌트 스코핑 ──────────
    def select_scheduler_list(self, args: dict) -> tuple[list, int]:
        args["workspace_id"] = require_workspace_id()
        return self.scheduler_repository.select_scheduler_list(args)

    def select_scheduler(self, args: dict) -> dict:
        args["workspace_id"] = require_workspace_id()
        scheduler = self.scheduler_repository.select_scheduler(args)
        if not scheduler:
            raise NotFoundError("스케줄러를 찾을 수 없습니다.")
        return scheduler

    def insert_scheduler(self, args: dict) -> tuple:
        args["workspace_id"] = require_workspace_id()
        if self.scheduler_repository.select_scheduler(args):
            raise ConflictError("이미 존재하는 스케줄러입니다.")
        return self.scheduler_repository.insert_scheduler(args)

    def update_scheduler(self, args: dict) -> None:
        args["workspace_id"] = require_workspace_id()
        if not self.scheduler_repository.select_scheduler(args):
            raise NotFoundError("스케줄러를 찾을 수 없습니다.")
        self.scheduler_repository.update_scheduler(args)

    def delete_scheduler(self, args: dict) -> None:
        args["workspace_id"] = require_workspace_id()
        if not self.scheduler_repository.select_scheduler(args):
            raise NotFoundError("스케줄러를 찾을 수 없습니다.")
        self.scheduler_repository.delete_scheduler(args)

    # ── SchedulerMember (detail) ────────────────────────────────────────
    def select_member_list(self, args: dict) -> tuple[list, int]:
        args["workspace_id"] = require_workspace_id()
        return self.scheduler_repository.select_member_list(args)

    async def insert_member(self, args: dict) -> None:
        args["workspace_id"] = require_workspace_id()
        # 멤버는 소유한 스케줄러에만 등록 — 타 테넌트 스케줄러로의 멤버 주입 차단
        if not self.scheduler_repository.select_scheduler(args):
            raise NotFoundError("스케줄러를 찾을 수 없습니다.")
        if self.scheduler_repository.select_member(args):
            raise ConflictError("이미 등록된 멤버입니다.")
        # 계좌 소유·존재 검증 (#115) — 미소유·미존재 account_id 를 등록하면 발송 시점에 portfolio-mcp 가
        # 영구 found=False 를 돌려 무음 실패로 남고, 타 테넌트 계좌가 스케줄러에 박힌다. 등록 시점에
        # 요청자 테넌트 소유를 확인해 즉시 거절한다.
        await self._assert_account_owned(args["account_id"])
        self.scheduler_repository.insert_member(args)

    async def _assert_account_owned(self, account_id: str) -> None:
        """account_id 가 요청자 테넌트 소유·존재 계좌인지 portfolio-mcp 로 확인 (fail-closed).

        on-behalf 서비스 토큰(요청자 workspace_id)으로 portfolio_list_accounts 를 호출하면 portfolio-mcp 가
        요청자 테넌트 소유 계좌만 반환한다. 미존재·타 테넌트 account_id 는 모두 목록에 없어 동일하게 거절 —
        어느 쪽인지 밝히지 않아 존재 오라클을 노출하지 않는다(portfolio-mcp found=False 통합과 동형).
        검증 자체가 불가하면(portfolio-mcp 장애) 미검증 계좌를 통과시키지 않고 등록을 막는다.
        """
        try:
            result = await call_mcp_tool(self.mcp_client, "portfolio_list_accounts")
        except Exception as e:
            logger.warning("[멤버등록] 계좌 소유 검증 실패 — portfolio-mcp 연결/응답 오류: %s", e)
            raise ServiceUnavailableError(
                "계좌 확인 서비스에 연결할 수 없어 등록을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요."
            ) from e
        owned_ids = {a.get("account_id") for a in result.get("items", [])}
        if account_id not in owned_ids:
            logger.warning("[멤버등록] 미소유·미존재 계좌 등록 거절 — account_id=%s", account_id)
            raise NotFoundError(
                "등록하려는 계좌를 찾을 수 없습니다. 계좌 번호가 정확한지, 접근 권한이 있는지 확인해 주세요."
            )

    def delete_member(self, args: dict) -> None:
        args["workspace_id"] = require_workspace_id()
        if not self.scheduler_repository.select_member(args):
            raise NotFoundError("멤버를 찾을 수 없습니다.")
        self.scheduler_repository.delete_member(args)

    def members_for_run(self, scheduler_id: str) -> list[dict]:
        self.select_scheduler({"scheduler_id": scheduler_id})  # 소유 검증 (없으면 NotFoundError)
        return self.scheduler_repository.select_members_for_job(scheduler_id)

    # ── 시스템 경로 (요청 밖 — 부팅/cron) — workspace_id 미주입, 전 테넌트 대상 ──
    def select_active_schedulers(self) -> list[dict]:
        return self.scheduler_repository.select_active_schedulers()

    async def run(self, scheduler_id: str) -> None:
        try:
            scheduler = self.scheduler_repository.select_scheduler_for_job(scheduler_id)
            if not scheduler:
                return
            members = self.scheduler_repository.select_members_for_job(scheduler_id)
            if not members:
                return
            # cron 은 요청 밖이라 신원 컨텍스트가 비어 있다 — 하류 MCP on-behalf 토큰이 스케줄러 소속
            # 워크스페이스로 스코핑되도록 workspace_id 를 컨텍스트에 실어 준다 (없으면 portfolio-mcp 가 fail-closed).
            set_auth_context(user_id=None, role=None, workspace_id=scheduler["workspace_id"])
            since, until = self.activity_report_service.period(scheduler["period_weeks"])
            async for msg in self.activity_report_service.generate_for(members, since, until):
                logger.info(f"[스케줄러 {scheduler_id}] {msg}")
        except Exception as e:
            logger.error(f"[스케줄러 {scheduler_id}] 실패: {e}")
