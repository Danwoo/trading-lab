import { describe, expect, it } from "vitest";
import { moveCell, resizeCell } from "@/lib/terminal/gridMath";
import type { GridCell } from "@/types/terminal/layout";

const COLUMNS = 12;

describe("moveCell", () => {
  it("위로 이동한다", () => {
    const cell: GridCell = { i: "a", x: 2, y: 3, w: 4, h: 4 };
    expect(moveCell(cell, "up", COLUMNS)).toEqual({ i: "a", x: 2, y: 2, w: 4, h: 4 });
  });

  it("맨 위에서 위로 이동해도 y=0 을 넘지 않는다", () => {
    const cell: GridCell = { i: "a", x: 2, y: 0, w: 4, h: 4 };
    expect(moveCell(cell, "up", COLUMNS).y).toBe(0);
  });

  it("아래로 이동은 상한이 없다", () => {
    const cell: GridCell = { i: "a", x: 2, y: 3, w: 4, h: 4 };
    expect(moveCell(cell, "down", COLUMNS).y).toBe(4);
  });

  it("왼쪽으로 이동해도 x=0 을 넘지 않는다", () => {
    const cell: GridCell = { i: "a", x: 0, y: 0, w: 4, h: 4 };
    expect(moveCell(cell, "left", COLUMNS).x).toBe(0);
  });

  it("오른쪽으로 이동해도 컬럼 경계를 넘지 않는다 (x+w <= columns)", () => {
    const cell: GridCell = { i: "a", x: 8, y: 0, w: 4, h: 4 };
    expect(moveCell(cell, "right", COLUMNS).x).toBe(8);
  });

  it("오른쪽으로 이동은 경계 안에서는 정상 증가한다", () => {
    const cell: GridCell = { i: "a", x: 2, y: 0, w: 4, h: 4 };
    expect(moveCell(cell, "right", COLUMNS).x).toBe(3);
  });
});

describe("resizeCell", () => {
  const minSize = { w: 2, h: 2 };

  it("너비를 키운다", () => {
    const cell: GridCell = { i: "a", x: 0, y: 0, w: 4, h: 4 };
    expect(resizeCell(cell, "w", 1, COLUMNS, minSize).w).toBe(5);
  });

  it("너비 축소는 minSize 아래로 내려가지 않는다", () => {
    const cell: GridCell = { i: "a", x: 0, y: 0, w: 2, h: 4 };
    expect(resizeCell(cell, "w", -1, COLUMNS, minSize).w).toBe(2);
  });

  it("너비 확대는 컬럼 경계를 넘지 않는다 (x+w <= columns)", () => {
    const cell: GridCell = { i: "a", x: 10, y: 0, w: 2, h: 4 };
    expect(resizeCell(cell, "w", 5, COLUMNS, minSize).w).toBe(2);
  });

  it("높이를 키운다", () => {
    const cell: GridCell = { i: "a", x: 0, y: 0, w: 4, h: 4 };
    expect(resizeCell(cell, "h", 1, COLUMNS, minSize).h).toBe(5);
  });

  it("높이 축소는 minSize 아래로 내려가지 않는다", () => {
    const cell: GridCell = { i: "a", x: 0, y: 0, w: 4, h: 2 };
    expect(resizeCell(cell, "h", -1, COLUMNS, minSize).h).toBe(2);
  });

  it("높이 확대는 상한이 없다", () => {
    const cell: GridCell = { i: "a", x: 0, y: 0, w: 4, h: 4 };
    expect(resizeCell(cell, "h", 10, COLUMNS, minSize).h).toBe(14);
  });
});
