"use client";

import { resolveRegion } from "@/lib/terminal/market";
import { useContextStore } from "@/stores/terminal/contextStore";
import type { CandleInterval, DateRange, Region, SymbolRef, TerminalContext } from "@/types/terminal/context";

/** 셀렉터 기반 읽기 전용 훅 — 누구나 import 해도 된다(설계 §3.2). */
export function useTerminalContext<T>(selector: (ctx: TerminalContext) => T): T {
  return useContextStore(selector);
}

export function useTerminalSymbol(): SymbolRef | null {
  return useTerminalContext((ctx) => ctx.symbol);
}

export function useTerminalInterval(): CandleInterval {
  return useTerminalContext((ctx) => ctx.interval);
}

export function useTerminalRange(): DateRange | null {
  return useTerminalContext((ctx) => ctx.range);
}

export function useTerminalRegion(): Region {
  const market = useTerminalContext((ctx) => ctx.symbol?.market);
  return resolveRegion(market);
}
