// @vitest-environment jsdom
//
// #350 — **적재 신호가 오면 적재본을 읽는 훅이 실제로 다시 받는다.**
//
// 같은 이슈의 정적 그물(`tests/regressions/350-ingest-refresh.test.ts`)은 「구독하고 쓰는가」를
// 소스에서 센다. 여기서는 그 위 한 겹 — **세대가 오르면 조회가 한 번 더 나가는가**를 실제로
// 돌려서 본다. 의존성 배열에서 세대를 빼면 정적 그물이 잡지만, 세대를 받아 엉뚱한 자리에 쓰는
// 경우는 이 파일만 잡는다.
//
// **검증 경계** — 서비스 계층을 세운다. 화면에 캔들이 그려지는지는 브라우저로 확인한다.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, renderHook, waitFor } from "@testing-library/react";

import { SymbolSearch } from "@/components/features/Terminal/SymbolSearch";
import { useBarGaps } from "@/hooks/terminal/useBarGaps";
import { useLoadedSeries } from "@/hooks/terminal/useLoadedSeries";
import { useContextStore } from "@/stores/terminal/contextStore";
import { observeIngestRuns, useIngestSignalStore } from "@/stores/terminal/ingestSignalStore";
import { selectBarGaps, selectCandles } from "@/services/terminal/marketService";
import { selectInstrumentList } from "@/services/terminal/instrumentService";
import type { IngestRunOut } from "@/schemas/terminal/ingest";

vi.mock("@/services/terminal/marketService", () => ({
  selectCandles: vi.fn(),
  selectBarGaps: vi.fn(),
}));

vi.mock("@/services/terminal/instrumentService", () => ({ selectInstrumentList: vi.fn() }));
vi.mock("@/services/watchlist/watchlistService", () => ({ createWatchlist: vi.fn() }));

const candles = vi.mocked(selectCandles);
const instruments = vi.mocked(selectInstrumentList);
const gaps = vi.mocked(selectBarGaps);

const SYMBOL = { ticker: "005490", market: "KOSPI", name: "POSCO홀딩스" };
const RANGE = { from: "2025-08-23", to: "2026-08-23" };

/** 이 종목의 일봉 적재가 끝났다는 이력 판. 첫 판은 기준선이라 두 판을 흘린다. */
function givenIngestFinished(scope: string) {
  const running = { run_id: 1, source: "toss", job_kind: "daily_bar", scope, status: "running", written_rows: 0 };
  const done = { ...running, status: "succeeded", written_rows: 242 };
  act(() => observeIngestRuns([running as unknown as IngestRunOut]));
  act(() => observeIngestRuns([done as unknown as IngestRunOut]));
}

beforeEach(() => {
  useIngestSignalStore.setState({ revisionByKey: {}, seenRuns: null });
  useContextStore.setState({ symbol: SYMBOL, interval: "1d", range: RANGE, selectedBotId: null });
  candles.mockResolvedValue({ items: [], source: "toss", asOf: null, unavailableReason: null, unavailableCode: null });
  gaps.mockResolvedValue({ missingDates: [], dateFrom: RANGE.from, dateTo: RANGE.to });
  instruments.mockResolvedValue({ items: [], total_count: 0, unavailable_reason: null } as never);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("#350 적재가 끝나면 적재본을 읽는 훅이 스스로 다시 받는다", () => {
  it("차트 계열 — 종목·주기·기간이 그대로여도 다시 받는다", async () => {
    renderHook(() => useLoadedSeries());
    await waitFor(() => expect(candles).toHaveBeenCalledTimes(1));

    givenIngestFinished("KOSPI:005490");

    await waitFor(() => expect(candles).toHaveBeenCalledTimes(2));
  });

  it("빠진 거래일 — 같은 신호로 결측도 다시 센다", async () => {
    renderHook(() => useBarGaps(true));
    await waitFor(() => expect(gaps).toHaveBeenCalledTimes(1));

    givenIngestFinished("KOSPI:005490");

    await waitFor(() => expect(gaps).toHaveBeenCalledTimes(2));
  });

  it("종목 검색 — 마스터가 채워지면 같은 검색어로 다시 훑는다", async () => {
    vi.useFakeTimers();
    try {
      render(<SymbolSearch onAdded={() => {}} />);
      await act(async () => {
        vi.advanceTimersByTime(300);
      });
      expect(instruments).toHaveBeenCalledTimes(1);

      const master = {
        run_id: 2,
        source: "krx",
        job_kind: "instrument_master",
        scope: "KOSPI",
        status: "running",
        written_rows: 0,
      };
      act(() => observeIngestRuns([master as unknown as IngestRunOut]));
      act(() => observeIngestRuns([{ ...master, status: "succeeded", written_rows: 2476 } as unknown as IngestRunOut]));
      await act(async () => {
        vi.advanceTimersByTime(300);
      });

      expect(instruments).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it("남의 종목 적재는 이 자리를 흔들지 않는다", async () => {
    renderHook(() => useLoadedSeries());
    await waitFor(() => expect(candles).toHaveBeenCalledTimes(1));

    givenIngestFinished("KOSPI:005930");

    // 신호는 분명히 갔는데(다른 키의 세대가 올랐다) 이 훅은 그대로여야 한다.
    expect(useIngestSignalStore.getState().revisionByKey["bar:KOSPI:005930"]).toBe(1);
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(candles).toHaveBeenCalledTimes(1);
  });
});
