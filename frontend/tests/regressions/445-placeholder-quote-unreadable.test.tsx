// @vitest-environment jsdom
//
// #445 F11 — 종목이 달라도 종목 정보가 **똑같은 값**을 냈다: 74,200원 ▲1,200 (1.64%).
// 배지는 「임시 데이터」라고 정직하게 말하지만, **여러 종목을 훑기 전에는 같은 값인 줄 모른다.**
// 하나만 보고 있으면 그 숫자가 진짜인지 아닌지 화면에서 가릴 단서가 없다.
//
// **리드 결정 (2026-09-02, Q1)**: 임시 시세는 **「못 읽을 값」**으로 낸다 — 오독이 원리적으로
// 불가능한 표시. 「그럴듯한 값 유지」와 「종목마다 다른 합성값」은 기각됐다 (후자가 가장 위험하다 —
// 그럴듯한데 종목마다 다르면 진짜와 구별할 단서가 사라진다).
//
// 자리는 지킨다(레이아웃이 무너지면 진짜 값이 왔을 때 화면이 튄다). 읽을 수 없게만 만든다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

vi.mock("@/components/features/Terminal/panelProvenanceBridge", () => ({
  usePanelProvenance: () => vi.fn(),
}));
vi.mock("@/hooks/terminal/useTerminalContext", () => ({
  useTerminalSymbol: () => ({ ticker: "005930", name: "삼성전자", market: "KOSPI" }),
}));
vi.mock("@/hooks/terminal/useRealtimeQuote", () => ({ useRealtimeQuote: vi.fn() }));

const { useRealtimeQuote } = await import("@/hooks/terminal/useRealtimeQuote");
const SymbolInfoPanel = (await import("@/components/features/SymbolInfoPanel/SymbolInfoPanel")).default;

const placeholder = () =>
  vi.mocked(useRealtimeQuote).mockReturnValue({
    data: null,
    error: null,
    provenance: { kind: "placeholder", hint: "실시간 계약이 아직 없습니다" },
  } as never);

const live = () =>
  vi.mocked(useRealtimeQuote).mockReturnValue({
    data: { price: 74200, change: 1200, changeRate: 1.64, volume: 8_423_190, at: "2026-09-03T00:00:00Z" },
    error: null,
    provenance: { kind: "live" },
  } as never);

describe("임시 시세는 읽을 수 없다", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("임시일 때 숫자가 하나도 안 보인다 — 종목 코드 말고는", () => {
    placeholder();
    const { container } = render(<SymbolInfoPanel instanceId="p1" settings={{}} onSettingsChange={vi.fn()} />);

    // 종목 코드(005930)는 시세가 아니라 신원이므로 남는다. 그것을 뺀 나머지에 숫자가 없어야 한다.
    const shown = (container.textContent ?? "").replace("005930", "");
    expect(shown).not.toMatch(/\d/);
  });

  it("임시일 때 방향 기호(▲▼)를 그리지 않는다 — 방향도 지어낸 값이다", () => {
    placeholder();
    const { container } = render(<SymbolInfoPanel instanceId="p1" settings={{}} onSettingsChange={vi.fn()} />);

    expect(container.textContent ?? "").not.toMatch(/[▲▼]/);
  });

  it("임시일 때도 자리는 남는다 — 값이 오면 레이아웃이 안 튄다", () => {
    placeholder();
    render(<SymbolInfoPanel instanceId="p1" settings={{}} onSettingsChange={vi.fn()} />);

    expect(screen.getByText("거래량")).toBeTruthy();
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(3);
  });

  it("진짜 시세는 종전대로 그린다 — 막는 범위가 넓어지지 않았다", () => {
    live();
    const { container } = render(<SymbolInfoPanel instanceId="p1" settings={{}} onSettingsChange={vi.fn()} />);
    const shown = container.textContent ?? "";

    expect(shown).toContain("74,200");
    expect(shown).toMatch(/▲/);
    expect(shown).toContain("8,423,190");
  });
});
