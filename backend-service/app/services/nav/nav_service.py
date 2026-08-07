# services/nav/nav_service.py
from core.auth_context import require_workspace_id
from repositories.nav.nav_repository import NavRepository


class NavService:
    def __init__(self, nav_repository: NavRepository):
        self.nav_repository = nav_repository

    def record_snapshot(self, snapshot: dict, source_message_id: int) -> None:
        """producer 가 메시지 큐에 발행한 NAV 스냅샷을 시계열 테이블에 기록 (consumer dispatch 경유).

        백그라운드 시스템 write — 테넌트는 producer 가 스냅샷에 실어 보낸 workspace_id 를 사용한다.
        source_message_id 는 at-least-once 재소비의 중복 적재를 막는 멱등키(유발 메시지 id)다.

        **구 페이로드 폴백**: 배포 시점에 큐에 남아 있던 메시지는 리네임 전 키(`company_id`)로 실려
        있다. 폴백이 없으면 KeyError → 재시도 소진 → dead-letter 로 조용히 유실된다. in-flight
        데이터의 하위호환이라 JWT 검증측 폴백과 성격이 같다 — 큐에서 구 페이로드가 사라지면 지운다.
        """
        workspace_id = snapshot.get("workspace_id")
        if workspace_id is None:
            workspace_id = snapshot.get("company_id")
        if workspace_id is None:
            raise ValueError("nav 스냅샷에 테넌트(workspace_id)가 없습니다")
        self.nav_repository.insert_nav(
            {
                "workspace_id": workspace_id,
                "source_message_id": source_message_id,
                "nav": snapshot.get("nav"),
                "benchmark": snapshot.get("benchmark"),
                "daily_return": snapshot.get("daily_return"),
                "drawdown": snapshot.get("drawdown"),
                "reg_id": "system",
            }
        )

    def select_history(self, minutes: int) -> tuple[list[dict], int]:
        workspace_id = require_workspace_id()
        items = self.nav_repository.select_history({"minutes": minutes, "workspace_id": workspace_id})
        return items, len(items)
