import type { CapabilityContext, CapabilityVerdict, PanelCapability } from "@/types/terminal/capability";

type RegionMatrix = { KR: CapabilityVerdict; US: CapabilityVerdict };

const AVAILABLE: CapabilityVerdict = { available: true };

/**
 * [트레이딩-터미널 §2] 패널 목록 표를 그대로 옮긴다. 배포 모드 축(FR-044)은 여기 없다 —
 * `CapabilityContext` 가 처음부터 객체라 나중에 필드를 더해도 이 매트릭스 형태는 그대로다.
 */
const CAPABILITY_MATRIX: Record<PanelCapability, RegionMatrix> = {
  candles: { KR: AVAILABLE, US: AVAILABLE },
  quote: { KR: AVAILABLE, US: AVAILABLE },
  orderbook: {
    KR: AVAILABLE,
    US: { available: false, reason: "미국 심층 호가는 확보된 소스가 없습니다" },
  },
  financials: { KR: AVAILABLE, US: AVAILABLE },
  disclosure: { KR: AVAILABLE, US: AVAILABLE },
  news: { KR: AVAILABLE, US: AVAILABLE },
  flow: {
    KR: AVAILABLE,
    US: { available: false, reason: "미국에는 투자자별 수급 개념이 없습니다 — 기관 보유·공매도 잔고로 대체 예정" },
  },
  peers: { KR: AVAILABLE, US: AVAILABLE },
  positions: { KR: AVAILABLE, US: AVAILABLE },
  botState: { KR: AVAILABLE, US: AVAILABLE },
  researchDocs: { KR: AVAILABLE, US: AVAILABLE },
  aiConsole: { KR: AVAILABLE, US: AVAILABLE },
};

const UNKNOWN_REGION_VERDICT: CapabilityVerdict = { available: false, reason: "시장 정보를 알 수 없는 종목입니다" };

export function resolveCapability(capability: PanelCapability, ctx: CapabilityContext): CapabilityVerdict {
  if (ctx.region === "UNKNOWN") return UNKNOWN_REGION_VERDICT;
  return CAPABILITY_MATRIX[capability][ctx.region];
}
