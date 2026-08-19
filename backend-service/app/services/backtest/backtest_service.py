"""백테스트 실행 — 캔들을 **한 번** 로드해 엔진을 돌리고 결과를 남긴다 (#200).

## 이 층이 있는 이유

`engine.py` 는 저장소를 모른다(그 경계는 `verify_backtest_engine_purity.py` 가 지킨다).
그래서 「캔들을 읽어 온다」와 「결과를 쓴다」는 여기가 맡는다 — **조합 루프 밖**이다.

스펙 §6 실측이 조합마다 DB 재조회면 4.9분이 83분이 된다고 못박았다(I/O 가 계산의 16배).
그래서 이 서비스가 캔들을 `BarSeries` 로 한 번 올리고, 격자(#202)는 그 위에서 엔진을
N 번 호출한다 — 다시 읽지 않는다.
"""

import json
from types import SimpleNamespace

from core.exceptions import BadRequestError, NotFoundError
from services.backtest.engine import BarSeries, CostModel, RunResult, Strategy, quantize, run_single
from services.backtest.grid import axes_from_spec, run_grid
from services.backtest.metrics import compute

# 스펙 §8.5.1 — 위탁수수료 0.15% 는 **10배 오차**였고 그 오차가 "연 비용 원금의 145%" 경고를
# 만들었다. 첫 화면부터 뜨는 경고는 경고를 무시하는 법을 학습시킨다.
#
# 기본값을 두되 실행마다 `cost_assumptions` 로 남겨, 나중에 「무엇을 가정했나」가 복원된다.
DEFAULT_COSTS = {"fee_rate": 0.00015, "slippage_rate": 0.0005, "sell_tax_rate": 0.0018}


def _build_context(universe_series, initial_cash: float) -> dict:
    """벤치마크·집중도 — 유니버스 캔들이 있어야 계산된다.

    없으면 **지어내지 않고 사유를 남긴다.** 화면은 그 문구를 그대로 쓴다.
    """
    from services.backtest.context import cluster_concentration, equal_weight_universe

    if not universe_series:
        return {
            "benchmarks": [],
            "concentration": None,
            "absent_reason": "유니버스 캔들을 싣지 않았습니다 — 벤치마크·집중도를 계산할 수 없습니다",
        }

    bench = equal_weight_universe(universe_series, initial_cash)
    conc = cluster_concentration(universe_series)
    return {
        "benchmarks": [
            {
                "key": bench.key,
                "label": bench.label,
                "dt": bench.dt,
                "equity": bench.equity,
                "total_return": bench.total_return,
                "derived_from": bench.derived_from,
            }
        ],
        "concentration": {
            "clusters": [
                {"instrument_ids": c.instrument_ids, "representative": c.representative, "weight_pct": c.weight_pct}
                for c in conc.clusters
            ],
            "top_share_pct": conc.top_share_pct,
            "derived_from": conc.derived_from,
            "absent_reason": conc.absent_reason,
        },
        "absent_reason": None,
    }


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

        # **`bar_service` 의 항목 계약은 `time` 이다** (`_to_item`) — `dt` 가 아니다.
        # 처음엔 `dt` 로 읽어 `KeyError: 'dt'` 로 500 이 났다. 단위 테스트는 엔진에 직접
        # BarSeries 를 넣어 돌리므로 이 경계를 한 번도 안 태웠고, 실제 적재본으로 돌린
        # 첫 순간에 드러났다(#217).
        #
        # `instrument_id` 도 안 온다 — 그 표현은 종목이 아니라 캔들만 담는다. 백테스트는
        # 한 종목만 다루므로 0 으로 두되, **없는 값을 있는 척 만들지 않는다**는 뜻으로
        # 명시한다(다종목이 오면 이 자리가 먼저 바뀌어야 한다).
        return BarSeries(
            instrument_id=0,
            dt=[str(row["time"])[:10] for row in items],
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

    # ── 격자 실행 (#202) ─────────────────────────────────────────────────────
    def run_grid(self, args: dict) -> dict:
        """**단일 점을 만들지 않는다** — 실행 하나가 격자를 낳는다 (스펙 D-Q1).

        캔들을 **한 번** 올려 조합마다 재사용한다. 조합마다 DB 를 다시 읽으면 4.9분이
        83분이 된다(스펙 §6 실측).

        각 칸은 자기 `run_id` 를 갖고 `parent_run_id` 로 부모 실행에 매달린다 —
        「무엇이 달라졌나」가 그 계보로 계산된다.
        """
        strategy_key = args["strategy_key"]
        module = self.strategy_loader(strategy_key)
        if module is None:
            raise NotFoundError(f"전략을 찾을 수 없습니다: {strategy_key}")
        strategy = Strategy(module)

        sweep = args.get("sweep") or {}
        if not sweep:
            raise BadRequestError(
                "훑을 파라미터가 없습니다 — 격자 실행은 축이 하나 이상 필요합니다. 한 조합만 보려면 단일 실행을 쓰세요."
            )
        param_specs = list(module.STRATEGY.get("params") or [])
        axes = axes_from_spec(param_specs, sweep)

        base_params = dict(args.get("params") or {})
        costs_raw = {**DEFAULT_COSTS, **(args.get("costs") or {})}
        costs = CostModel(
            fee_rate=float(costs_raw["fee_rate"]),
            slippage_rate=float(costs_raw["slippage_rate"]),
            sell_tax_rate=float(costs_raw["sell_tax_rate"]),
        )

        series = self.load_series(args)  # ← 루프 밖. 한 번만 읽는다.
        grid = run_grid(
            strategy=strategy,
            axes=axes,
            base_params=base_params,
            series=series,
            initial_cash=float(args["initial_cash"]),
            costs=costs,
        )

        parent_run_id = args.get("parent_run_id")
        cells_out = []
        for cell in grid.cells:
            run_id = self._insert_run(args, strategy, cell.params, costs_raw, parent_run_id)
            failed_reason = cell.failed_reason

            # **저장 실패도 칸 하나만 죽인다.** 감싸지 않으면 DB 문제가 난 칸의 행이
            # `running` 으로 영원히 멈추고, 이미 끝난 앞 칸들의 결과도 호출자에게 못 간다 —
            # 「한 칸이 터져도 격자를 버리지 않는다」가 전략 실패에만 지켜지고 저장 실패에는
            # 안 지켜지는 것이다. 단일 실행(`run`)은 이미 저장까지 한 묶음으로 감쌌다.
            if cell.ok:
                try:
                    self._persist(run_id, cell.result)
                except Exception as exc:  # noqa: BLE001
                    failed_reason = f"결과를 저장하지 못했습니다: {str(exc)[:400]}"

            try:
                self.backtest_repository.finish_run(
                    {
                        "run_id": run_id,
                        "status": "succeeded" if failed_reason is None else "failed",
                        "failed_reason": failed_reason,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                # 마감조차 못 하면 그 행은 `running` 으로 남는다 — 숨기지 말고 결과에 적어,
                # 화면이 「돌고 있음」과 「마감 못 함」을 구분할 수 있게 한다.
                failed_reason = (failed_reason or "") + f" (마감 실패: {str(exc)[:200]})"

            # **격자 칸이 1급 지표를 갖는다** (#220). 격자는 사용자가 조합을 **고르는** 자리라,
            # 여기서 4급 지표(수익률)만 보이면 「가장 많이 번 칸」이 가장 진해 보이고 사용자는 그
            # 칸을 고른다 — 스펙 D-Q2 가 *"트레이더가 계좌를 닫는 이유는 샤프가 낮아서가 아니라
            # 낙폭을 못 견뎌서다"* 라며 뒤집어 놓은 순서와 정면으로 어긋난다.
            #
            # 리포트를 열면 그제야 1급이 보이는데, **고른 뒤에 보이는 것은 선택을 못 바꾼다.**
            #
            # 저장하지 않고 여기서 만든다 — 정의(#201)가 바뀌면 저장된 값이 낡은 정의를 낸다.
            cell_metrics = None
            if failed_reason is None and cell.result.equity:
                from services.backtest.metrics import longest_underwater, max_drawdown

                _eq = [p.equity for p in cell.result.equity]
                _under, _still = longest_underwater(_eq)
                _mdd, _, _ = max_drawdown(_eq)
                cell_metrics = {
                    "longest_underwater": float(_under),
                    "still_underwater": _still,
                    "mdd_pct": _mdd * 100,
                    "total_return_pct": ((_eq[-1] - _eq[0]) / _eq[0] * 100 if _eq[0] else None),
                }

            cells_out.append(
                {
                    "run_id": run_id,
                    "params": cell.params,
                    "status": "succeeded" if failed_reason is None else "failed",
                    "failed_reason": failed_reason,
                    "final_equity": cell.result.final_equity if failed_reason is None else None,
                    # 색을 만드는 값 — 화면이 무엇으로 칠했는지 함께 적을 수 있게 이름을 그대로 준다.
                    "metrics": cell_metrics,
                }
            )

        return {
            "shape": list(grid.shape),
            "axes": [{"name": a.name, "values": list(a.values)} for a in grid.axes],
            "cells": cells_out,
            # **화면이 「전부 돌려봤다」고 말하려면 이 수가 한계 계산에 들어가야 한다.**
            # 격자를 훑는 것도 시도이므로(스펙 §8.5.2), 칸 수가 곧 소비한 시도다.
            "attempts_used": grid.attempts_used,
            # 칸의 수익률은 이 값 대비다 — 화면이 최종 평가액만 받으면 색을 정할 기준이 없다.
            "initial_cash": float(args["initial_cash"]),
        }

    def _insert_run(self, args, strategy, params, costs_raw, parent_run_id) -> int:
        workspace_id = args["workspace_id"]
        return self.backtest_repository.insert_run(
            {
                "workspace_id": workspace_id,
                "parent_run_id": parent_run_id,
                "attempt_no": self.backtest_repository.next_attempt_no(workspace_id, strategy.key),
                "bot_id": args.get("bot_id"),
                "strategy_key": strategy.key,
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

    # ── 조회 ─────────────────────────────────────────────────────────────────
    def diff_against_parent(self, run_id: int) -> dict:
        """이 실행이 **부모와 무엇이 달라졌나**.

        완료 조건이 「`parent_run_id` 로 두 실행의 차이가 조회된다」인데, 값만 저장하고
        비교를 클라이언트에 맡기면 그 조건은 절반만 닫힌다 — 리뷰가 짚은 자리다.

        비교 대상은 **사람이 바꿀 수 있었던 것**이다: 파라미터·비용 가정·구간·유니버스.
        전략 버전이 달라졌으면 그것부터 알려야 한다 — 파라미터가 같아도 결과가 달라진다.
        """
        run = self.backtest_repository.select_run(run_id)
        if not run:
            raise NotFoundError(f"실행을 찾을 수 없습니다: {run_id}")

        parent_id = run.get("parent_run_id")
        if parent_id is None:
            return {
                "run_id": run_id,
                "parent_run_id": None,
                "changes": [],
                "reason": "부모 실행이 없습니다 — 이 실행이 계보의 시작입니다",
            }

        parent = self.backtest_repository.select_run(parent_id)
        if not parent:
            return {
                "run_id": run_id,
                "parent_run_id": parent_id,
                "changes": [],
                "reason": f"부모 실행({parent_id})을 찾을 수 없습니다 — 지워졌을 수 있습니다",
            }

        changes: list[dict] = []
        for field in ("strategy_key", "strategy_version", "adj_policy", "period_from", "period_to", "initial_cash"):
            before, after = parent.get(field), run.get(field)
            if str(before) != str(after):
                changes.append({"kind": "field", "name": field, "before": str(before), "after": str(after)})

        for field in ("params", "cost_assumptions", "universe_def"):
            before = parent.get(field) or {}
            after = run.get(field) or {}
            for key in sorted(set(before) | set(after)):
                if before.get(key) != after.get(key):
                    changes.append({"kind": field, "name": key, "before": before.get(key), "after": after.get(key)})

        return {
            "run_id": run_id,
            "parent_run_id": parent_id,
            "changes": changes,
            "reason": None if changes else "부모와 같은 조건입니다",
        }

    def select_result(self, run_id: int) -> dict:
        run = self.backtest_repository.select_run(run_id)
        if not run:
            raise NotFoundError(f"실행을 찾을 수 없습니다: {run_id}")
        return {
            "run": run,
            "equity": self.backtest_repository.select_equity_curve(run_id),
            "trades": self.backtest_repository.select_trades(run_id),
        }

    def select_runs_by_bot(self, args: dict) -> dict:
        """봇 하나의 검증 이력. 「만들고 → 검증하고 → 굴린다」의 가운데를 화면이 잇는 근거다."""
        rows = self.backtest_repository.select_runs_by_bot(
            int(args["bot_id"]), int(args["workspace_id"]), int(args["limit"])
        )
        items = [
            {
                **row,
                "period_from": str(row["period_from"]),
                "period_to": str(row["period_to"]),
                "finished_dt": str(row["finished_dt"]) if row["finished_dt"] else None,
            }
            for row in rows
        ]
        total = self.backtest_repository.count_runs_by_bot(int(args["bot_id"]), int(args["workspace_id"]))
        return {"items": items, "total_count": total}

    def select_report(self, args: dict) -> dict:
        """한 조합의 리포트 — 곡선·거래에 **지표를 붙여** 낸다 (#203).

        격자 칸 클릭이 이 조회 하나로 끝나야 한다(스펙 §5 — 격자는 사전계산이므로 칸 클릭은
        계산이 아니라 조회다). 지표는 저장하지 않고 여기서 만든다 — 정의(#201)가 바뀌면
        저장된 값이 낡은 정의를 화면에 내는 것을 막는다.
        """
        run_id = int(args["run_id"])
        run = self.backtest_repository.select_run(run_id)
        # 남의 워크스페이스 run 은 「없는 것」과 같은 답을 준다 — 존재 여부도 정보다.
        if not run or run["workspace_id"] != args["workspace_id"]:
            raise NotFoundError(f"실행을 찾을 수 없습니다: {run_id}")

        equity_rows = self.backtest_repository.select_equity_curve(run_id)
        trade_rows = self.backtest_repository.select_trades(run_id)

        costs = dict(run.get("cost_assumptions") or {})
        # 왕복 비용률 — 수수료·슬리피지는 사고팔 때 두 번, 증권거래세는 매도에만 (engine.CostModel).
        round_trip = (
            2 * float(costs.get("fee_rate") or 0)
            + 2 * float(costs.get("slippage_rate") or 0)
            + float(costs.get("sell_tax_rate") or 0)
        )

        metrics = compute(
            equity_dt=[str(row["dt"]) for row in equity_rows],
            equity=[float(row["equity"]) for row in equity_rows],
            # metrics.compute 는 engine.Trade 의 속성 계약만 요구한다 — DB 행을 그 모양으로 입힌다.
            trades=[
                SimpleNamespace(
                    realized_pnl=float(row["realized_pnl"]) if row["realized_pnl"] is not None else None,
                    entry_price=float(row["fill_price"]),
                    qty=float(row["qty"]),
                )
                for row in trade_rows
            ],
            round_trip_cost_rate=round_trip,
        )

        return {
            "run": {
                "run_id": run["run_id"],
                "bot_id": run["bot_id"],
                "parent_run_id": run["parent_run_id"],
                "attempt_no": run["attempt_no"],
                "strategy_key": run["strategy_key"],
                "strategy_version": run["strategy_version"],
                "params": run["params"],
                "universe_def": run["universe_def"],
                "adj_policy": run["adj_policy"],
                "cost_assumptions": costs,
                "period_from": str(run["period_from"]),
                "period_to": str(run["period_to"]),
                "initial_cash": float(run["initial_cash"]),
                "status": run["status"],
                "failed_reason": run["failed_reason"],
                "finished_dt": str(run["finished_dt"]) if run["finished_dt"] else None,
            },
            "equity": [
                {
                    "dt": str(row["dt"]),
                    "equity": float(row["equity"]),
                    "cash": float(row["cash"]),
                    "position_count": int(row["position_count"]),
                    "gross_exposure": float(row["gross_exposure"]),
                }
                for row in equity_rows
            ],
            "trades": [
                {
                    "trade_id": row["trade_id"],
                    "instrument_id": row["instrument_id"],
                    "side": row["side"],
                    "entry_ts": str(row["entry_ts"]),
                    "exit_ts": str(row["exit_ts"]) if row["exit_ts"] else None,
                    "qty": float(row["qty"]),
                    "fill_price": float(row["fill_price"]),
                    "exit_price": float(row["exit_price"]) if row["exit_price"] is not None else None,
                    "fee": float(row["fee"]),
                    "slippage": float(row["slippage"]),
                    "realized_pnl": float(row["realized_pnl"]) if row["realized_pnl"] is not None else None,
                    "mae": float(row["mae"]) if row["mae"] is not None else None,
                    "mfe": float(row["mfe"]) if row["mfe"] is not None else None,
                }
                for row in trade_rows
            ],
            # **맥락(#204)** — 「내가 잘한 건가, 그냥 시장이 좋았던 건가」. 유니버스 캔들이 없으면
            # 지어내지 않고 사유를 남긴다. 계산만 되고 결과에 안 실리면 「실행 결과」에 곡선·집중도가
            # 없다(리뷰 지적 #212).
            "context": _build_context(args.get("universe_series"), float(run["initial_cash"])),
            "metrics": [
                {
                    "key": m.key,
                    "label": m.label,
                    "value": m.value,
                    "unit": m.unit,
                    "derived_from": m.derived_from,
                    "absent_reason": m.absent_reason,
                    "note": m.note,
                }
                for m in metrics
            ],
        }
