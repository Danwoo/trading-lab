import { describe, expect, it } from "vitest";
import { migrateLayout, pruneUnknownPanels, LAYOUT_SCHEMA_VERSION } from "@/lib/terminal/layoutSchema";
import type { LayoutMigration } from "@/lib/terminal/layoutSchema";
import type { TerminalLayout } from "@/types/terminal/layout";

describe("migrateLayout", () => {
  it("① 정상 현행 버전 입력은 손상 없이 그대로 통과한다", () => {
    const raw = {
      schemaVersion: LAYOUT_SCHEMA_VERSION,
      panels: [{ instanceId: "chart-1", type: "chart", collapsed: false, settings: {} }],
    };

    const result = migrateLayout(raw);

    expect(result.recovered).toBe(false);
    expect(result.layout).toEqual(raw);
  });

  it("② schemaVersion 누락 → 기본 레이아웃 폴백 + recovered:true", () => {
    const raw = { panels: [] };

    const result = migrateLayout(raw);

    expect(result.recovered).toBe(true);
    expect(result.layout.schemaVersion).toBe(LAYOUT_SCHEMA_VERSION);
    expect(result.layout.panels.length).toBeGreaterThan(0);
  });

  it("③ 배열이 아닌 panels → 폴백", () => {
    const raw = { schemaVersion: LAYOUT_SCHEMA_VERSION, panels: { not: "an array" } };

    const result = migrateLayout(raw);

    expect(result.recovered).toBe(true);
  });

  it("④ 알 수 없는 미래 버전 → 폴백", () => {
    const raw = { schemaVersion: LAYOUT_SCHEMA_VERSION + 1, panels: [] };

    const result = migrateLayout(raw);

    expect(result.recovered).toBe(true);
    expect(result.layout.schemaVersion).toBe(LAYOUT_SCHEMA_VERSION);
  });

  it("⑤ 주입한 가짜 마이그레이션 2개가 순차 적용된다", () => {
    // schemaVersion 을 일부러 현행보다 두 홉 아래로 낮춰 사슬을 강제한다.
    const raw = { schemaVersion: LAYOUT_SCHEMA_VERSION - 2, panels: [] };
    const hops: string[] = [];
    const fakeMigrations: Record<number, LayoutMigration> = {
      [LAYOUT_SCHEMA_VERSION - 1]: (input) => {
        hops.push("첫 홉");
        return { ...input, schemaVersion: LAYOUT_SCHEMA_VERSION - 1 };
      },
      [LAYOUT_SCHEMA_VERSION]: (input) => {
        hops.push("둘째 홉");
        return { ...input, schemaVersion: LAYOUT_SCHEMA_VERSION };
      },
    };

    const result = migrateLayout(raw, fakeMigrations);

    expect(hops).toEqual(["첫 홉", "둘째 홉"]);
    expect(result.recovered).toBe(false);
    expect(result.layout.schemaVersion).toBe(LAYOUT_SCHEMA_VERSION);
  });

  it("⑥ pruneUnknownPanels 가 모르는 타입을 preserved 로 분리하고 renderable 에서 뺀다", () => {
    const layout: TerminalLayout = {
      schemaVersion: LAYOUT_SCHEMA_VERSION,
      panels: [
        { instanceId: "chart-1", type: "chart", collapsed: false, settings: {} },
        { instanceId: "ghost-1", type: "retired-panel-type", collapsed: false, settings: {} },
      ],
    };

    const { renderable, preserved } = pruneUnknownPanels(layout, ["chart", "symbol-info"]);

    expect(renderable.map((p) => p.instanceId)).toEqual(["chart-1"]);
    expect(preserved.map((p) => p.instanceId)).toEqual(["ghost-1"]);
  });

  it("⑦ 마이그레이션 함수가 예외를 던지면 폴백 + recovered:true", () => {
    const raw = { schemaVersion: 0, panels: [] };
    const throwingMigrations: Record<number, LayoutMigration> = {
      1: () => {
        throw new Error("마이그레이션 실패");
      },
    };

    const result = migrateLayout(raw, throwingMigrations);

    expect(result.recovered).toBe(true);
    expect(result.layout.schemaVersion).toBe(LAYOUT_SCHEMA_VERSION);
  });

  it("raw 가 null·undefined 면 손상이 아니라 '저장본 없음'으로 취급해 알리지 않는다", () => {
    expect(migrateLayout(null).recovered).toBe(false);
    expect(migrateLayout(undefined).recovered).toBe(false);
  });

  it("raw 가 객체가 아니면(문자열·배열) 폴백 + recovered:true", () => {
    expect(migrateLayout("완전히 깨진 문자열").recovered).toBe(true);
    expect(migrateLayout([1, 2, 3]).recovered).toBe(true);
  });

  it("migrateLayout 이 반환한 기본 레이아웃은 호출마다 새 참조다(공유 뮤테이션 방지)", () => {
    const a = migrateLayout(undefined).layout;
    const b = migrateLayout(undefined).layout;

    expect(a).not.toBe(b);
    expect(a.panels).not.toBe(b.panels);
  });
});

/**
 * 자유 배치를 걷어내기 전(v1)에 저장된 배치는 실제 사람의 localStorage 에 남아 있다.
 * 좌표가 사라졌다는 이유로 저장본 전체를 버리면 열어 두었던 패널 구성이 조용히 없어진다.
 */
describe("v1 → v2 — 좌표(grid) 가 있던 옛 저장본", () => {
  const V1_SAVED_LAYOUT = {
    schemaVersion: 1,
    panels: [
      { instanceId: "chart-1", type: "chart", collapsed: false, settings: { interval: "1d" } },
      { instanceId: "symbol-info-1", type: "symbol-info", collapsed: true, settings: {} },
    ],
    grid: [
      { i: "chart-1", x: 3, y: 3, w: 6, h: 6 },
      { i: "symbol-info-1", x: 9, y: 0, w: 3, h: 6 },
    ],
  };

  it("복원이 깨지지 않는다 — 폴백하지 않고 열려 있던 패널이 그대로 살아난다", () => {
    const result = migrateLayout(structuredClone(V1_SAVED_LAYOUT));

    expect(result.recovered).toBe(false);
    expect(result.layout.schemaVersion).toBe(LAYOUT_SCHEMA_VERSION);
    // 열려 있던 패널은 **그대로**(설정·접힘까지) 앞에 남는다. 뒤에 붙는 것은 v3 이 들여온
    // 새 패널이고, 그것 때문에 옛 구성이 바뀌면 안 된다.
    expect(result.layout.panels.slice(0, V1_SAVED_LAYOUT.panels.length)).toEqual(V1_SAVED_LAYOUT.panels);
    expect(result.layout.panels.map((panel) => panel.type)).toEqual(["chart", "symbol-info", "orderbook", "bot-state"]);
  });

  it("좌표는 떨어져 나간다 — 새 스키마에 grid 라는 자리가 없다", () => {
    const result = migrateLayout(structuredClone(V1_SAVED_LAYOUT));

    expect(Object.keys(result.layout).sort()).toEqual(["panels", "schemaVersion"]);
  });

  it("좌표만 있고 panels 가 깨진 v1 저장본은 그대로 폴백한다 — 마이그레이션이 검증을 무르게 하지 않는다", () => {
    const result = migrateLayout({ schemaVersion: 1, panels: "not-an-array", grid: [] });

    expect(result.recovered).toBe(true);
  });
});
