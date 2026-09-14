// @vitest-environment jsdom
//
// #445 F11 (차트) — 값이 없을 때 **그럴듯한 캔들**을 그렸다.
//
// 정보 패널의 74,200원은 지웠지만 차트는 그대로였다. `SAMPLE_CANDLES` 는 74,000원에서 출발하는
// 시드 난수 120영업일이라 **종목이 달라도 모양이 같다** — 하나만 보고 있으면 진짜인지 가릴
// 단서가 화면에 없다. 해칭과 배지가 붙어 있어도 「그럴듯한 값」이 남아 있는 한 오독은 가능하다
// (리드 결정 2026-09-14: 차트도 못 읽게).
//
// 이 그물은 **차트에 실제로 넘어가는 캔들**을 본다 — 소스 문자열이 아니라 `setCandles` 가
// 받은 것이다. 지어낸 값이 다른 이름으로 돌아와도 여기서 걸린다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { NO_CONTEXT_REASON } from "@/hooks/terminal/useLoadedSeries";

const setCandles = vi.fn();

vi.mock("@/lib/terminal/candleChart", () => ({
  createCandleChart: () => ({
    setCandles,
    setOverlay: vi.fn(),
    removeOverlay: vi.fn(),
    resize: vi.fn(),
    destroy: vi.fn(),
  }),
}));

const series = vi.fn();
// **`NO_CONTEXT_REASON` 은 원본을 쓴다.** 여기서 지어내면 화면이 「종목을 아직 안 골랐다」로
// 가르는 실제 문자열과 달라져, 그물이 자기가 만든 세계만 검사하게 된다.
vi.mock("@/hooks/terminal/useLoadedSeries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/hooks/terminal/useLoadedSeries")>()),
  useLoadedSeries: () => series(),
}));
vi.mock("@/hooks/terminal/useTerminalContext", () => ({
  useTerminalSymbol: () => ({ ticker: "005930", market: "KRX" }),
  useTerminalInterval: () => "1d",
  useTerminalRange: () => ({ from: "2026-01-01", to: "2026-06-30" }),
}));
vi.mock("@/components/features/Terminal/panelProvenanceBridge", () => ({
  usePanelProvenance: () => vi.fn(),
}));

afterEach(() => {
  cleanup();
  setCandles.mockClear();
});

async function renderChart() {
  const { default: ChartPanel } = await import("@/components/features/ChartPanel/ChartPanel");
  render(<ChartPanel instanceId="c1" settings={{}} onSettingsChange={vi.fn()} />);
}

const lastCandles = () => setCandles.mock.calls.at(-1)?.[0];

describe("값이 없으면 캔들을 그리지 않는다", () => {
  it("키가 아직 없을 때 — 캔들 0개, 사유는 화면에 남는다", async () => {
    series.mockReturnValue({
      data: null,
      isLoading: false,
      error: null,
      provenance: { kind: "placeholder", source: "임시 데이터", hint: ".env 에 데이터 소스 키를 채우세요" },
    });
    await renderChart();

    expect(lastCandles()).toEqual([]);
    expect(screen.getByText(/키를 채우세요/)).toBeTruthy();
  });

  it("종목을 아직 안 골랐을 때 — 캔들 0개, 무엇을 기다리는지 말한다", async () => {
    series.mockReturnValue({
      data: null,
      isLoading: false,
      error: null,
      provenance: { kind: "unavailable", reason: NO_CONTEXT_REASON, because: "not-chosen" },
    });
    await renderChart();

    expect(lastCandles()).toEqual([]);
    expect(screen.getByText(/아직 그릴 값이 없습니다/)).toBeTruthy();
  });

  it("적재본이 있으면 그대로 그린다 — 막는 범위가 넓어지지 않았다", async () => {
    const real = [{ time: "2026-01-02", open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 }];
    series.mockReturnValue({
      data: real,
      isLoading: false,
      error: null,
      provenance: { kind: "loaded", source: "적재본", asOf: "2026-01-02" },
    });
    await renderChart();

    expect(lastCandles()).toEqual(real);
  });

  it("그 밖의 사유는 종전대로 문장으로 덮는다", async () => {
    series.mockReturnValue({
      data: null,
      isLoading: false,
      error: null,
      provenance: { kind: "unavailable", reason: "이 소스는 월봉을 주지 않습니다" },
    });
    await renderChart();

    expect(lastCandles()).toEqual([]);
    expect(screen.getByText(/월봉/)).toBeTruthy();
  });
});
