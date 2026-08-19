"""capability 조회 스키마 — "이 패널이 왜 비어 있나"가 화면 하드코딩이 아니라 데이터가 되는 표.

FR-021 이 요구하는 "해당 시장은 제공되지 않음"은 프론트의 정적 매트릭스로도 흉내 낼 수 있지만,
그러면 **키를 넣었을 때 화면이 저절로 열리지 않는다** — 키 유무는 런타임 상태이므로 서버만 안다.
그래서 가용 여부와 사유를 이 응답으로 내보낸다.
"""

from pydantic import BaseModel


class CapabilityOut(BaseModel):
    """`providers.models.Capability` + 어느 소스가 한 말인지. 소스 **이름**은 화면에 그대로 보일
    수 있는 표시값이다 — 이 문자열로 분기하지 않는다(어댑터 선택은 언제나 레지스트리 조회다)."""

    source: str
    market: str
    data_kind: str
    available: bool
    reason: str | None = None
    # 화면이 「키를 넣으면 풀린다」와 「이 소스는 원래 안 준다」를 가르는 근거. 문구로 가르지
    # 않는 이유는 문구만 바뀌어도 판정이 조용히 갈리기 때문이다 — 그래서 서버가 코드를 준다.
    code: str | None = None


class CapabilitiesOut(BaseModel):
    items: list[CapabilityOut]
    total_count: int
