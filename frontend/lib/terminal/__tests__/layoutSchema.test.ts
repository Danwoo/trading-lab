import { describe, expect, it } from "vitest";
import { migrateLayout, pruneUnknownPanels, LAYOUT_SCHEMA_VERSION } from "@/lib/terminal/layoutSchema";
import type { LayoutMigration } from "@/lib/terminal/layoutSchema";
import type { TerminalLayout } from "@/types/terminal/layout";

describe("migrateLayout", () => {
  it("① 정상 v1 입력은 손상 없이 그대로 통과한다", () => {
    const raw = {
      schemaVersion: LAYOUT_SCHEMA_VERSION,
      panels: [{ instanceId: "chart-1", type: "chart", collapsed: false, settings: {} }],
      grid: [{ i: "chart-1", x: 0, y: 0, w: 8, h: 8 }],
    };

    const result = migrateLayout(raw);

    expect(result.recovered).toBe(false);
    expect(result.layout).toEqual(raw);
  });

  it("② schemaVersion 누락 → 기본 레이아웃 폴백 + recovered:true", () => {
    const raw = { panels: [], grid: [] };

    const result = migrateLayout(raw);

    expect(result.recovered).toBe(true);
    expect(result.layout.schemaVersion).toBe(LAYOUT_SCHEMA_VERSION);
    expect(result.layout.panels.length).toBeGreaterThan(0);
  });

  it("③ 배열이 아닌 panels → 폴백", () => {
    const raw = { schemaVersion: LAYOUT_SCHEMA_VERSION, panels: { not: "an array" }, grid: [] };

    const result = migrateLayout(raw);

    expect(result.recovered).toBe(true);
  });

  it("④ 알 수 없는 미래 버전(2) → 폴백", () => {
    const raw = { schemaVersion: 2, panels: [], grid: [] };

    const result = migrateLayout(raw);

    expect(result.recovered).toBe(true);
    expect(result.layout.schemaVersion).toBe(LAYOUT_SCHEMA_VERSION);
  });

  it("⑤ 주입한 가짜 마이그레이션 2개가 순차 적용된다", () => {
    // schemaVersion 을 일부러 실제 LAYOUT_SCHEMA_VERSION 아래(-1)로 낮춰 두 홉짜리 사슬을 강제한다.
    const raw = { schemaVersion: -1, panels: [], grid: [] };
    const hops: string[] = [];
    const fakeMigrations: Record<number, LayoutMigration> = {
      0: (input) => {
        hops.push("−1→0");
        return { ...input, schemaVersion: 0 };
      },
      1: (input) => {
        hops.push("0→1");
        return { ...input, schemaVersion: LAYOUT_SCHEMA_VERSION };
      },
    };

    const result = migrateLayout(raw, fakeMigrations);

    expect(hops).toEqual(["−1→0", "0→1"]);
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
      grid: [
        { i: "chart-1", x: 0, y: 0, w: 8, h: 8 },
        { i: "ghost-1", x: 8, y: 0, w: 4, h: 8 },
      ],
    };

    const { renderable, preserved } = pruneUnknownPanels(layout, ["chart", "symbol-info"]);

    expect(renderable.map((p) => p.instanceId)).toEqual(["chart-1"]);
    expect(preserved.map((p) => p.instanceId)).toEqual(["ghost-1"]);
  });

  it("⑦ 마이그레이션 함수가 예외를 던지면 폴백 + recovered:true", () => {
    const raw = { schemaVersion: 0, panels: [], grid: [] };
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
