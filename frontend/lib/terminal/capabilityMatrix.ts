import type { CapabilityContext, CapabilityVerdict, PanelCapability } from "@/types/terminal/capability";

type RegionMatrix = { KR: CapabilityVerdict; US: CapabilityVerdict };

const AVAILABLE: CapabilityVerdict = { available: true };

/**
 * 시장 축이 아예 걸리지 않는 capability. 종목을 고르기 전(`region === "UNKNOWN"`)에도 열려야
 * 하므로 아래 UNKNOWN 판정보다 먼저 걸린다 — 적재 상태처럼 "무엇을 보고 있는가"와 무관하게
 * 성립하는 패널이 여기 속한다.
 */
const REGION_INDEPENDENT = "region-independent" as const;

type CapabilityAvailability = RegionMatrix | typeof REGION_INDEPENDENT;

/**
 * [트레이딩-터미널 §2] 패널 목록 표를 그대로 옮긴다. 배포 모드 축(FR-044)은 여기 없다 —
 * `CapabilityContext` 가 처음부터 객체라 나중에 필드를 더해도 이 매트릭스 형태는 그대로다.
 *
 * `Record<PanelCapability, …>` 라 capability 를 새로 만들면 컴파일러가 시장 축 분류를 강제한다 —
 * 시장별 표를 쓸지 `REGION_INDEPENDENT` 인지가 이 표 한 곳에서만 정해진다.
 */
const CAPABILITY_MATRIX: Record<PanelCapability, CapabilityAvailability> = {
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
  dataIngest: REGION_INDEPENDENT,
};

const UNKNOWN_REGION_VERDICT: CapabilityVerdict = { available: false, reason: "시장 정보를 알 수 없는 종목입니다" };

export function resolveCapability(capability: PanelCapability, ctx: CapabilityContext): CapabilityVerdict {
  const availability = CAPABILITY_MATRIX[capability];
  if (availability === REGION_INDEPENDENT) return AVAILABLE;
  if (ctx.region === "UNKNOWN") return UNKNOWN_REGION_VERDICT;
  return availability[ctx.region];
}

/**
 * 매트릭스에 실린 capability 전수. 타입 유니온은 런타임에 못 세므로 테스트가 이 표를 직접 훑도록
 * 내보낸다 — capability 를 새로 만들면 손으로 적은 테스트 목록에서 새는 것을 막는다.
 */
export function listCapabilities(): PanelCapability[] {
  return Object.keys(CAPABILITY_MATRIX) as PanelCapability[];
}

/** 시장 축이 걸리지 않는 capability 인가. 종목 미선택(`UNKNOWN`) 상태에서도 열린다. */
export function isRegionIndependent(capability: PanelCapability): boolean {
  return CAPABILITY_MATRIX[capability] === REGION_INDEPENDENT;
}
