"use client";

import { useMemo, type ReactNode } from "react";
import { GridLayout, useContainerWidth } from "react-grid-layout";
import type { Layout, LayoutItem } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import { GRID_COLUMNS_COUNT } from "@/constants/terminal";
import type { GridCell } from "@/types/terminal/layout";

export interface PanelGridProps {
  cells: GridCell[];
  onCellsChange: (cells: GridCell[]) => void;
  minSizeByInstanceId?: Record<string, { w: number; h: number }>;
  children: (cell: GridCell) => ReactNode;
}

function toLayoutItems(cells: GridCell[], minSizeByInstanceId?: Record<string, { w: number; h: number }>): Layout {
  return cells.map((cell) => ({
    ...cell,
    minW: minSizeByInstanceId?.[cell.i]?.w,
    minH: minSizeByInstanceId?.[cell.i]?.h,
  }));
}

function toGridCells(layout: Layout): GridCell[] {
  return layout.map(({ i, x, y, w, h }: LayoutItem) => ({ i, x, y, w, h }));
}

/**
 * `react-grid-layout` 를 감싼다 — 라이브러리 타입(`Layout`/`LayoutItem`)은 이 파일 밖으로
 * 나가지 않는다. `GridCell` 만 오간다 (설계 §3.3, O3 명세).
 *
 * 규칙 A(#242 O1 스파이크) — RGL 은 이 `"use client"` 모듈 안에서만 import 한다.
 * 규칙 B — 저장 레이아웃을 렌더 중에 읽지 않는다. 이 컴포넌트는 `cells`(controlled prop)만
 * 그리고, 저장소 읽기는 호출자(TerminalContainer)의 마운트 이펙트가 책임진다.
 */
export function PanelGrid({ cells, onCellsChange, minSizeByInstanceId, children }: PanelGridProps) {
  const { width, containerRef, mounted } = useContainerWidth();
  const layout = useMemo(() => toLayoutItems(cells, minSizeByInstanceId), [cells, minSizeByInstanceId]);

  return (
    <div ref={containerRef} className="h-full w-full overflow-auto">
      {mounted && (
        <GridLayout
          width={width}
          layout={layout}
          gridConfig={{ cols: GRID_COLUMNS_COUNT, rowHeight: 32, margin: [8, 8] }}
          dragConfig={{ handle: ".panel-drag-handle", cancel: ".panel-no-drag" }}
          onLayoutChange={(next) => onCellsChange(toGridCells(next))}
        >
          {cells.map((cell) => (
            <div key={cell.i}>{children(cell)}</div>
          ))}
        </GridLayout>
      )}
    </div>
  );
}
