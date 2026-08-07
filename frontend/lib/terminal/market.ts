import type { Region } from "@/types/terminal/context";

const REGION_BY_MARKET: Record<string, Region> = {
  KOSPI: "KR",
  KOSDAQ: "KR",
  NASDAQ: "US",
  NYSE: "US",
};

export function resolveRegion(market: string | undefined | null): Region {
  if (!market) return "UNKNOWN";
  return REGION_BY_MARKET[market.toUpperCase()] ?? "UNKNOWN";
}
