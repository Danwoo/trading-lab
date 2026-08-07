"""등록된 모든 소스의 capability 표를 모은다 — 화면이 "왜 비었는지"를 읽는 유일한 경로.

키 주입이 여기서 일어난다. 어댑터는 `settings.` 를 읽지 않으므로(MD-AD-20), 키를 아는 쪽
(`DataKeyService`)이 어댑터를 만들 때 넘긴다. `.env` 가 비어 있으면 `None` 이 넘어가고, 그래서
키가 필요한 소스가 스스로 `available=False` + 사유를 돌려준다 — 이 서비스는 그 판단을 대신하지
않는다.

**응답에 키 값도, 앞자리 몇 글자도 싣지 않는다.** 여기서 나가는 것은 「있나/없나」와 「없으면
어디서 받나」뿐이고, 그 계약은 `tests/test_data_source_key_leak.py` 가 실제 키를 꽂고 확인한다.
"""

from providers import get_provider, list_sources
from providers.base import CREDENTIAL_MISSING_HINT
from services.data_key.data_key_service import DataKeyService


class CapabilityService:
    def __init__(self, data_key_service: DataKeyService):
        self.data_key_service = data_key_service

    def list_capabilities(self, workspace_id: int | None, market: str | None = None) -> list[dict]:
        """`market` 을 주면 그 시장만. 모르는 시장을 주면 빈 목록이 나오는데, 이것은 정상이다 —
        "그 시장을 다루는 소스가 하나도 없다"가 곧 답이다."""
        rows: list[dict] = []
        for source in list_sources():
            api_key = self.data_key_service.get_key(workspace_id, source)
            provider = get_provider(source, api_key)
            for capability in provider.capabilities():
                if market and capability.market.upper() != market.upper():
                    continue
                reason = capability.reason
                if reason and CREDENTIAL_MISSING_HINT in reason:
                    # 어댑터는 "키가 없다"까지만 안다. **어디서 받아 어디에 넣는지**는 키를 아는
                    # 쪽이 붙인다 — 화면이 사유만 보고 다음 행동을 알 수 있게. 판단 근거를 상수로
                    # 두는 이유는 base.py 의 그 상수 주석에 적었다.
                    reason = f"{reason} ({self.data_key_service.unavailable_reason(source)})"
                rows.append(
                    {
                        "source": source,
                        "market": capability.market,
                        "data_kind": capability.data_kind,
                        "available": capability.available,
                        "reason": reason,
                    }
                )
        return rows
