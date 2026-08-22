"use client";

import { useEffect, useState } from "react";
import { useQuoteBatch } from "@/hooks/terminal/useQuoteBatch";
import { selectHoldingList, selectPortfolioList } from "@/services/portfolio/portfolioService";
import type { HoldingOut } from "@/schemas/portfolio/portfolio";
import type { SymbolRef } from "@/types/terminal/context";
import { PanelSkeleton } from "./PanelSkeleton";
import { PanelUnavailable } from "./PanelUnavailable";
import { ProvenanceBadge } from "./ProvenanceBadge";
import { SidebarSymbolRow } from "./SidebarSymbolRow";

export interface HoldingTabProps {
  activeTicker: string | undefined;
  onSelect: (symbol: SymbolRef) => void;
}

/**
 * 같은 종목을 두 포트폴리오가 각각 보유하면(예: 삼성전자를 "core"·"growth" 둘 다 보유) 데이터로는
 * 정확한 두 행이지만, 이 사이드바의 목적은 "종목을 골라 문맥(전역 symbol)을 바꾸는" 것뿐이라 —
 * `SidebarSymbolRow` 는 포트폴리오별 수량을 보여주지 않는다 — 같은 티커가 두 번 뜨는 것은
 * 클릭 결과가 똑같은 항목의 중복일 뿐이다. 먼저 나온 포트폴리오의 보유를 대표로
 * 남긴다 — 어떤 포트폴리오인지가 아니라 "이 종목을 보유 중"이라는 사실이 이 목록의 단위다.
 */
function dedupeByTicker(holdings: HoldingOut[]): HoldingOut[] {
  const seen = new Set<string>();
  return holdings.filter((holding) => {
    if (seen.has(holding.ticker)) return false;
    seen.add(holding.ticker);
    return true;
  });
}

/**
 * 보유종목 탭(FR-006) — `tn_holding` 은 워크스페이스 안에서도 포트폴리오별로 나뉘어 있고
 * (PK: workspace·portfolio·ticker), 백엔드는 포트폴리오를 가로지르는 집계 엔드포인트를 두지
 * 않는다(`GET /portfolio/{id}/holding` 만 존재). 그래서 이 탭이 포트폴리오 목록을 먼저 받고
 * 각 포트폴리오의 보유를 병렬로 모아 합친다 — 서비스 함수 자체는 O5/보유 화면과 동일하게 쓴다.
 *
 * `Holding.market` 은 백엔드 마이그레이션(#328, 0010_holding_market)으로 생겼지만 기존 행은
 * 백필하지 않아 비어 있을 수 있다 — 있으면 그대로 쓰고, 없으면 빈 문자열을 넘긴다(`resolveRegion`
 * 이 UNKNOWN 으로 판정해 시장을 지어내지 않는다. `PanelSlot` 의 MARKET_MISSING_VERDICT 가
 * "시장 값이 비어 있다"고 있는 그대로 말한다 — "종목이 이상하다"로 오인시키지 않는다).
 *
 * `throwOnFailure: true` 로 호출해 서버 실패(`success:false`)를 `catch` 로 보낸다. 기본
 * (`apiCall`) 계약은 실패와 "정상 0건"을 둘 다 `null` 로 뭉개므로, 그것을 그대로 두면 사이드바가
 * 서버 오류를 "보유종목이 없습니다"로 말한다. 이 탭은 격자 커널(`useServerTable`)을 타지 않고
 * 직접 서비스 함수를 부르므로 호출부에서 갈라야 한다
 * ([#332](https://github.com/Danwoo/trading-lab/issues/332) 은 격자 경로 쪽을 닫았다).
 */
export function HoldingTab({ activeTicker, onSelect }: HoldingTabProps) {
  const [holdings, setHoldings] = useState<HoldingOut[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setHoldings(null);
    setFailed(false);

    async function load() {
      try {
        const portfolios = await selectPortfolioList({}, { throwOnFailure: true });
        const portfolioIds = portfolios?.items.map((portfolio) => portfolio.portfolio_id) ?? [];
        const holdingLists = await Promise.all(
          portfolioIds.map((portfolioId) => selectHoldingList({ portfolio_id: portfolioId }, { throwOnFailure: true })),
        );
        if (cancelled) return;
        setHoldings(dedupeByTicker(holdingLists.flatMap((result) => result?.items ?? [])));
      } catch {
        if (!cancelled) setFailed(true);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  // 시장을 모르는 행은 일괄 조회에서 뺀다 — 같은 티커가 국내·미국에 함께 있을 수 있어
  // 시장 없이는 어느 소스에 물어야 할지 정해지지 않는다. 뺀 행은 시세 칸이 비는데, 그 사유는
  // `resolveRegion`(UNKNOWN)이 이미 화면에 표시한다.
  const symbols =
    holdings?.flatMap((holding) => (holding.market ? [{ ticker: holding.ticker, market: holding.market }] : [])) ?? [];
  const { quotes, provenance } = useQuoteBatch(symbols);

  if (failed) {
    return <PanelUnavailable reason="보유종목을 불러오지 못했습니다 — 잠시 후 다시 시도하세요." />;
  }

  if (holdings === null) {
    return <PanelSkeleton />;
  }

  if (holdings.length === 0) {
    // 「포트폴리오 화면」이라고만 적으면 레일의 「포트폴리오」(아직 못 여는 자리)로 읽힌다 —
    // 보유를 실제로 등록하는 자리는 관리 화면의 포트폴리오 상세다. 관심종목 탭과 같은 규칙:
    // 「어디로 가라」를 적으면 그 자리로 가는 조작부를 함께 준다.
    return (
      <PanelUnavailable
        reason="보유종목이 없습니다 — 등록하면 여기에서 그 종목을 고를 수 있습니다."
        action={{ href: "/admin/portfolio", label: "보유종목 등록하러 가기" }}
      />
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-shrink-0 border-b border-line px-2 py-1">
        <ProvenanceBadge provenance={provenance} />
      </div>
      <ul className="min-h-0 flex-1 overflow-auto">
        {holdings.map((holding) => (
          <SidebarSymbolRow
            key={holding.ticker}
            symbol={{ ticker: holding.ticker, market: holding.market ?? "", name: holding.holding_nm }}
            isActive={holding.ticker === activeTicker}
            quote={quotes[holding.ticker]}
            onSelect={onSelect}
          />
        ))}
      </ul>
    </div>
  );
}
