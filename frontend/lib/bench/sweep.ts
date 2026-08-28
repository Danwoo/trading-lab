import type { StrategyField } from "@/schemas/bot/bot";

/**
 * 축 하나가 훑는 칸 수의 범위 — 아래는 양 끝점(1칸은 축이 아니다), 위는 두 축이 81칸으로 표에
 * 읽히는 선. 폼의 네이티브 `min`/`max` 와 상태가 받는 범위가 **같은 숫자**여야 한다 — 갈리면
 * 폼은 큰 칸 수를 약속하고 제출은 브라우저 제약에 조용히 막힌다 (#398).
 */
export const STEPS_MIN = 2;
export const STEPS_MAX = 9;

/**
 * 칸 수를 폼이 선언한 제약 안으로 누른다 — 범위(`min`/`max`)와 **눈금(`step`=1)** 둘 다.
 *
 * 눈금을 빼면 범위 안 소수(`5.5`)가 상태에 그대로 앉는다. 칸이 곧 시도라 반 칸은 애초에 없고,
 * 네이티브 `step` 위반이라 제출은 `onSubmit` 에 닿기 전에 막힌다 — 범위만 눌러서는 #398 의
 * 침묵이 그대로 남는다.
 */
export function clampSteps(steps: number): number {
  return Math.min(STEPS_MAX, Math.max(STEPS_MIN, Math.round(steps)));
}

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
