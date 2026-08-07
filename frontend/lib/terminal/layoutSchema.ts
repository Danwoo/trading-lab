import type { GridCell, PanelInstance, TerminalLayout } from "@/types/terminal/layout";
import { DEFAULT_LAYOUT, cloneLayout } from "./layoutDefaults";

export const LAYOUT_SCHEMA_VERSION = 1;

export type LayoutMigration = (input: Record<string, unknown>) => Record<string, unknown>;

/** 키는 "적용하면 도달하는 버전". v1 이 최초라 지금은 비어 있다 */
export const LAYOUT_MIGRATIONS: Record<number, LayoutMigration> = {};

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isValidGridCell(value: unknown): value is GridCell {
  return (
    isPlainObject(value) &&
    typeof value.i === "string" &&
    typeof value.x === "number" &&
    typeof value.y === "number" &&
    typeof value.w === "number" &&
    typeof value.h === "number"
  );
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
    typeof value.schemaVersion === "number" &&
    Array.isArray(value.panels) &&
    value.panels.every(isValidPanelInstance) &&
    Array.isArray(value.grid) &&
    value.grid.every(isValidGridCell)
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

  return { layout: current, recovered: false };
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
