from core.auth_context import require_workspace_id
from core.exceptions import ConflictError, NotFoundError
from repositories.watchlist.watchlist_repository import WatchlistRepository


class WatchlistService:
    def __init__(self, watchlist_repository: WatchlistRepository):
        self.watchlist_repository = watchlist_repository

    def select_watchlist_list(self, args: dict) -> tuple[list, int]:
        """
        관심종목 리스트를 조회하는 메소드
        """
        args["workspace_id"] = require_workspace_id()
        return self.watchlist_repository.select_watchlist_list(args)

    def select_watchlist(self, args: dict) -> dict:
        """
        관심종목 항목을 조회하는 메소드
        """
        args["workspace_id"] = require_workspace_id()
        watchlist = self.watchlist_repository.select_watchlist(args)
        if not watchlist:
            raise NotFoundError("데이터를 찾을 수 없습니다.")
        return watchlist

    def insert_watchlist(self, args: dict) -> tuple:
        """
        관심종목 항목을 등록하는 메소드
        """
        args["workspace_id"] = require_workspace_id()
        if self.watchlist_repository.select_watchlist(args):
            raise ConflictError("이미 존재하는 데이터입니다.")
        return self.watchlist_repository.insert_watchlist(args)

    def update_watchlist(self, args: dict) -> None:
        """
        관심종목 항목을 수정하는 메소드
        """
        args["workspace_id"] = require_workspace_id()
        if not self.watchlist_repository.select_watchlist(args):
            raise NotFoundError("데이터를 찾을 수 없습니다.")
        self.watchlist_repository.update_watchlist(args)

    def delete_watchlist(self, args: dict) -> None:
        """
        관심종목 항목을 삭제하는 메소드
        """
        args["workspace_id"] = require_workspace_id()
        if not self.watchlist_repository.select_watchlist(args):
            raise NotFoundError("데이터를 찾을 수 없습니다.")
        self.watchlist_repository.delete_watchlist(args)
