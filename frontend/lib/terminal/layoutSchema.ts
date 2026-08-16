import type { PanelInstance, TerminalLayout } from "@/types/terminal/layout";
import { DEFAULT_LAYOUT, cloneLayout } from "./layoutDefaults";

export const LAYOUT_SCHEMA_VERSION = 2;

export type LayoutMigration = (input: Record<string, unknown>) => Record<string, unknown>;

/**
 * v1 → v2 — 자유 배치를 걷어내며 좌표 배열(`grid`)이 사라졌다(화면 결정 §20.2).
 *
 * **떼어내기만 하고 나머지는 그대로 넘긴다.** 옛 저장본에서 살릴 것은 「무엇이 열려 있었는가」
 * (`panels`)이고, 그것은 새 셸에서도 뜻이 같다. 좌표를 버린다고 저장본 전체를 폴백시키면
 * 사람이 열어 둔 패널 구성이 조용히 사라진다.
 */
function dropGrid(input: Record<string, unknown>): Record<string, unknown> {
  const { grid: _grid, ...rest } = input;
  return { ...rest, schemaVersion: 2 };
}

/** 키는 "적용하면 도달하는 버전" */
export const LAYOUT_MIGRATIONS: Record<number, LayoutMigration> = {
  2: dropGrid,
};

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isValidPanelInstance(value: unknown): value is PanelInstance {
  return (
    isPlainObject(value) &&
    typeof value.instanceId === "string" &&
    typeof value.type === "string" &&
    typeof value.collapsed === "boolean" &&
    isPlainObject(value.settings)
  );
}

function isValidLayoutShape(value: Record<string, unknown>): value is Record<string, unknown> & TerminalLayout {
  return (
    typeof value.schemaVersion === "number" && Array.isArray(value.panels) && value.panels.every(isValidPanelInstance)
  );
}

/**
 * 손상되거나 낯선 버전의 저장 배치를 기본 레이아웃으로 안전하게 되돌린다.
 * `recovered: true` 는 폴백이 실제로 일어났다는 뜻이며, 호출자가 사용자에게 알려야 한다.
 */
export function migrateLayout(
  raw: unknown,
  migrations: Record<number, LayoutMigration> = LAYOUT_MIGRATIONS,
): { layout: TerminalLayout; recovered: boolean } {
  if (raw === null || raw === undefined) {
    return { layout: cloneLayout(DEFAULT_LAYOUT), recovered: false };
  }
  if (!isPlainObject(raw)) {
    return { layout: cloneLayout(DEFAULT_LAYOUT), recovered: true };
  }

  const startVersion = typeof raw.schemaVersion === "number" ? raw.schemaVersion : NaN;
  if (Number.isNaN(startVersion)) {
    return { layout: cloneLayout(DEFAULT_LAYOUT), recovered: true };
  }

  let current: Record<string, unknown> = raw;
  let version = startVersion;

  try {
    while (version < LAYOUT_SCHEMA_VERSION) {
      const migrate = migrations[version + 1];
      if (!migrate) {
        return { layout: cloneLayout(DEFAULT_LAYOUT), recovered: true };
      }
      current = migrate(current);
      version += 1;
    }
  } catch {
    return { layout: cloneLayout(DEFAULT_LAYOUT), recovered: true };
  }

  if (version !== LAYOUT_SCHEMA_VERSION || !isValidLayoutShape(current)) {
    return { layout: cloneLayout(DEFAULT_LAYOUT), recovered: true };
  }

  return { layout: { schemaVersion: current.schemaVersion, panels: current.panels }, recovered: false };
}

/**
 * 레지스트리에 없는 패널 타입은 렌더하지 않되 저장본에서 지우지 않는다 (FE-AD-8).
 * `preserved` 는 렌더하지 않지만 저장본에 남는다.
 */
export function pruneUnknownPanels(
  layout: TerminalLayout,
  knownTypes: string[],
): { renderable: PanelInstance[]; preserved: PanelInstance[] } {
  const known = new Set(knownTypes);
  const renderable: PanelInstance[] = [];
  const preserved: PanelInstance[] = [];
  for (const panel of layout.panels) {
    (known.has(panel.type) ? renderable : preserved).push(panel);
  }
  return { renderable, preserved };
}
