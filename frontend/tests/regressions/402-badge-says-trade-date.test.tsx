// @vitest-environment jsdom
//
// #402 — 배지가 「적재본이 덮는 마지막 날」이라며 **적재를 돌린 시각**을 말했다.
//
// 실측(공용 스택): 배지 `시세 · 08-23 · 2일 낡음` / DB `max(trade_date) = 2026-08-21`.
// **08-23 은 일요일**이라 캔들이 있을 수 없는 날이다 — 적재 요청이 기간을 안 실어
// `period_to` 가 NULL 이면 `coverageOf` 가 `finished_dt`(실행 시각)를 집었다.
//
// 그 폴백을 없앴다. 이 그물은 **적재 실행 시각이 배지에 뜨지 않는 것**을 잡는다.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, renderHook, screen, waitFor } from "@testing-library/react";

import { QuoteFreshnessBanner } from "@/components/features/Bench/QuoteFreshnessBanner";
import { coverageKey, useCoverageStore } from "@/stores/terminal/coverageStore";
import { useContextStore } from "@/stores/terminal/contextStore";
import { useLoadedSeries } from "@/hooks/terminal/useLoadedSeries";
import type { IngestRunOut } from "@/schemas/terminal/ingest";

vi.mock("@/services/terminal/ingestService", () => ({ selectIngestRunList: vi.fn() }));
const { selectIngestRunList } = await import("@/services/terminal/ingestService");

vi.mock("@/services/terminal/marketService", () => ({ selectCandles: vi.fn(), selectBarGaps: vi.fn() }));
const { selectCandles } = await import("@/services/terminal/marketService");

const SYMBOL = { market: "KOSPI", ticker: "012450" };
/** 실측 그대로 — 일요일에 끝난 적재. 기간은 안 실렸다(UI 경로가 그렇다). */
const SUNDAY_RUN: IngestRunOut = {
  run_id: 36,
  source: "yfinance",
  job_kind: "daily_bar",
  scope: "KOSPI:012450",
  period_from: null as never,
  period_to: null as never,
  status: "succeeded",
  cursor: null,
  written_rows: 120,
  skipped_rows: 0,
  failed_reason: null,
  started_dt: "2026-08-23T17:00:00",
  finished_dt: "2026-08-23T17:04:49",
  reg_dt: "2026-08-23T17:00:00",
};

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date("2026-08-25T12:00:00"));
  useContextStore.setState({ symbol: null } as never);
  useCoverageStore.setState({ lastTradeDate: {} });
  vi.mocked(selectIngestRunList).mockResolvedValue({ items: [SUNDAY_RUN], total_count: 1 } as never);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.clearAllMocks();
});

const bannerText = () => screen.getByRole("region", { name: "시세 신선도" }).textContent ?? "";

describe("배지는 캔들의 마지막 거래일을 말한다", () => {
  it("적재 실행 시각(일요일)을 덮는 마지막 날로 말하지 않는다", async () => {
    useContextStore.setState({ symbol: SYMBOL } as never);
    useCoverageStore.setState({ lastTradeDate: { [coverageKey(SYMBOL.market, SYMBOL.ticker)]: "2026-08-21" } });

    render(<QuoteFreshnessBanner />);

    await waitFor(() => expect(bannerText()).toContain("08-21"));
    expect(bannerText()).not.toContain("08-23");
  });

  it("종목을 안 골랐으면 날짜를 주장하지 않는다", async () => {
    render(<QuoteFreshnessBanner />);

    // 배지의 문구는 「고르면 채워집니다」다 — 날짜를 주장하지 않는다는 것이 요점이다.
    await waitFor(() => expect(bannerText()).toContain("고르면 채워집니다"));
    expect(bannerText()).not.toContain("08-23");
    expect(bannerText()).not.toContain("낡음");
  });

  it("종목은 골랐는데 캔들을 아직 안 읽었으면 확인 중이다 — 최신으로도 낡음으로도 안 그린다", async () => {
    useContextStore.setState({ symbol: SYMBOL } as never);

    render(<QuoteFreshnessBanner />);

    await waitFor(() => expect(bannerText()).toContain("확인 중"));
    expect(bannerText()).not.toContain("낡음");
  });
});

/**
 * 위 세 단언은 저장소에 값이 **있을 때** 배지가 그것을 말하는지를 본다. 값을 넣는 쪽이 비어 있으면
 * 배지는 영원히 「확인 중」에 머물고 그것을 잡는 그물이 없다 — 그래서 쓰는 쪽도 여기서 함께 잡는다.
 */
describe("캔들을 읽은 자리가 그 마지막 거래일을 알린다", () => {
  const RANGE = { from: "2025-08-25", to: "2026-08-25" };

  beforeEach(() => {
    useContextStore.setState({ symbol: SYMBOL, interval: "1d", range: RANGE, selectedBotId: null } as never);
  });

  it("적재본의 마지막 거래일이 저장소에 남는다", async () => {
    vi.mocked(selectCandles).mockResolvedValue({
      items: [
        { time: "2026-08-19", open: 1, high: 1, low: 1, close: 1, volume: 1 },
        { time: "2026-08-21", open: 1, high: 1, low: 1, close: 1, volume: 1 },
      ],
      source: "적재본",
      // 응답의 `asOf` 를 일부러 **일요일**로 준다 — 배지가 읽는 것이 캔들이지 응답 기준시각이 아님을 못박는다.
      asOf: "2026-08-23T17:04:49",
      unavailableReason: null,
      unavailableCode: null,
    } as never);

    renderHook(() => useLoadedSeries());

    await waitFor(() =>
      expect(useCoverageStore.getState().lastTradeDate[coverageKey(SYMBOL.market, SYMBOL.ticker)]).toBe("2026-08-21"),
    );
  });

  it("빈 적재본은 날짜를 지어내지 않는다", async () => {
    vi.mocked(selectCandles).mockResolvedValue({
      items: [],
      source: "적재본",
      asOf: null,
      unavailableReason: null,
      unavailableCode: null,
    } as never);

    renderHook(() => useLoadedSeries());

    await waitFor(() => expect(selectCandles).toHaveBeenCalledTimes(1));
    expect(useCoverageStore.getState().lastTradeDate[coverageKey(SYMBOL.market, SYMBOL.ticker)]).toBeUndefined();
  });
});
