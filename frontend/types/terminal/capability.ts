import type { Region } from "./context";

export type PanelCapability =
  | "candles"
  | "quote"
  | "orderbook"
  | "financials"
  | "disclosure"
  | "news"
  | "flow"
  | "peers"
  | "positions"
  | "botState"
  | "researchDocs"
  | "aiConsole";

export type CapabilityVerdict = { available: true } | { available: false; reason: string };

/** 배포 모드 축이 FR-044 때 여기 더해진다 */
export interface CapabilityContext {
  region: Region;
}
