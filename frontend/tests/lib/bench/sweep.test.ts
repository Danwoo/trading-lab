// 훑기 값 생성 — 선언 범위 전체를 고르게, step 배수로 (#203).
import { describe, expect, it } from "vitest";

import { sweepValues } from "@/lib/bench/sweep";
import type { StrategyField } from "@/schemas/bot/bot";

function field(overrides: Partial<StrategyField>): StrategyField {
  return { name: "p", label: "p", control: "number", default: 0, ...overrides };
}

describe("sweepValues", () => {
  it("min~max 를 고르게 자른다", () => {
    expect(sweepValues(field({ min: 0, max: 100 }), 5)).toEqual([0, 25, 50, 75, 100]);
  });

  it("step 배수로 누른다 — 전략이 못 받는 값을 만들지 않는다", () => {
    // 5~120 을 5칸: 눌리기 전 [5, 33.75, 62.5, 91.25, 120] → step 1 로 반올림
    expect(sweepValues(field({ min: 5, max: 120, step: 1 }), 5)).toEqual([5, 34, 63, 91, 120]);
  });

  it("소수 step 도 부동소수 잔재 없이 나온다", () => {
    expect(sweepValues(field({ min: 0.5, max: 15, step: 0.5 }), 4)).toEqual([0.5, 5.5, 10, 15]);
  });

  it("눌러서 겹친 값은 하나로 줄인다 — 겹친 칸은 시도만 태운다 (§8.5.2)", () => {
    const values = sweepValues(field({ min: 1, max: 3, step: 1 }), 7);
    expect(values).toEqual([1, 2, 3]);
  });

  it("범위 선언이 없으면 훑지 않는다", () => {
    expect(sweepValues(field({}), 5)).toEqual([]);
  });

  it("min === max 면 한 값이다", () => {
    expect(sweepValues(field({ min: 7, max: 7 }), 5)).toEqual([7]);
  });
});
