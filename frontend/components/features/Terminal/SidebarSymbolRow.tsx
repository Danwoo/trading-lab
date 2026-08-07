import { formatNumber } from "@/utils/common/formatters/number";
import type { Quote } from "@/lib/terminal/realtimeArbiter";
import type { SymbolRef } from "@/types/terminal/context";

export interface SidebarSymbolRowProps {
  symbol: SymbolRef;
  isActive: boolean;
  quote: Quote | undefined;
  onSelect: (symbol: SymbolRef) => void;
}

/**
 * 사이드바 목록 한 행 — 순수 표시 컴포넌트다. `contextActions` 를 import 하지 않는다
 * (룰 14) — 클릭은 `onSelect` 콜백으로 위에(`SymbolSidebar`) 위임한다.
 */
export function SidebarSymbolRow({ symbol, isActive, quote, onSelect }: SidebarSymbolRowProps) {
  const isUp = quote !== undefined && quote.change >= 0;

  return (
    <li>
      <button
        type="button"
        aria-pressed={isActive}
        onClick={() => onSelect(symbol)}
        className={
          isActive
            ? "flex w-full items-center justify-between gap-2 border-l-2 border-ink-primary bg-slate-line px-2 py-1.5 text-left"
            : "flex w-full items-center justify-between gap-2 border-l-2 border-transparent px-2 py-1.5 text-left hover:bg-slate-line"
        }
      >
        <span className="min-w-0 flex-1">
          <span className="block truncate text-ink-primary">{symbol.name ?? symbol.ticker}</span>
          <span className="block text-ink-muted">{symbol.ticker}</span>
        </span>
        {quote && (
          <span className={`flex-shrink-0 text-right ${isUp ? "text-market-up" : "text-market-down"}`}>
            <span className="block">{formatNumber(quote.price, "number")}</span>
            {/* 색만으로 방향을 표시하지 않는다 — 부호(▲/▼)를 항상 함께 그린다 (#242 O3 착수 코멘트). */}
            <span className="block">
              {isUp ? "▲" : "▼"} {formatNumber(Math.abs(quote.changeRate), "decimal", { decimals: 2 })}%
            </span>
          </span>
        )}
      </button>
    </li>
  );
}
