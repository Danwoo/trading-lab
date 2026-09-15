from core.auth_context import require_workspace_id
from core.exceptions import ConflictError, NotFoundError
from repositories.portfolio.portfolio_repository import PortfolioRepository


class PortfolioService:
    def __init__(self, portfolio_repository: PortfolioRepository):
        self.portfolio_repository = portfolio_repository

    # ── Portfolio (master) ─────────────────────────────────────────────
    def select_portfolio_list(self, args: dict) -> tuple[list, int]:
        args["workspace_id"] = require_workspace_id()
        return self.portfolio_repository.select_portfolio_list(args)

    def select_portfolio(self, args: dict) -> dict:
        args["workspace_id"] = require_workspace_id()
        portfolio = self.portfolio_repository.select_portfolio(args)
        if not portfolio:
            raise NotFoundError("데이터를 찾을 수 없습니다.")
        return portfolio

    def insert_portfolio(self, args: dict) -> tuple:
        args["workspace_id"] = require_workspace_id()
        if self.portfolio_repository.select_portfolio(args):
            raise ConflictError("이미 존재하는 데이터입니다.")
        return self.portfolio_repository.insert_portfolio(args)

    def update_portfolio(self, args: dict) -> None:
        args["workspace_id"] = require_workspace_id()
        if not self.portfolio_repository.select_portfolio(args):
            raise NotFoundError("데이터를 찾을 수 없습니다.")
        self.portfolio_repository.update_portfolio(args)

    def delete_portfolio(self, args: dict) -> None:
        args["workspace_id"] = require_workspace_id()
        if not self.portfolio_repository.select_portfolio(args):
            raise NotFoundError("데이터를 찾을 수 없습니다.")
        self.portfolio_repository.delete_portfolio(args)

    # ── Holding (detail) ───────────────────────────────────────────────
    def select_holding_list(self, args: dict) -> tuple[list, int]:
        args["workspace_id"] = require_workspace_id()
        return self.portfolio_repository.select_holding_list(args)

    def select_holding(self, args: dict) -> dict:
        args["workspace_id"] = require_workspace_id()
        holding = self.portfolio_repository.select_holding(args)
        if not holding:
            raise NotFoundError("데이터를 찾을 수 없습니다.")
        return holding

    def insert_holding(self, args: dict) -> tuple:
        args["workspace_id"] = require_workspace_id()
        # 저장소에 FK 가 없다 — 여기서 안 막으면 부모 없는 보유종목이 남고 API 로 지울 수도 없다.
        if not self.portfolio_repository.select_portfolio(args):
            raise NotFoundError("포트폴리오를 찾을 수 없습니다.")
        if self.portfolio_repository.select_holding(args):
            raise ConflictError("이미 존재하는 데이터입니다.")
        return self.portfolio_repository.insert_holding(args)

    def update_holding(self, args: dict) -> None:
        args["workspace_id"] = require_workspace_id()
        if not self.portfolio_repository.select_holding(args):
            raise NotFoundError("데이터를 찾을 수 없습니다.")
        self.portfolio_repository.update_holding(args)

    def delete_holding(self, args: dict) -> None:
        args["workspace_id"] = require_workspace_id()
        if not self.portfolio_repository.select_holding(args):
            raise NotFoundError("데이터를 찾을 수 없습니다.")
        self.portfolio_repository.delete_holding(args)
