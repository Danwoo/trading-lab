import type { StrategyField } from "@/schemas/bot/bot";

/**
 * 전략 폼 필드 하나가 훑을 값 목록 — 선언된 min~max 를 `count` 개로 고르게 자른다.
 *
 * 격자는 봉우리 하나가 아니라 **지형**을 보는 도구다(스펙 D-Q1) — 그래서 기본값 주변이 아니라
 * 선언 범위 전체를 훑는다. 값은 필드의 `step` 배수로 눌러 전략이 못 받는 값을 만들지 않고,
 * 눌러서 겹친 값은 하나로 줄인다 (칸 수가 곧 시도 수라 겹친 칸은 시도만 태운다 — §8.5.2).
 */
export function sweepValues(field: StrategyField, count: number): number[] {
  const min = field.min;
  const max = field.max;
  if (min === undefined || max === undefined || count < 1) return [];
  if (min === max || count === 1) return [min];

  const step = field.step && field.step > 0 ? field.step : null;
  const values: number[] = [];
  for (let i = 0; i < count; i++) {
    let value = min + ((max - min) * i) / (count - 1);
    if (step !== null) value = min + Math.round((value - min) / step) * step;
    // 부동소수 잔재(0.30000000000000004)를 자른다 — 이 값이 그대로 params 가 된다.
    value = Number(value.toFixed(10));
    if (value >= min && value <= max && !values.includes(value)) values.push(value);
  }
  return values;
}
