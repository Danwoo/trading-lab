from core.auth_context import require_workspace_id
from core.exceptions import BadRequestError, ConflictError, NotFoundError
from repositories.bot.bot_repository import BotRepository
from services.bot.strategy_loader import (
    StrategyLoadResult,
    load_strategies,
    to_form_schema,
    validate_param_values,
)

# 설정 하나가 어디서 왔나 (실험대 스펙 §8.6.3 「출처가 남는다」)
PARAM_SOURCES = ("USER", "AI_SUGGESTED")


class BotService:
    """봇 저장·조회. 전략 선언을 읽어 값이 범위 안인지 보고 나서 저장한다."""

    def __init__(self, bot_repository: BotRepository):
        self.bot_repository = bot_repository

    # ── 전략 목록 (폼의 재료) ────────────────────────────────────────────────

    def select_strategy_catalog(self) -> dict:
        """전략 파일을 읽어 폼 스키마로 돌려준다.

        못 읽은 전략은 목록에서 빠지되 **이유를 함께 내보낸다** — 화면이 조용히 빈 목록을
        보여주면 「전략이 없다」와 「전략을 못 읽었다」가 구분되지 않는다.
        """
        result = load_strategies()
        return {
            "items": [to_form_schema(spec) for spec in result.valid],
            "errors": [error.model_dump() for error in result.errors],
        }

    # ── 봇 ──────────────────────────────────────────────────────────────────

    def select_bot_list(self, args: dict) -> tuple[list, int]:
        args["workspace_id"] = require_workspace_id()
        return self.bot_repository.select_bot_list(args)

    def select_bot(self, args: dict) -> dict:
        """봇 하나와 실린 전략. 전략 파일이 사라졌으면 그 사실을 값에 실어 보낸다."""
        args["workspace_id"] = require_workspace_id()
        bot = self.bot_repository.select_bot(args)
        if not bot:
            raise NotFoundError("데이터를 찾을 수 없습니다.")

        catalog = load_strategies()
        bot["strategies"] = [
            self._decorate(row, catalog)
            for row in self.bot_repository.select_bot_strategy_list({"bot_id": args["bot_id"]})
        ]
        return bot

    def insert_bot(self, args: dict) -> tuple:
        args["workspace_id"] = require_workspace_id()
        strategies = self._validated_strategies(args.pop("strategies", []))
        try:
            return self.bot_repository.insert_bot(args, strategies)
        except Exception as error:  # noqa: BLE001 — 유니크 제약 위반을 사용자 문구로 바꾼다
            raise self._as_domain_error(error) from error

    def update_bot(self, args: dict) -> None:
        args["workspace_id"] = require_workspace_id()
        if not self.bot_repository.select_bot(args):
            raise NotFoundError("데이터를 찾을 수 없습니다.")
        raw = args.pop("strategies", None)
        strategies = None if raw is None else self._validated_strategies(raw)
        try:
            self.bot_repository.update_bot(args, strategies)
        except Exception as error:  # noqa: BLE001
            raise self._as_domain_error(error) from error

    def delete_bot(self, args: dict) -> None:
        args["workspace_id"] = require_workspace_id()
        if not self.bot_repository.select_bot(args):
            raise NotFoundError("데이터를 찾을 수 없습니다.")
        self.bot_repository.delete_bot(args)

    # ── 내부 ────────────────────────────────────────────────────────────────

    def _validated_strategies(self, rows: list[dict]) -> list[dict]:
        """전략이 실제로 있는지, 값이 선언한 범위 안인지 본다 — 저장 전에 막는다."""
        if not rows:
            raise BadRequestError("봇에는 전략이 하나 이상 실려야 합니다.")

        catalog = load_strategies()
        seen: set[str] = set()
        validated: list[dict] = []

        for row in rows:
            key = row["strategy_key"]
            if key in seen:
                raise BadRequestError(f"같은 전략이 두 번 실렸습니다: {key}")
            seen.add(key)

            spec = catalog.by_key(key)
            if spec is None:
                # 이 제품의 사용자는 개인 투자자다 — 「전략 파일」은 서버의 소스라 볼 수도 고칠 수도 없다.
                raise BadRequestError(
                    f"'{key}' 전략을 찾을 수 없습니다. 고를 수 있는 전략은 봇 만들기 화면의 전략 목록에 있습니다."
                )

            try:
                params = validate_param_values(spec, row.get("params") or {})
            except ValueError as error:
                raise BadRequestError(str(error)) from error

            validated.append(
                {
                    "strategy_key": key,
                    "params": params,
                    "param_sources": _clean_sources(row.get("param_sources"), set(params)),
                    "weight": row.get("weight"),
                }
            )
        return validated

    @staticmethod
    def _decorate(row: dict, catalog: StrategyLoadResult) -> dict:
        """저장된 전략에 지금의 선언을 붙인다. 없으면 왜 없는지 남긴다."""
        spec = catalog.by_key(row["strategy_key"])
        if spec is None:
            row["form"] = None
            row["missing_reason"] = "전략 파일을 찾을 수 없습니다."
            return row
        row["form"] = to_form_schema(spec)
        row["missing_reason"] = None
        return row

    @staticmethod
    def _as_domain_error(error: Exception) -> Exception:
        message = str(error)
        if "uq_tn_bot_workspace_nm" in message:
            return ConflictError("같은 이름의 봇이 이미 있습니다.")
        return error


def _clean_sources(sources: dict | None, allowed: set[str]) -> dict:
    """선언에 없는 이름의 출처는 버린다 — 없는 설정의 출처가 남으면 근거가 어긋난다."""
    if not sources:
        return {}
    cleaned = {}
    for name, origin in sources.items():
        if name in allowed and origin in PARAM_SOURCES:
            cleaned[name] = origin
    return cleaned
