import type { PanelDefinition } from "@/types/terminal/panel";

/**
 * 패널 레지스트리(#242 O6) — 지금 4종. 나머지(news·positions·peers·flow·research·ai-console)는
 * 후속 오더가 채운다. `load` 는 동적 import 다 — SSR 에서 `document`
 * 를 만지는 캔버스 차트 라이브러리(`candleChart.ts` 가 감싼다)를 쓰는 패널도 이 경계 덕에
 * 안전하다(O6 위험 표).
 *
 * 레지스트리에 없는 타입은 렌더하지 않되 **저장본에서는 지우지 않는다**(FE-AD-8·
 * `pruneUnknownPanels` 의 `preserved`) — O3 랜딩 당시 이 주석이 반대로 적혀 있었다(#242 O3
 * 마감 코멘트, "저장본은 지키지 않는다"는 오기).
 */
export const PANEL_REGISTRY: Record<string, PanelDefinition> = {
  chart: {
    type: "chart",
    title: "차트",
    capability: "candles",
    needsSymbol: true,
    load: () => import("@/components/features/ChartPanel/ChartPanel"),
  },
  "symbol-info": {
    type: "symbol-info",
    title: "종목 정보",
    capability: "quote",
    needsSymbol: true,
    load: () => import("@/components/features/SymbolInfoPanel/SymbolInfoPanel"),
  },
  orderbook: {
    type: "orderbook",
    title: "호가",
    capability: "orderbook",
    needsSymbol: true,
    load: () => import("@/components/features/OrderbookPanel/OrderbookPanel"),
  },
  // 문맥 종목과 무관한 패널 — 봇은 종목이 아니라 워크스페이스에 속한다.
  "bot-state": {
    type: "bot-state",
    title: "봇 상태",
    capability: "botState",
    needsSymbol: false,
    load: () => import("@/components/features/BotStatePanel/BotStatePanel"),
  },
};

export function getPanelDefinition(type: string): PanelDefinition | undefined {
  return PANEL_REGISTRY[type];
}

export function listPanelDefinitions(): PanelDefinition[] {
  return Object.values(PANEL_REGISTRY);
}
