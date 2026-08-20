import { describe, expect, it } from "vitest";
import { resolveCapability } from "@/lib/terminal/capabilityMatrix";
import type { PanelCapability } from "@/types/terminal/capability";

// `because` 는 배지가 무엇이라 부를지다 — 판정과 함께 오지 않으면 화면이 「제공 안 됨」으로
// 뭉갠다(#284). 그래서 이 단언들이 `reason` 과 나란히 그것도 잡는다.
describe("resolveCapability", () => {
  it("orderbook × US 는 불가 + 이유", () => {
    const verdict = resolveCapability("orderbook", { region: "US" });
    expect(verdict).toEqual({
      available: false,
      reason: "미국 심층 호가는 확보된 소스가 없습니다",
      because: "no-source",
    });
  });

  it("flow × US 는 불가 + 이유", () => {
    const verdict = resolveCapability("flow", { region: "US" });
    expect(verdict).toEqual({
      available: false,
      reason: "미국에는 투자자별 수급 개념이 없습니다 — 기관 보유·공매도 잔고로 대체 예정",
      because: "no-source",
    });
  });

  it("candles × KR 은 가용", () => {
    expect(resolveCapability("candles", { region: "KR" })).toEqual({ available: true });
  });

  it("candles × US 는 가용", () => {
    expect(resolveCapability("candles", { region: "US" })).toEqual({ available: true });
  });

  it("모든 capability × UNKNOWN 은 불가 + 이유", () => {
    const capabilities: PanelCapability[] = [
      "candles",
      "quote",
      "orderbook",
      "financials",
      "disclosure",
      "news",
      "flow",
      "peers",
      "positions",
      "botState",
      "researchDocs",
      "aiConsole",
    ];
    for (const capability of capabilities) {
      expect(resolveCapability(capability, { region: "UNKNOWN" })).toEqual({
        available: false,
        reason: "시장 정보를 알 수 없는 종목입니다",
        because: "no-source",
      });
    }
  });

  it("orderbook × KR 은 가용 (미국만 불가여야 한다 — 대칭 실수 방지)", () => {
    expect(resolveCapability("orderbook", { region: "KR" })).toEqual({ available: true });
  });

  it("flow × KR 은 가용 (미국만 불가여야 한다 — 대칭 실수 방지)", () => {
    expect(resolveCapability("flow", { region: "KR" })).toEqual({ available: true });
  });
});
