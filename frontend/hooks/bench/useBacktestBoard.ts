"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { BacktestGridIn, GridOut, RunReportOut } from "@/schemas/backtest/backtest";
import { runBacktestGrid, selectBacktestReport } from "@/services/backtest/backtestService";
import { useBenchSelectionStore } from "@/stores/shell/benchSelectionStore";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";

export interface BacktestBoard {
  grid: GridOut | null;
  isRunning: boolean;
  /** 실행 실패의 서버 사유 — 화면이 그대로 낸다 (「캔들이 없습니다 — …」 류). */
  runError: string | null;
  report: RunReportOut | null;
  isReportLoading: boolean;
  reportError: string | null;
  /** 마지막 칸 클릭 → 리포트 도착까지 ms — 응답 예산(스펙 §5 ≤500ms)의 실측 자리. */
  lastReportMs: number | null;
  runGrid: (input: BacktestGridIn) => Promise<void>;
  selectCell: (runId: number, label: string) => void;
}

/**
 * 보드의 백테스트 상태 — 격자 하나와, 격자에서 고른 칸의 리포트 하나 (#203).
 *
 * 칸 클릭은 계산이 아니라 조회다(스펙 §5 — 격자는 사전계산). 한 번 온 리포트는 불변
 * 스냅샷이라(run 은 불변, 스펙 §4.1) Map 에 캐시해 되돌아온 클릭을 서버 왕복 없이 답한다.
 */
export function useBacktestBoard(): BacktestBoard {
  const [grid, setGrid] = useState<GridOut | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [report, setReport] = useState<RunReportOut | null>(null);
  const [isReportLoading, setIsReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [lastReportMs, setLastReportMs] = useState<number | null>(null);

  const reportCache = useRef(new Map<number, RunReportOut>());
  // 클릭이 연달아 오면 마지막 클릭만 화면이 된다 — 앞선 응답이 늦게 와서 덮는 것을 막는다.
  const latestRequestedRunId = useRef<number | null>(null);
  const select = useBenchSelectionStore((s) => s.select);

  const runGrid = useCallback(async (input: BacktestGridIn) => {
    setIsRunning(true);
    setRunError(null);
    try {
      const result = await runBacktestGrid(input);
      // 사유는 자리 머리가 「격자 실행이 실패했습니다 — 」를 앞에 붙여 낸다. 여기서 같은
      // 문장을 다시 쓰면 한 줄에 두 번 붙는다(`{success: false}` 200 → `apiCall` 이 null).
      if (result === null) throw new Error("서버가 실패를 알렸고 사유는 주지 않았습니다");
      setGrid(result);
      // 새 격자는 새 지형이다 — 옛 격자의 칸을 가리키던 리포트를 남겨 두면 화면이 거짓말한다.
      setReport(null);
      setReportError(null);
    } catch (error) {
      setRunError(getApiErrorMessage(error));
    } finally {
      setIsRunning(false);
    }
  }, []);

  const selectCell = useCallback(
    (runId: number, label: string) => {
      select({ kind: "grid-point", id: String(runId), label, origin: "board" });

      const cached = reportCache.current.get(runId);
      if (cached) {
        latestRequestedRunId.current = runId;
        setReport(cached);
        setReportError(null);
        setLastReportMs(0);
        return;
      }

      latestRequestedRunId.current = runId;
      setIsReportLoading(true);
      setReportError(null);
      const startedAt = performance.now();
      selectBacktestReport(runId)
        .then((result) => {
          if (latestRequestedRunId.current !== runId) return;
          if (result === null) throw new Error("리포트를 불러오지 못했습니다");
          reportCache.current.set(runId, result);
          setReport(result);
          setLastReportMs(Math.round(performance.now() - startedAt));
        })
        .catch((error) => {
          if (latestRequestedRunId.current !== runId) return;
          setReportError(getApiErrorMessage(error));
        })
        .finally(() => {
          if (latestRequestedRunId.current !== runId) return;
          setIsReportLoading(false);
        });
    },
    [select],
  );

  // 봇 상세의 검증 이력이 `/bench?run=<id>` 로 온다 — 그 실행의 리포트를 열어 둔다.
  // 한 번만 연다: 사용자가 격자에서 다른 칸을 고른 뒤 주소가 되돌리면 안 된다.
  const openedFromUrl = useRef(false);
  useEffect(() => {
    if (openedFromUrl.current) return;
    const asked = Number(new URLSearchParams(window.location.search).get("run"));
    if (!Number.isInteger(asked) || asked <= 0) return;
    openedFromUrl.current = true;
    selectCell(asked, `실행 #${asked}`);
  }, [selectCell]);

  return {
    grid,
    isRunning,
    runError,
    report,
    isReportLoading,
    reportError,
    lastReportMs,
    runGrid,
    selectCell,
  };
}
