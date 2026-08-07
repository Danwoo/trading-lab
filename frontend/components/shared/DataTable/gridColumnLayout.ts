// components/shared/DataTable/gridColumnLayout.ts
//
// DataTable 이 쓰는 순수 레이아웃 계산 — 컬럼 리사이즈 폭 클램프와 고정(fixed) 컬럼의 sticky
// 오프셋. React·TanStack Table 훅에 기대지 않는다 — gridQuery.ts 와 같은 이유로 분리한다:
// vitest 는 "node" 환경만 쓰므로(O0, #262) 렌더 없이 이 계산만 직접 테스트할 수 있어야 한다
// (이슈 #242 O1 2단계).

export const DEFAULT_MIN_COLUMN_WIDTH = 40;
export const COLUMN_RESIZE_STEP_PX = 12;

/** 리사이즈 결과 폭을 최소폭 이상, 정수 픽셀로 고정한다. 키보드 리사이즈(화살표 키)가 쓴다. */
export function clampColumnWidth(width: number, minWidth: number = DEFAULT_MIN_COLUMN_WIDTH): number {
  return Math.max(minWidth, Math.round(width));
}

export interface StickyColumnInput {
  field: string;
  fixed?: "left" | "right";
  size: number;
}

export interface StickyPlacement {
  position: "left" | "right";
  /** 스크롤 컨테이너 가장자리로부터의 픽셀 오프셋 — CSS `left`/`right` 값으로 그대로 쓴다. */
  offset: number;
  /** 고정 블록의 경계 컬럼(스크롤 콘텐츠와 맞닿는 쪽)이면 true — 그림자는 여기에만 그린다. */
  isBoundary: boolean;
}

/**
 * 고정(`fixed`) 컬럼들의 sticky 오프셋을 계산한다.
 * - `fixed: "left"`: 테이블 순서대로 왼쪽 가장자리부터 누적한다 — 첫 번째 left-fixed 컬럼이
 *   offset 0, 그다음이 그 폭만큼 뒤로.
 * - `fixed: "right"`: 오른쪽 가장자리에 가장 가까운(=테이블 순서상 나중) 컬럼부터 거꾸로
 *   누적한다 — 마지막 right-fixed 컬럼이 offset 0.
 * 고정되지 않은 컬럼은 결과 맵에 없다(스크롤과 함께 흐르는 일반 컬럼).
 */
export function computeStickyOffsets(columns: StickyColumnInput[]): Record<string, StickyPlacement> {
  const placements: Record<string, StickyPlacement> = {};

  const leftColumns = columns.filter((column) => column.fixed === "left");
  let leftOffset = 0;
  leftColumns.forEach((column, index) => {
    placements[column.field] = { position: "left", offset: leftOffset, isBoundary: index === leftColumns.length - 1 };
    leftOffset += column.size;
  });

  const rightColumns = columns.filter((column) => column.fixed === "right");
  let rightOffset = 0;
  for (let index = rightColumns.length - 1; index >= 0; index -= 1) {
    const column = rightColumns[index];
    placements[column.field] = { position: "right", offset: rightOffset, isBoundary: index === 0 };
    rightOffset += column.size;
  }

  return placements;
}

export interface ColumnLayoutEntry {
  /** 현재 폭(px) — TanStack 의 `header.column.getSize()` 를 그대로 담는다. */
  width: number;
  /** `fixed` 컬럼일 때만 존재한다. */
  sticky?: StickyPlacement;
}

/** 필드명 → 현재 레이아웃(폭·sticky 배치). DataTableHeader·DataTableBody 가 함께 쓴다. */
export type ColumnLayoutMap = Record<string, ColumnLayoutEntry>;

// 고정 컬럼 블록과 스크롤 콘텐츠의 경계에만 그리는 그림자 — 앱 전역에 이미 있는 그림자 톤
// (기존 DataGrid/*, 미검토)과 정확히 맞추는 것은 O10(시각 방향) 판단 영역이라 임의로 베끼지
// 않고, sticky 경계라는 기능 자체를 드러내는 최소한의 값만 쓴다.
export const STICKY_SHADOW_CLASS: Record<"left" | "right", string> = {
  left: "shadow-[2px_0_4px_-2px_rgba(0,0,0,0.15)]",
  right: "shadow-[-2px_0_4px_-2px_rgba(0,0,0,0.15)]",
};
