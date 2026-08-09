import { describe, expect, it } from "vitest";
import { isRegionIndependent, listCapabilities, resolveCapability } from "@/lib/terminal/capabilityMatrix";

describe("resolveCapability", () => {
  it("orderbook × US 는 불가 + 이유", () => {
    const verdict = resolveCapability("orderbook", { region: "US" });
    expect(verdict).toEqual({ available: false, reason: "미국 심층 호가는 확보된 소스가 없습니다" });
  });

  it("flow × US 는 불가 + 이유", () => {
    const verdict = resolveCapability("flow", { region: "US" });
    expect(verdict).toEqual({
      available: false,
      reason: "미국에는 투자자별 수급 개념이 없습니다 — 기관 보유·공매도 잔고로 대체 예정",
    });
  });

  it("candles × KR 은 가용", () => {
    expect(resolveCapability("candles", { region: "KR" })).toEqual({ available: true });
  });

  it("candles × US 는 가용", () => {
    expect(resolveCapability("candles", { region: "US" })).toEqual({ available: true });
  });

  // 목록을 손으로 적으면 capability 가 늘 때 조용히 새므로 매트릭스에서 전수를 받아 훑는다.
  it("시장 축이 걸리는 capability × UNKNOWN 은 전부 불가 + 이유", () => {
    const regionScoped = listCapabilities().filter((capability) => !isRegionIndependent(capability));

    expect(regionScoped.length).toBeGreaterThan(0);
    for (const capability of regionScoped) {
      expect(resolveCapability(capability, { region: "UNKNOWN" })).toEqual({
        available: false,
        reason: "시장 정보를 알 수 없는 종목입니다",
      });
    }
  });

  it("시장 무관 capability 는 UNKNOWN 에서도 가용 — 종목을 고르기 전에 열려야 한다", () => {
    const regionIndependent = listCapabilities().filter(isRegionIndependent);

    expect(regionIndependent).toContain("dataIngest");
    for (const capability of regionIndependent) {
      for (const region of ["KR", "US", "UNKNOWN"] as const) {
        expect(resolveCapability(capability, { region })).toEqual({ available: true });
      }
    }
  });

  it("orderbook × KR 은 가용 (미국만 불가여야 한다 — 대칭 실수 방지)", () => {
    expect(resolveCapability("orderbook", { region: "KR" })).toEqual({ available: true });
  });

  it("flow × KR 은 가용 (미국만 불가여야 한다 — 대칭 실수 방지)", () => {
    expect(resolveCapability("flow", { region: "KR" })).toEqual({ available: true });
  });
});
