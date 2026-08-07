import { describe, expect, it } from "vitest";

import {
  DEFAULT_MIN_COLUMN_WIDTH,
  clampColumnWidth,
  computeStickyOffsets,
} from "@/components/shared/DataTable/gridColumnLayout";

describe("clampColumnWidth — 컬럼 리사이즈 폭 클램프", () => {
  it("최소폭보다 크면 그대로(반올림만) 통과한다", () => {
    expect(clampColumnWidth(120)).toBe(120);
    expect(clampColumnWidth(120.4)).toBe(120);
    expect(clampColumnWidth(120.6)).toBe(121);
  });

  it("최소폭 아래로는 내려가지 않는다 — 기본값", () => {
    expect(clampColumnWidth(10)).toBe(DEFAULT_MIN_COLUMN_WIDTH);
    expect(clampColumnWidth(0)).toBe(DEFAULT_MIN_COLUMN_WIDTH);
    expect(clampColumnWidth(-50)).toBe(DEFAULT_MIN_COLUMN_WIDTH);
  });

  it("컬럼별 minWidth(GridColumn.minWidth)가 있으면 그것을 바닥으로 쓴다", () => {
    expect(clampColumnWidth(50, 80)).toBe(80);
    expect(clampColumnWidth(100, 80)).toBe(100);
  });
});

describe("computeStickyOffsets — 고정 컬럼 sticky 오프셋", () => {
  it("fixed 가 없는 컬럼은 결과에 없다", () => {
    const result = computeStickyOffsets([{ field: "ticker", size: 100 }]);
    expect(result).toEqual({});
  });

  it("left 고정 컬럼은 테이블 순서대로 왼쪽부터 누적한다", () => {
    const result = computeStickyOffsets([
      { field: "a", fixed: "left", size: 100 },
      { field: "b", fixed: "left", size: 80 },
      { field: "c", size: 120 },
    ]);
    expect(result.a).toEqual({ position: "left", offset: 0, isBoundary: false });
    expect(result.b).toEqual({ position: "left", offset: 100, isBoundary: true });
    expect(result.c).toBeUndefined();
  });

  it("right 고정 컬럼은 테이블 뒤쪽(오른쪽 가장자리에 가까운 컬럼)부터 거꾸로 누적한다", () => {
    const result = computeStickyOffsets([
      { field: "a", size: 100 },
      { field: "b", fixed: "right", size: 90 },
      { field: "c", fixed: "right", size: 60 },
    ]);
    // 테이블 순서상 c 가 더 뒤(오른쪽 가장자리에 더 가깝다) → c 의 offset 이 0.
    expect(result.c).toEqual({ position: "right", offset: 0, isBoundary: false });
    expect(result.b).toEqual({ position: "right", offset: 60, isBoundary: true });
  });

  it("left·right 고정이 섞여도 서로 간섭하지 않는다", () => {
    const result = computeStickyOffsets([
      { field: "pin-left", fixed: "left", size: 50 },
      { field: "middle", size: 100 },
      { field: "pin-right", fixed: "right", size: 70 },
    ]);
    expect(result["pin-left"]).toEqual({ position: "left", offset: 0, isBoundary: true });
    expect(result["pin-right"]).toEqual({ position: "right", offset: 0, isBoundary: true });
    expect(result.middle).toBeUndefined();
  });
});
