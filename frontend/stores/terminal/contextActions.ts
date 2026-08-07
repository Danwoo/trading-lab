"use client";

import type { CandleInterval, DateRange, SymbolRef } from "@/types/terminal/context";
import { useContextStore } from "./contextStore";

/**
 * 쓰기 액션 — 종목 사이드바 · 차트 컨트롤 · AI 콘솔만 import 한다 (설계 §3.2).
 * 패널은 문맥을 props 로 받거나 이 모듈을 통해 바꾸지 않는다(FE-AD-9).
 */

export function setSymbol(symbol: SymbolRef | null): void {
  useContextStore.setState({ symbol });
}

export function setInterval(interval: CandleInterval): void {
  useContextStore.setState({ interval });
}

export function setRange(range: DateRange | null): void {
  useContextStore.setState({ range });
}

export function setSelectedBot(botId: string | null): void {
  useContextStore.setState({ selectedBotId: botId });
}

/** O4 의 구독 중재자가 쓴다 — 종목이 실제로 바뀐 전이에서만 알린다. */
export function subscribeSymbolChange(listener: (symbol: SymbolRef | null) => void): () => void {
  return useContextStore.subscribe((state, prevState) => {
    if (state.symbol !== prevState.symbol) {
      listener(state.symbol);
    }
  });
}
