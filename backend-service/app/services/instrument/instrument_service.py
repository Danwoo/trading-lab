"""종목 마스터 검색 서비스 — 「없다」와 「아직 안 받았다」를 가른다 (FR-021).

마스터가 통째로 비어 있으면 검색 결과 0건은 **「그런 종목이 없다」가 아니다.** 그때 「결과
없음」만 보여 주면 사용자는 자기가 친 종목명을 의심하고 다음에 무엇을 할지도 잃는다 —
`BarService._missing_instrument_error` 가 단건 조회에서 같은 갈래를 세운 것과 같은 규율이다.
"""

from core.exceptions import BadRequestError
from repositories.instrument.instrument_repository import InstrumentRepository

#: 한 응답에 실을 수 있는 종목 수 상한. 검색 결과는 사람이 눈으로 훑어 고르는 목록이라
#: 4,303행을 통째로 내려보낼 이유가 없다 — 좁히는 것은 검색어의 일이다.
MAX_TAKE = 100
DEFAULT_TAKE = 20

MASTER_EMPTY_REASON = "종목 마스터를 아직 한 번도 받지 않았습니다 — 「적재」에서 종목 마스터를 먼저 받아 오세요."


class InstrumentService:
    def __init__(self, instrument_repository: InstrumentRepository):
        self.instrument_repository = instrument_repository

    def select_instrument_list(self, args: dict) -> dict:
        """종목명·코드로 마스터를 훑는다. 검색어가 없으면 앞에서부터 `take` 건."""
        take = self._validated_take(args.get("take"))
        skip = int(args.get("skip") or 0)
        if skip < 0:
            raise BadRequestError(f"skip 은 0 이상이어야 합니다: {skip}")

        items, total_count = self.instrument_repository.select_instrument_list(
            {"q": args.get("q"), "market": args.get("market"), "skip": skip, "take": take}
        )
        # 0건일 때만 마스터 적재 여부를 묻는다 — 결과가 있으면 물어볼 것이 없고, 매 검색마다
        # 세는 쿼리를 한 번 더 태울 이유도 없다.
        reason = None if total_count else self._empty_reason()
        return {"items": items, "total_count": total_count, "unavailable_reason": reason}

    def _empty_reason(self) -> str | None:
        if self.instrument_repository.has_any_instrument():
            return None
        return MASTER_EMPTY_REASON

    @staticmethod
    def _validated_take(take) -> int:
        value = int(take) if take is not None else DEFAULT_TAKE
        if value <= 0 or value > MAX_TAKE:
            raise BadRequestError(f"take 는 1 이상 {MAX_TAKE} 이하여야 합니다: {value}")
        return value
