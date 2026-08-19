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

export type CapabilityVerdict =
  | { available: true }
  /** `because` 는 배지가 무엇이라 부를지를 정한다 — 뜻은 `Provenance` 의 같은 이름 필드와 같다. */
  | { available: false; reason: string; because?: "not-chosen" };

/** 배포 모드 축이 FR-044 때 여기 더해진다 */
export interface CapabilityContext {
  region: Region;
}
