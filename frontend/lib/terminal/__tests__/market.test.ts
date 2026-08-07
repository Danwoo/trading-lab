import { describe, expect, it } from "vitest";
import { resolveRegion } from "@/lib/terminal/market";

describe("resolveRegion", () => {
  it.each([
    ["KOSPI", "KR"],
    ["KOSDAQ", "KR"],
    ["NASDAQ", "US"],
    ["NYSE", "US"],
  ] as const)("%s -> %s", (market, region) => {
    expect(resolveRegion(market)).toBe(region);
  });

  it("소문자 입력도 대소문자 무시로 판정한다", () => {
    expect(resolveRegion("kospi")).toBe("KR");
    expect(resolveRegion("nasdaq")).toBe("US");
  });

  it("undefined·null 은 UNKNOWN", () => {
    expect(resolveRegion(undefined)).toBe("UNKNOWN");
    expect(resolveRegion(null)).toBe("UNKNOWN");
  });

  it("미등록 시장은 UNKNOWN", () => {
    expect(resolveRegion("LSE")).toBe("UNKNOWN");
    expect(resolveRegion("")).toBe("UNKNOWN");
  });
});
