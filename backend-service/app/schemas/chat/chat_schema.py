from pydantic import BaseModel


class ChatAccountInfo(BaseModel):
    """좌측 패널·범위 필터용 계좌 요약 — portfolio-mcp `AccountInfo`(정본)에서 뽑아낸 뷰 모델.

    생산자와 필드명이 다르므로 이름을 `AccountInfo` 로 두지 않는다 — 같은 이름의 다른 모델이
    두 벌 있으면 어느 쪽 계약을 보는지 알 수 없다(#368). 매핑은 `PortfolioChatService` 가 한다.
    """

    account_id: str  # ← account_id
    name: str  # ← account_name (계좌 별칭)
    kind: str = ""  # ← account_type: cash(위탁) | margin(신용) | isa | pension(연금) 등
    base_ccy: str = ""  # ← base_currency (KRW/USD …)


class AccountsOut(BaseModel):
    items: list[ChatAccountInfo]
    total_count: int


class ChatHolderInfo(BaseModel):
    """계좌주 필터 드롭다운용 — 생산자(portfolio-mcp)에 계좌주 신원 필드가 없어 현재는 늘 비어 있다(#368)."""

    account_id: str
    name: str
    email: str


class HoldersOut(BaseModel):
    items: list[ChatHolderInfo]
    total_count: int
