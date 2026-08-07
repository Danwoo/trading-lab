import type { CandleInterval } from "@/types/terminal/context";
import type { Quote } from "@/lib/terminal/realtimeArbiter";
import { apiCall } from "@/utils/common/api/client";

// 프론트 프록시 경로(#146 컨벤션) → 백엔드 prefix "/bar" · "/quote" · "/market-capability"
const BAR_URL = "/api/external/backend/bar";
const QUOTE_URL = "/api/external/backend/quote";
const CAPABILITY_URL = "/api/external/backend/market-capability";

export interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/**
 * 캔들 응답. `unavailableReason` 이 빈 배열과 짝을 이룬다 — 0건이 "그 기간에 거래가 없었다"인지
 * "이 시장은 아직 채워지지 않았다"인지 화면이 구분할 수 있어야 한다(FR-021).
 */
export interface CandleSeries {
  items: Candle[];
  source: string;
  asOf: string | null;
  unavailableReason: string | null;
}

interface BarsOut {
  items: Array<Candle & { trade_value?: number | null }>;
  total_count: number;
  market: string;
  symbol: string;
  interval: string;
  source: string | null;
  adj_policy: string | null;
  asof: string | null;
  unavailable_reason: string | null;
}

/** 분 단위 주기 문자열 → 백엔드 `interval_min`. 월봉(`1M`)은 아직 계약이 없다. */
const MINUTES_BY_INTERVAL: Partial<Record<CandleInterval, number>> = {
  "1m": 1,
  "5m": 5,
  "15m": 15,
  "30m": 30,
  "60m": 60,
};

const MONTHLY_NOT_READY = "월봉은 아직 제공되지 않습니다 — 일봉·분봉만 적재 대상입니다";

function toSeries(result: BarsOut | null, fallbackReason: string): CandleSeries {
  if (result === null) {
    return { items: [], source: "적재본", asOf: null, unavailableReason: fallbackReason };
  }
  return {
    items: result.items.map(({ time, open, high, low, close, volume }) => ({
      time,
      open,
      high,
      low,
      close,
      volume,
    })),
    // 출처·수정주가 정책을 한 줄로 합쳐 보여준다 — 어느 소스의 어떤 정책인지가 화면에서
    // 사라지면 백테스트 재현성 논의가 근거를 잃는다(FR-019).
    source: result.source ? `${result.source}${result.adj_policy ? ` · ${result.adj_policy}` : ""}` : "적재본",
    asOf: result.asof,
    unavailableReason: result.unavailable_reason,
  };
}

/**
 * 갈래 1 — 적재본 캔들 조회. **provider 를 부르지 않는다**: 이 함수가 아는 것은 우리 백엔드
 * 경로뿐이고, 어느 소스에서 왔는지는 응답의 `source` 로만 안다(MD-AD-19).
 *
 * 시간축은 시장 시각 고정이다(2026-07-30 결정) — 백엔드가 문자열로 준 `time` 을 그대로 넘기고
 * 여기서 타임존 변환을 하지 않는다. 공용 `formatDate` 를 태우면 사용자 타임존이 섞인다.
 */
export async function selectCandles(params: {
  ticker: string;
  market: string;
  interval: CandleInterval;
  from: string;
  to: string;
}): Promise<CandleSeries> {
  if (params.interval === "1M") {
    return { items: [], source: "적재본", asOf: null, unavailableReason: MONTHLY_NOT_READY };
  }

  const intervalMin = MINUTES_BY_INTERVAL[params.interval];
  if (intervalMin === undefined) {
    const result = await apiCall<BarsOut>(`${BAR_URL}/daily`, {
      method: "GET",
      params: { market: params.market, symbol: params.ticker, date_from: params.from, date_to: params.to },
    });
    return toSeries(result, "일봉을 불러오지 못했습니다");
  }

  const result = await apiCall<BarsOut>(`${BAR_URL}/minute`, {
    method: "GET",
    params: {
      market: params.market,
      symbol: params.ticker,
      ts_from: `${params.from}T00:00:00`,
      ts_to: `${params.to}T23:59:59`,
      interval_min: intervalMin,
    },
  });
  return toSeries(result, "분봉을 불러오지 못했습니다");
}

interface QuotesOut {
  items: Array<{
    market: string;
    symbol: string;
    price: number;
    change: number;
    change_rate: number;
    volume: number;
    asof: string;
  }>;
  total_count: number;
  source: string | null;
  unavailable: Record<string, string>;
}

/**
 * 갈래 3 — 사이드바 일괄 조회 전용. `useQuoteBatch` 밖에서 부르지 않는다.
 *
 * **구독이 아니라 요청-응답이다**(MD-AD-19) — 이 모듈에 구독 API 가 없는 것이 계약이다.
 * `market` 을 함께 받는 이유: 같은 티커가 국내·미국에 동시에 존재할 수 있어 티커만으로는
 * 어느 시장을 물어야 할지 정해지지 않는다.
 */
export async function selectQuoteBatch(
  symbols: Array<{ ticker: string; market: string }>,
): Promise<{ items: Record<string, Quote>; source: string; asOf: string | null; unavailable: Record<string, string> }> {
  const result = await apiCall<QuotesOut>(`${QUOTE_URL}/batch`, {
    method: "POST",
    data: { symbols: symbols.map(({ ticker, market }) => ({ market, symbol: ticker })) },
  });
  if (result === null) {
    return { items: {}, source: "일괄 조회", asOf: null, unavailable: {} };
  }

  const items: Record<string, Quote> = {};
  for (const row of result.items) {
    items[row.symbol] = {
      price: row.price,
      change: row.change,
      changeRate: row.change_rate,
      volume: row.volume,
      at: row.asof,
    };
  }
  const asOf = result.items.length > 0 ? result.items[0].asof : null;
  return { items, source: result.source ?? "일괄 조회", asOf, unavailable: result.unavailable };
}

export interface MarketCapability {
  source: string;
  market: string;
  dataKind: string;
  available: boolean;
  reason: string | null;
}

interface CapabilitiesOut {
  items: Array<{ source: string; market: string; data_kind: string; available: boolean; reason: string | null }>;
  total_count: number;
}

/**
 * "이 시장의 이 데이터를 줄 수 있는 소스가 있는가"를 서버에 묻는다 (FR-013·FR-021).
 *
 * 프론트 정적 매트릭스(`lib/terminal/capabilityMatrix.ts`)로 흉내 낼 수 없는 축이 하나 있다 —
 * **키 유무는 런타임 상태라 서버만 안다.** 키를 넣었을 때 화면이 저절로 열리려면 이 조회가
 * 있어야 한다.
 */
export async function selectMarketCapabilities(market?: string): Promise<MarketCapability[]> {
  const result = await apiCall<CapabilitiesOut>(CAPABILITY_URL, {
    method: "GET",
    params: market ? { market } : undefined,
  });
  if (result === null) return [];
  return result.items.map((row) => ({
    source: row.source,
    market: row.market,
    dataKind: row.data_kind,
    available: row.available,
    reason: row.reason,
  }));
}
