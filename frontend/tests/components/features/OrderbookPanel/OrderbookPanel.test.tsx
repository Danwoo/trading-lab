// @vitest-environment jsdom
//
// 「아직 확인 중」과 「소스가 없다」는 다르다. 캐패빌리티 응답이 오기 전에는 `data` 가 `null`
// 인데, 그것을 빈 목록으로 읽으면 화면이 **없는 사실을 단언한다** — 네트워크가 느린 환경에서
// 사용자가 실제로 그 문구를 본다. 이 자리는 사유를 지어내지 않는 것이 요점이라 그물을 건다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";

import OrderbookPanel from "@/components/features/OrderbookPanel/OrderbookPanel";
import type { PanelData } from "@/types/terminal/provenance";
import type { MarketCapability } from "@/services/terminal/marketService";

const SYMBOL = { market: "KRX", ticker: "005930", name: "삼성전자" };

vi.mock("@/hooks/terminal/useTerminalContext", () => ({ useTerminalSymbol: () => SYMBOL }));
vi.mock("@/hooks/terminal/useMarketCapabilities", () => ({ useMarketCapabilities: vi.fn() }));

const reported: string[] = [];
vi.mock("@/components/features/Terminal/panelProvenanceBridge", () => ({
  usePanelProvenance: () => (p: { kind: string; reason?: string }) => {
    if (p.kind === "unavailable" && p.reason) reported.push(p.reason);
  },
}));

const { useMarketCapabilities } = await import("@/hooks/terminal/useMarketCapabilities");

function capabilities(over: Partial<PanelData<MarketCapability[]>>): PanelData<MarketCapability[]> {
  return {
    data: null,
    isLoading: false,
    error: null,
    provenance: { kind: "loaded", source: "캐패빌리티", asOf: null },
    ...over,
  };
}

describe("OrderbookPanel — 확인 중을 「소스 없음」이라 말하지 않는다", () => {
  afterEach(() => {
    cleanup();
    reported.length = 0;
    vi.clearAllMocks();
  });

  it("응답 전(data=null)에는 「등록되어 있지 않습니다」를 단언하지 않는다", () => {
    vi.mocked(useMarketCapabilities).mockReturnValue(capabilities({ data: null, isLoading: true }));

    render(<OrderbookPanel instanceId="orderbook-1" settings={{}} onSettingsChange={() => {}} />);

    expect(reported.some((r) => r.includes("등록되어 있지 않습니다"))).toBe(false);
    expect(reported.some((r) => r.includes("확인하고 있습니다"))).toBe(true);
  });

  it("응답이 와서 정말 0건일 때만 「등록되어 있지 않습니다」라고 말한다", () => {
    vi.mocked(useMarketCapabilities).mockReturnValue(capabilities({ data: [] }));

    render(<OrderbookPanel instanceId="orderbook-1" settings={{}} onSettingsChange={() => {}} />);

    expect(reported.some((r) => r.includes("등록되어 있지 않습니다"))).toBe(true);
  });
});
