import type { TerminalLayout } from "@/types/terminal/layout";

/**
 * 리터럴 2 — `LAYOUT_SCHEMA_VERSION` 을 import 하면 `layoutSchema.ts` 와 순환 참조가
 * 생긴다(그쪽이 폴백값으로 이 파일의 `DEFAULT_LAYOUT` 을 가져간다). 스키마 버전이 오르면
 * 이 값도 함께 올린다.
 */
const DEFAULT_LAYOUT_SCHEMA_VERSION = 2;

/**
 * 「시세」 화면의 기본 패널 구성 — 패널 타입 문자열은 패널 레지스트리의 키와 반드시 일치해야
 * 한다. 순서가 곧 화면에 놓이는 순서다(자유 배치를 걷어낸 뒤로 좌표는 없다).
 */
export const DEFAULT_LAYOUT: TerminalLayout = {
  schemaVersion: DEFAULT_LAYOUT_SCHEMA_VERSION,
  panels: [
    { instanceId: "chart-1", type: "chart", collapsed: false, settings: {} },
    { instanceId: "symbol-info-1", type: "symbol-info", collapsed: false, settings: {} },
  ],
};

/** `DEFAULT_LAYOUT` 은 모듈 싱글턴이다 — 호출자가 그대로 들고 있다 mutate 하지 않도록 매번 얕은 복제본을 낸다. */
export function cloneLayout(layout: TerminalLayout): TerminalLayout {
  return {
    schemaVersion: layout.schemaVersion,
    panels: layout.panels.map((panel) => ({ ...panel, settings: { ...panel.settings } })),
  };
}
