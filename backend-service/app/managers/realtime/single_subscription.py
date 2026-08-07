"""실시간 구독 슬롯 (갈래 2) — **슬롯이 하나뿐인 자료구조** (MD-AD-19).

"보고 있는 한 종목만 구독한다"를 규약이 아니라 **타입**으로 만든다. 이 클래스에는 종목 목록을
받는 메서드가 존재하지 않으므로, 동시에 두 종목을 구독하는 코드를 **쓸 수 없다** — 리뷰가
잡아야 할 규율이 아니라 컴파일 전에 막히는 형태다.

근거: 증권사 실시간 채널의 동시 구독 상한(조사 기준 40건, 실질 20종목, #227). 상한을 40으로
두고 관리하는 대신 1로 못 박는 이유는, 상한 관리 코드가 생기는 순간 "몇 개까지 되지?"가 화면
곳곳으로 퍼지기 때문이다.

**브로커 어댑터는 아직 없다.** 계좌 개설이 선행이고 에이전트는 계좌를 만들지 않는다(오더 3 T9
위험). 이 파일은 슬롯 구조와 "왜 비어 있는지"의 전달까지이며, `attach_channel()` 이 그 어댑터가
꽂힐 자리다.
"""

from collections.abc import Awaitable, Callable

from core.logger import logger

# 브로커 채널이 붙기 전까지의 사유 — capability 표와 같은 문장을 화면이 받게 한다.
NO_CHANNEL_REASON = "증권사 계좌가 연동되지 않았습니다 — 실시간 호가·체결은 모의계좌 개설 후 열립니다"


class SingleSubscription:
    """구독 슬롯 하나. 새 구독이 들어오면 기존을 해제하고 **교체**한다."""

    def __init__(self):
        self._current: tuple[str, str] | None = None
        self._channel: Callable[[str, str], Awaitable[None]] | None = None
        self._unsubscribe: Callable[[str, str], Awaitable[None]] | None = None
        # 교체가 실제로 해제를 동반했는지 세는 계수기 — 증명 의무(오더 3 T9)의 관측점이다.
        self.released = 0

    def attach_channel(
        self,
        subscribe: Callable[[str, str], Awaitable[None]],
        unsubscribe: Callable[[str, str], Awaitable[None]],
    ) -> None:
        """브로커 실시간 채널을 꽂는다. 채널이 없어도 슬롯은 동작한다 — 무엇을 보고 있는지는
        채널과 무관한 상태이기 때문이다."""
        self._channel = subscribe
        self._unsubscribe = unsubscribe

    async def switch(self, market: str, symbol: str) -> None:
        """슬롯을 이 종목으로 옮긴다. 같은 종목이면 아무 일도 하지 않는다(중복 구독 방지)."""
        target = (market.upper(), symbol.upper())
        if self._current == target:
            return
        await self.release()
        self._current = target
        if self._channel is not None:
            await self._channel(*target)
        else:
            logger.info(f"실시간 구독 슬롯 전환 (채널 미연동) — {target[0]} {target[1]}: {NO_CHANNEL_REASON}")

    async def release(self) -> None:
        """현재 구독을 해제한다. 채널이 없으면 상태만 비운다."""
        if self._current is None:
            return
        previous, self._current = self._current, None
        self.released += 1
        if self._unsubscribe is not None:
            await self._unsubscribe(*previous)

    def current(self) -> tuple[str, str] | None:
        return self._current

    def unavailable_reason(self) -> str | None:
        """채널이 없으면 사유, 있으면 `None` — 화면이 그대로 보여줄 문장이다(FR-021)."""
        return None if self._channel is not None else NO_CHANNEL_REASON


single_subscription = SingleSubscription()
