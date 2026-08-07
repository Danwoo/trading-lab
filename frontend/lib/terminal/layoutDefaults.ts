import type { TerminalLayout } from "@/types/terminal/layout";

/**
 * 리터럴 1 — `LAYOUT_SCHEMA_VERSION` 을 import 하면 `layoutSchema.ts` 와 순환 참조가
 * 생긴다(그쪽이 폴백값으로 이 파일의 `DEFAULT_LAYOUT` 을 가져간다). 스키마 버전이 오르면
 * 이 값도 함께 올린다.
 */
const DEFAULT_LAYOUT_SCHEMA_VERSION = 1;

/**
 * M2 기본 레이아웃 — 패널 타입 문자열은 O3 패널 레지스트리의 키와 반드시 일치해야 한다.
 * 지금 배치되는 것은 "chart"·"symbol-info" 둘뿐, 나머지 8종(orderbook·news·bot-state·
 * positions·peers·flow·research·ai-console)은 닫힌 상태로 목록에서만 존재한다.
 */
export const DEFAULT_LAYOUT: TerminalLayout = {
  schemaVersion: DEFAULT_LAYOUT_SCHEMA_VERSION,
  panels: [
    { instanceId: "chart-1", type: "chart", collapsed: false, settings: {} },
    { instanceId: "symbol-info-1", type: "symbol-info", collapsed: false, settings: {} },
  ],
  grid: [
    { i: "chart-1", x: 0, y: 0, w: 8, h: 8 },
    { i: "symbol-info-1", x: 8, y: 0, w: 4, h: 8 },
  ],
};

/** `DEFAULT_LAYOUT` 은 모듈 싱글턴이다 — 호출자가 그대로 들고 있다 mutate 하지 않도록 매번 얕은 복제본을 낸다. */
export function cloneLayout(layout: TerminalLayout): TerminalLayout {
  return {
    schemaVersion: layout.schemaVersion,
    panels: layout.panels.map((panel) => ({ ...panel, settings: { ...panel.settings } })),
    grid: layout.grid.map((cell) => ({ ...cell })),
  };
}
