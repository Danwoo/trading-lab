import type { PanelInstance, TerminalLayout } from "@/types/terminal/layout";
import { DEFAULT_LAYOUT, cloneLayout } from "./layoutDefaults";

export const LAYOUT_SCHEMA_VERSION = 3;

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

/**
 * v2 → v3 — 패널 두 종(호가·봇 상태)이 생겼다. **옛 저장본에 없으면 덧붙인다.**
 *
 * 덧붙이는 쪽을 고른 이유: 이 저장본은 「내가 고른 구성」이 아니라 대부분 **기본값이 굳은 것**
 * 이다(패널을 고르는 UI 가 아직 없다). 그대로 두면 새 패널이 생겨도 아무에게도 안 보인다.
 * 패널을 스스로 닫을 수 있게 되면 이 마이그레이션은 「닫은 것을 되살리는」 동작이 되므로,
 * 그때는 이 방식을 다시 판단해야 한다 — 지금은 닫기가 곧 이 세션 한정이라 문제되지 않는다.
 */
function addPanelsIntroducedInV3(input: Record<string, unknown>): Record<string, unknown> {
  // 깨진 저장본은 **고치지 않는다** — 여기서 빈 배열을 만들어 주면 뒤의 검증이 통과해 버려
  // 폴백이 사라진다(그물이 실제로 잡았다). 모양이 아니면 그대로 흘려보내고 검증이 판정한다.
  if (!Array.isArray(input.panels)) return { ...input, schemaVersion: 3 };
  const panels = [...(input.panels as PanelInstance[])];
  const existing = new Set(panels.map((panel) => panel?.type));
  for (const [type, instanceId] of [
    ["orderbook", "orderbook-1"],
    ["bot-state", "bot-state-1"],
  ] as const) {
    if (!existing.has(type)) panels.push({ instanceId, type, collapsed: false, settings: {} });
  }
  return { ...input, panels, schemaVersion: 3 };
}

/** 키는 "적용하면 도달하는 버전" */
export const LAYOUT_MIGRATIONS: Record<number, LayoutMigration> = {
  2: dropGrid,
  3: addPanelsIntroducedInV3,
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
