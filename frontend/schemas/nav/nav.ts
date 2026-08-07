// schemas/nav/nav.ts
// 타입 전용 + 배럴 우회 — `@/components/shared/Dashboard` 배럴은 `TimeRangePanel` 을 재수출하고
// 그것이 `@/components/shared/ui` 배럴을 거쳐 devextreme 프리미티브 + locale 부수효과에 닿는다.
// #352 가 끊었다고 본 「schemas/* → devextreme」 경로가 이 파일에 하나 남아 있었다(정적 그래프
// 실측 13건). 값 위치에서 안 쓰이는 import 라 SWC 는 어차피 지우지만, `import type` 으로 못
// 박아두지 않으면 다음 편집이 값 import 로 되돌려 놓아도 아무도 모른다.
import type { TimeSeriesDataPoint } from "@/components/shared/Dashboard/types";

export interface NavPoint extends TimeSeriesDataPoint {
  nav: number | null;
  benchmark: number | null;
  daily_return: number | null;
  drawdown: number | null;
}

export interface NavHistoryOut {
  items: NavPoint[];
  total_count: number;
}
