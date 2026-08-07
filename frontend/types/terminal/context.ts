export type Region = "KR" | "US" | "UNKNOWN";

export type CandleInterval = "1m" | "5m" | "15m" | "30m" | "60m" | "1d" | "1M";

export interface SymbolRef {
  ticker: string;
  market: string;
  name?: string;
}

/** YYYY-MM-DD */
export interface DateRange {
  from: string;
  to: string;
}

export interface TerminalContext {
  symbol: SymbolRef | null;
  interval: CandleInterval;
  range: DateRange | null;
  selectedBotId: string | null;
}
