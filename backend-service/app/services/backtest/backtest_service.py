"""백테스트 실행 — 캔들을 **한 번** 로드해 엔진을 돌리고 결과를 남긴다 (#200).

## 이 층이 있는 이유

`engine.py` 는 저장소를 모른다(그 경계는 `verify_backtest_engine_purity.py` 가 지킨다).
그래서 「캔들을 읽어 온다」와 「결과를 쓴다」는 여기가 맡는다 — **조합 루프 밖**이다.

스펙 §6 실측이 조합마다 DB 재조회면 4.9분이 83분이 된다고 못박았다(I/O 가 계산의 16배).
그래서 이 서비스가 캔들을 `BarSeries` 로 한 번 올리고, 격자(#202)는 그 위에서 엔진을
N 번 호출한다 — 다시 읽지 않는다.
"""

import json

from core.exceptions import BadRequestError, NotFoundError
from services.backtest.engine import BarSeries, CostModel, RunResult, Strategy, quantize, run_single

# 스펙 §8.5.1 — 위탁수수료 0.15% 는 **10배 오차**였고 그 오차가 "연 비용 원금의 145%" 경고를
# 만들었다. 첫 화면부터 뜨는 경고는 경고를 무시하는 법을 학습시킨다.
#
# 기본값을 두되 실행마다 `cost_assumptions` 로 남겨, 나중에 「무엇을 가정했나」가 복원된다.
DEFAULT_COSTS = {"fee_rate": 0.00015, "slippage_rate": 0.0005, "sell_tax_rate": 0.0018}


class BacktestService:
    def __init__(self, backtest_repository, bar_service, strategy_loader):
        self.backtest_repository = backtest_repository
        self.bar_service = bar_service
        self.strategy_loader = strategy_loader

    # ── 캔들 로딩 (조합 루프 **밖**) ─────────────────────────────────────────
    def load_series(self, args: dict) -> BarSeries:
        """한 종목의 일봉을 컬럼 지향으로 올린다. **격자는 이것을 재사용한다.**"""
        payload = self.bar_service.select_daily_bar_list(
            {
                "market": args["market"],
                "symbol": args["symbol"],
                "date_from": args["period_from"],
                "date_to": args["period_to"],
                "workspace_id": args.get("workspace_id"),
            }
        )
        items = payload.get("items") or []
        if not items:
            # 「없는 종목」과 「아직 못 받은 종목」을 가르지 않고 뭉뚱그리면, 키가 없어서
            # 비었을 때 사용자가 자기 입력을 의심하게 된다. bar_service 가 만든 사유를 그대로 낸다.
            reason = payload.get("unavailable_reason") or "그 구간에 적재된 캔들이 없습니다"
            raise BadRequestError(f"백테스트를 돌릴 캔들이 없습니다 — {reason}")

        instrument_id = int(items[0].get("instrument_id") or 0)
        return BarSeries(
            instrument_id=instrument_id,
            dt=[str(row["dt"]) for row in items],
            open=[float(row["open"]) for row in items],
            high=[float(row["high"]) for row in items],
            low=[float(row["low"]) for row in items],
            close=[float(row["close"]) for row in items],
            volume=[float(row.get("volume") or 0) for row in items],
        )

    # ── 실행 ─────────────────────────────────────────────────────────────────
    def run(self, args: dict) -> dict:
        """전략·종목·구간을 받아 한 조합을 돌리고 결과를 남긴다.

        완료 조건(#200): 이 함수를 부르면 `tn_backtest_run` 에 행이 생기고
        `tn_backtest_equity` 로 곡선이 조회된다.
        """
        strategy_key = args["strategy_key"]
        module = self.strategy_loader(strategy_key)
        if module is None:
            raise NotFoundError(f"전략을 찾을 수 없습니다: {strategy_key}")
        strategy = Strategy(module)

        params = dict(args.get("params") or {})
        costs_raw = {**DEFAULT_COSTS, **(args.get("costs") or {})}
        costs = CostModel(
            fee_rate=float(costs_raw["fee_rate"]),
            slippage_rate=float(costs_raw["slippage_rate"]),
            sell_tax_rate=float(costs_raw["sell_tax_rate"]),
        )

        series = self.load_series(args)
        workspace_id = args["workspace_id"]

        run_id = self.backtest_repository.insert_run(
            {
                "workspace_id": workspace_id,
                "parent_run_id": args.get("parent_run_id"),
                "attempt_no": self.backtest_repository.next_attempt_no(workspace_id, strategy_key),
                "bot_id": args.get("bot_id"),
                "strategy_key": strategy_key,
                "strategy_version": strategy.version,
                "params": json.dumps(params, ensure_ascii=False),
                "universe_def": json.dumps({"market": args["market"], "symbols": [args["symbol"]]}, ensure_ascii=False),
                "universe_as_of": args.get("universe_as_of"),
                "data_snapshot_id": args.get("data_snapshot_id"),
                "adj_policy": args.get("adj_policy") or "unadjusted",
                "cost_assumptions": json.dumps(costs_raw, ensure_ascii=False),
                "period_from": args["period_from"],
                "period_to": args["period_to"],
                "initial_cash": args["initial_cash"],
                "reg_id": args.get("reg_id") or "system",
            }
        )

        try:
            result = run_single(
                strategy=strategy,
                params=params,
                series=series,
                rows=series.rows(),
                initial_cash=float(args["initial_cash"]),
                costs=costs,
            )
            written = self._persist(run_id, result)
            self.backtest_repository.finish_run({"run_id": run_id, "status": "succeeded", "failed_reason": None})
        except Exception as exc:  # noqa: BLE001
            # 실패도 남긴다 — 「돌렸는데 아무것도 없다」와 「실패했다」는 다른 상태다.
            self.backtest_repository.finish_run(
                {"run_id": run_id, "status": "failed", "failed_reason": str(exc)[:1000]}
            )
            raise

        return {"run_id": run_id, "status": "succeeded", **written}

    def _persist(self, run_id: int, result: RunResult) -> dict:
        """엔진 산출물을 네 테이블 + 현금 원장에 넣는다."""
        equity = [
            {
                "run_id": run_id,
                "dt": point.dt,
                "equity": quantize(point.equity),
                "cash": quantize(point.cash),
                "position_count": point.position_count,
                "gross_exposure": quantize(point.gross_exposure),
            }
            for point in result.equity
        ]

        trades = [
            {
                "run_id": run_id,
                "instrument_id": t.instrument_id,
                "side": t.side,
                "entry_ts": t.entry_ts,
                "exit_ts": t.exit_ts,
                "qty": quantize(t.qty, 6),
                "fill_price": quantize(t.entry_price, 6),
                "exit_price": quantize(t.exit_price, 6) if t.exit_price is not None else None,
                "fee": quantize(t.fee, 6),
                "slippage": quantize(t.slippage, 6),
                "realized_pnl": quantize(t.realized_pnl, 6) if t.realized_pnl is not None else None,
                "mae": quantize(t.mae, 6) if t.mae is not None else None,
                "mfe": quantize(t.mfe, 6) if t.mfe is not None else None,
            }
            for t in result.trades
        ]

        signals = [
            {
                "run_id": run_id,
                "dt": s["dt"],
                "instrument_id": s["instrument_id"],
                "conditions": json.dumps(s.get("conditions") or {}, ensure_ascii=False),
                "factors": json.dumps(s.get("factors") or {}, ensure_ascii=False),
                "passed": bool(s.get("passed")),
            }
            for s in result.signals
        ]

        cash = [
            {
                "run_id": run_id,
                "dt": e.dt,
                "event_kind": e.event_kind,
                "amount": quantize(e.amount),
                "note": e.note,
            }
            for e in result.cash_events
        ]

        return {
            "equity_rows": self.backtest_repository.insert_equity(equity),
            "trade_rows": self.backtest_repository.insert_trades(trades),
            "signal_rows": self.backtest_repository.insert_signals(signals),
            "cash_rows": self.backtest_repository.insert_cash_events(cash),
        }

    # ── 조회 ─────────────────────────────────────────────────────────────────
    def select_result(self, run_id: int) -> dict:
        run = self.backtest_repository.select_run(run_id)
        if not run:
            raise NotFoundError(f"실행을 찾을 수 없습니다: {run_id}")
        return {
            "run": run,
            "equity": self.backtest_repository.select_equity_curve(run_id),
            "trades": self.backtest_repository.select_trades(run_id),
        }
