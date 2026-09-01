/**
 * 곡선 렌더 전 순수 계산 — 다운샘플(LTTB)과 낙폭 시계열.
 *
 * 스펙 §5 「곡선 렌더 → 픽셀 단위 다운샘플(M4 또는 LTTB)」. 원본 점을 다 던지면 긴 구간에서
 * 렌더가 예산(링크된 뷰 갱신 ≤500ms)을 깬다. LTTB 를 고른 이유 — M4 는 픽셀 컬럼별
 * min/max/first/last 로 극값 보존에 강하지만 버킷당 4점을 내 선 차트에선 지그재그가 남고,
 * LTTB 는 삼각형 면적 기준으로 **선의 모양**을 보존한다. 자산곡선은 극값 하나보다 추세·낙폭의
 * 모양이 판정 재료라 LTTB 가 맞다.
 */

export interface XyPoint {
  x: number;
  y: number;
}

/**
 * Largest-Triangle-Three-Buckets. 점 수가 `threshold` 이하면 그대로 돌려준다.
 * 첫 점과 끝 점은 항상 살아남는다 — 구간의 시작·끝 값이 바뀌면 지표와 화면이 어긋난다.
 */
export function downsampleLttb(points: XyPoint[], threshold: number): XyPoint[] {
  if (threshold >= points.length || threshold < 3) return points;

  const sampled: XyPoint[] = [points[0]];
  const bucketSize = (points.length - 2) / (threshold - 2);
  let previous = points[0];

  for (let bucket = 0; bucket < threshold - 2; bucket++) {
    const rangeStart = Math.floor(bucket * bucketSize) + 1;
    const rangeEnd = Math.min(Math.floor((bucket + 1) * bucketSize) + 1, points.length - 1);

    // 다음 버킷의 평균점 — 마지막 버킷의 다음은 끝 점이다.
    const nextStart = Math.min(Math.floor((bucket + 1) * bucketSize) + 1, points.length - 1);
    const nextEnd = Math.min(Math.floor((bucket + 2) * bucketSize) + 1, points.length);
    let avgX = 0;
    let avgY = 0;
    const nextCount = Math.max(nextEnd - nextStart, 1);
    for (let i = nextStart; i < nextStart + nextCount; i++) {
      const point = points[Math.min(i, points.length - 1)];
      avgX += point.x;
      avgY += point.y;
    }
    avgX /= nextCount;
    avgY /= nextCount;

    let best = points[rangeStart];
    let bestArea = -1;
    for (let i = rangeStart; i < rangeEnd; i++) {
      const point = points[i];
      const area = Math.abs(
        (previous.x - avgX) * (point.y - previous.y) - (previous.x - point.x) * (avgY - previous.y),
      );
      if (area > bestArea) {
        bestArea = area;
        best = point;
      }
    }
    sampled.push(best);
    previous = best;
  }

  sampled.push(points[points.length - 1]);
  return sampled;
}

/**
 * 각 시점의 낙폭 비율(0 또는 음수) — **그때까지의 고점 대비**다 (metrics.py 와 같은 정의).
 * 원금 대비가 아니다. 정의가 어긋나면 곡선의 낙폭과 지표의 MDD 가 서로 다른 말을 한다.
 */
export function drawdownRatios(equity: number[]): number[] {
  let peak = Number.NEGATIVE_INFINITY;
  return equity.map((value) => {
    peak = Math.max(peak, value);
    return peak > 0 ? (value - peak) / peak : 0;
  });
}

/**
 * 곡선의 대체 텍스트 — 곡선은 캔버스라 보조기술에는 아무것도 없다(실측: `role`·`aria-label`·
 * `<title>` 전부 없음, `innerText` 공백). 구간·시작·끝·최대 낙폭을 한 문장으로 주어 「곡선이
 * 있다」는 사실과 요지가 읽히게 한다. 값의 정본은 판정 지표 목록이고 이 문장은 곡선의 이름이다.
 */
export function equityCurveSummary(points: { dt: string; equity: number }[]): string {
  if (points.length === 0) return "";
  const first = points[0];
  const last = points[points.length - 1];
  const won = (value: number) => `${Math.round(value).toLocaleString("ko-KR")}원`;
  const worst = drawdownRatios(points.map((point) => point.equity)).reduce((acc, ratio) => Math.min(acc, ratio), 0);
  const drawdown = (Math.abs(worst) * 100).toLocaleString("ko-KR", { maximumFractionDigits: 1 });
  return `자산곡선과 낙폭 곡선 — ${first.dt} ~ ${last.dt} · 시작 ${won(first.equity)} → 끝 ${won(last.equity)} · 최대 낙폭 ${drawdown}%`;
}
