// 곡선 렌더 전 순수 계산 — LTTB 다운샘플과 낙폭 시계열 (#203, 스펙 §5).
import { describe, expect, it } from "vitest";

import { downsampleLttb, drawdownRatios, type XyPoint } from "@/lib/bench/equityMath";

function line(n: number, fn: (i: number) => number): XyPoint[] {
  return Array.from({ length: n }, (_, i) => ({ x: i, y: fn(i) }));
}

describe("downsampleLttb", () => {
  it("threshold 이하면 원본을 그대로 돌려준다 — 필요 없는 손실을 만들지 않는다", () => {
    const points = line(10, (i) => i);
    expect(downsampleLttb(points, 10)).toBe(points);
    expect(downsampleLttb(points, 50)).toBe(points);
  });

  it("정확히 threshold 개로 줄인다", () => {
    expect(
      downsampleLttb(
        line(1000, (i) => Math.sin(i / 20)),
        100,
      ),
    ).toHaveLength(100);
  });

  it("첫 점과 끝 점은 항상 살아남는다 — 시작·끝 값이 바뀌면 지표와 화면이 어긋난다", () => {
    const points = line(500, (i) => i * 2);
    const sampled = downsampleLttb(points, 20);
    expect(sampled[0]).toEqual(points[0]);
    expect(sampled[sampled.length - 1]).toEqual(points[points.length - 1]);
  });

  it("급락 극점을 버리지 않는다 — 낙폭의 모양이 판정 재료다", () => {
    const points = line(400, (i) => (i === 200 ? -100 : 10));
    const sampled = downsampleLttb(points, 30);
    expect(sampled.some((p) => p.y === -100)).toBe(true);
  });

  it("x 순서가 보존된다", () => {
    const sampled = downsampleLttb(
      line(777, (i) => Math.cos(i / 7) * i),
      50,
    );
    for (let i = 1; i < sampled.length; i++) {
      expect(sampled[i].x).toBeGreaterThan(sampled[i - 1].x);
    }
  });
});

describe("drawdownRatios", () => {
  it("고점 갱신 중엔 0 이다", () => {
    expect(drawdownRatios([100, 110, 120])).toEqual([0, 0, 0]);
  });

  it("그때까지의 고점 대비다 — 원금 대비가 아니다 (metrics.py 와 같은 정의)", () => {
    // 원금 100 → 고점 200 → 150: 원금 대비면 +50% 지만 낙폭은 고점 대비 −25% 다.
    const ratios = drawdownRatios([100, 200, 150]);
    expect(ratios[2]).toBeCloseTo(-0.25);
  });

  it("회복하면 다시 0 으로 돌아온다", () => {
    const ratios = drawdownRatios([100, 80, 100, 90]);
    expect(ratios).toEqual([0, -0.2, 0, -0.1]);
  });

  it("빈 입력은 빈 출력이다", () => {
    expect(drawdownRatios([])).toEqual([]);
  });
});
