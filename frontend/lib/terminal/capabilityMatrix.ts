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
    US: { available: false, reason: "미국 심층 호가는 확보된 소스가 없습니다", because: "no-source" },
  },
  financials: { KR: AVAILABLE, US: AVAILABLE },
  disclosure: { KR: AVAILABLE, US: AVAILABLE },
  news: { KR: AVAILABLE, US: AVAILABLE },
  flow: {
    KR: AVAILABLE,
    US: {
      available: false,
      reason: "미국에는 투자자별 수급 개념이 없습니다 — 기관 보유·공매도 잔고로 대체 예정",
      because: "no-source",
    },
  },
  peers: { KR: AVAILABLE, US: AVAILABLE },
  positions: { KR: AVAILABLE, US: AVAILABLE },
  botState: { KR: AVAILABLE, US: AVAILABLE },
  researchDocs: { KR: AVAILABLE, US: AVAILABLE },
  aiConsole: { KR: AVAILABLE, US: AVAILABLE },
};

const UNKNOWN_REGION_VERDICT: CapabilityVerdict = {
  available: false,
  reason: "시장 정보를 알 수 없는 종목입니다",
  because: "no-source",
};

/**
 * 시장을 **모르는데** 그 자리가 종목에 매여 있지도 않을 때의 판정 — 봇 상태처럼 종목이 아니라
 * 워크스페이스에 속한 패널이 여기 해당한다. 시장을 물어봤자 그 패널의 자료와 무관하다.
 *
 * 시장마다 답이 갈리는 capability 면 **모르는 채로 열어 주지 않는다**(fail-closed) — 어느 쪽인지
 * 알아야 답할 수 있는 물음이라 그렇다. 어느 시장이든 같은 답이면 시장은 애초에 변수가 아니다.
 *
 * 시장을 **아는** 경우는 이 함수를 타지 않는다 — 그때는 매트릭스 답이 그대로 유효하다.
 */
export function resolveCapabilityWithoutRegion(capability: PanelCapability): CapabilityVerdict {
  const row = CAPABILITY_MATRIX[capability];
  return row.KR.available && row.US.available ? AVAILABLE : UNKNOWN_REGION_VERDICT;
}

export function resolveCapability(capability: PanelCapability, ctx: CapabilityContext): CapabilityVerdict {
  if (ctx.region === "UNKNOWN") return UNKNOWN_REGION_VERDICT;
  return CAPABILITY_MATRIX[capability][ctx.region];
}
