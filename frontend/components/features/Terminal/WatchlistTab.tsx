"use client";

import { useServerTable } from "@/hooks/shared/useServerTable";
import { useQuoteBatch } from "@/hooks/terminal/useQuoteBatch";
import { selectWatchlistList } from "@/services/watchlist/watchlistService";
import type { WatchlistOut } from "@/schemas/watchlist/watchlist";
import type { SymbolRef } from "@/types/terminal/context";
import { PanelSkeleton } from "./PanelSkeleton";
import { PanelUnavailable } from "./PanelUnavailable";
import { ProvenanceBadge } from "./ProvenanceBadge";
import { SidebarSymbolRow } from "./SidebarSymbolRow";

export interface WatchlistTabProps {
  activeTicker: string | undefined;
  onSelect: (symbol: SymbolRef) => void;
}

// 사이드바는 페이저를 두지 않는다 — 관심종목 전체를 한 화면에서 훑는 목록이라 그리드 페이지
// 사이즈(`PAGE_SIZE.MASTER` 20)보다 넉넉히 잡는다. 그래도 상한은 상한이다 — 201번째부터는
// 화면에 안 보인다. `table.totalCount`(절단 전 전체 건수, `applyClientQuery` 가 슬라이스 전
// 길이로 반환)와 `table.rows.length`(실제 표시 건수)를 비교해 절단됐으면 그 사실을 표시한다
// (#326 교차 리뷰 지적 — 조용한 절단 금지).
const SIDEBAR_LIST_PAGE_SIZE = 200;

/**
 * 관심종목 탭(FR-006) — `selectWatchlistList`(O5) 실데이터. 다종목 시세는 `useQuoteBatch`
 * (FR-048) 하나로만 조회한다.
 */
export function WatchlistTab({ activeTicker, onSelect }: WatchlistTabProps) {
  const table = useServerTable<WatchlistOut>({
    fetchGrid: selectWatchlistList,
    clientSide: true,
    pageSize: SIDEBAR_LIST_PAGE_SIZE,
  });
  // 시장을 모르는 행은 일괄 조회에서 뺀다 — 같은 티커가 국내·미국에 함께 있을 수 있어
  // 시장 없이는 어느 소스에 물어야 할지 정해지지 않는다. 뺀 행은 시세 칸이 비는데, 그 사유는
  // `resolveRegion`(UNKNOWN)이 이미 화면에 표시한다.
  const symbols = table.rows.flatMap((row) => (row.market ? [{ ticker: row.ticker, market: row.market }] : []));
  const { quotes, provenance } = useQuoteBatch(symbols);

  // 못 읽은 것을 「없다」고 하면 등록해 둔 종목 위에 다시 등록하러 가게 만든다 —
  // 실패를 먼저 가른다(같은 폴더 `HoldingTab` 과 같은 순서·같은 어휘).
  if (table.error) {
    return <PanelUnavailable reason="관심종목을 불러오지 못했습니다 — 잠시 후 다시 시도하세요." />;
  }

  if (table.isLoading) {
    return <PanelSkeleton />;
  }

  if (table.rows.length === 0) {
    return (
      <PanelUnavailable
        reason="관심종목이 없습니다 — 여기에 종목을 등록하면 차트·호가가 그 종목으로 채워집니다."
        action={{ href: "/admin/watchlist", label: "관심종목 등록하러 가기" }}
      />
    );
  }

  const isTruncated = table.totalCount > table.rows.length;

  return (
    <div className="flex h-full flex-col">
      {/* 이 배지는 **시세 칸**의 출처다 — 목록 자체는 우리 DB 에서 온 실물이다. 라벨 없이 두면
          「제공 안 됨」이 패널 전체를 가리키는 말로 읽힌다(종목이 버젓이 보이는데도). */}
      <div className="flex flex-shrink-0 items-center gap-1.5 border-b border-line px-2 py-1">
        <span className="text-ink-muted">시세</span>
        <ProvenanceBadge provenance={provenance} />
      </div>
      <ul className="min-h-0 flex-1 overflow-auto">
        {table.rows.map((row) => (
          <SidebarSymbolRow
            key={row.ticker}
            symbol={{ ticker: row.ticker, market: row.market ?? "", name: row.issuer_nm }}
            isActive={row.ticker === activeTicker}
            quote={quotes[row.ticker]}
            onSelect={onSelect}
          />
        ))}
      </ul>
      {isTruncated && (
        <div role="status" className="flex-shrink-0 border-t border-line px-2 py-1 text-ink-muted">
          {table.totalCount}건 중 {table.rows.length}건 표시
        </div>
      )}
    </div>
  );
}
