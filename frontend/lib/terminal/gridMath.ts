import type { GridCell } from "@/types/terminal/layout";

export type MoveDirection = "up" | "down" | "left" | "right";
export type ResizeAxis = "w" | "h";

const STEP = 1;

/** RGL 의 포인터 드래그와 별개로, 키보드 메뉴가 직접 좌표를 계산해 `applyGrid` 에 넘긴다. */
export function moveCell(cell: GridCell, direction: MoveDirection, columns: number): GridCell {
  switch (direction) {
    case "up":
      return { ...cell, y: Math.max(0, cell.y - STEP) };
    case "down":
      return { ...cell, y: cell.y + STEP };
    case "left":
      return { ...cell, x: Math.max(0, cell.x - STEP) };
    case "right":
      return { ...cell, x: Math.max(0, Math.min(columns - cell.w, cell.x + STEP)) };
  }
}

export function resizeCell(
  cell: GridCell,
  axis: ResizeAxis,
  delta: number,
  columns: number,
  minSize: { w: number; h: number },
): GridCell {
  if (axis === "w") {
    const floor = Math.max(1, minSize.w);
    const ceiling = Math.max(floor, columns - cell.x);
    const w = Math.min(ceiling, Math.max(floor, cell.w + delta));
    return { ...cell, w };
  }
  const floor = Math.max(1, minSize.h);
  const h = Math.max(floor, cell.h + delta);
  return { ...cell, h };
}
