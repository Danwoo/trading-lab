"use client";

import { useOnDemand } from "@/hooks/terminal/useOnDemand";
import { selectMarketCapabilities, type MarketCapability } from "@/services/terminal/marketService";
import type { PanelData } from "@/types/terminal/provenance";

/**
 * 소스별 가용 여부 — 요청형 갈래(③). **키 유무는 런타임 상태라 서버만 안다**(설계 §7.4): 키가
 * 비어 있으면 서버가 `.env` 항목명과 발급 경로를 사유로 내려 주고, 화면은 그 문자열을 그대로
 * 보여준다. 프론트가 "키를 넣으세요" 같은 문구를 따로 만들면 서버가 아는 항목명과 갈린다.
 */
export function useMarketCapabilities(enabled: boolean): PanelData<MarketCapability[]> {
  return useOnDemand<MarketCapability[]>({
    group: "market-capability",
    enabled,
    source: "소스 가용성",
    fetcher: async () => ({ items: await selectMarketCapabilities(), asOf: null }),
  });
}
