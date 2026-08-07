"use client";

import { useRef, useState, type KeyboardEvent } from "react";
import { useTerminalSymbol } from "@/hooks/terminal/useTerminalContext";
import { setSymbol } from "@/stores/terminal/contextActions";
import type { SymbolRef } from "@/types/terminal/context";
import { HoldingTab } from "./HoldingTab";
import { ScreenerTab } from "./ScreenerTab";
import { WatchlistTab } from "./WatchlistTab";

type SidebarTabId = "watchlist" | "holding" | "screener";

const TABS: Array<{ id: SidebarTabId; label: string }> = [
  { id: "watchlist", label: "관심종목" },
  { id: "holding", label: "보유" },
  { id: "screener", label: "스크리너" },
];

/**
 * 종목 사이드바(#326, FR-006·FR-007) — 터미널 페이지 안에 산다(FE-AD-14). `setSymbol`
 * import 는 이 파일에서만 한다 — 탭·행 컴포넌트는 문맥을 읽지 않고 `onSelect` 콜백만 받는다
 * (anti-patterns 룰 14, 설계 §3.2 "문맥 쓰기가 허용된 3곳" 중 하나).
 */
export function SymbolSidebar() {
  const [activeTab, setActiveTab] = useState<SidebarTabId>("watchlist");
  const symbol = useTerminalSymbol();
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const handleSelect = (next: SymbolRef) => {
    setSymbol(next);
  };

  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const currentIndex = TABS.findIndex((tab) => tab.id === activeTab);
    const delta = event.key === "ArrowRight" ? 1 : -1;
    const nextIndex = (currentIndex + delta + TABS.length) % TABS.length;
    const nextTab = TABS[nextIndex];
    setActiveTab(nextTab.id);
    tabRefs.current[nextIndex]?.focus();
  };

  return (
    <aside className="flex h-full w-64 flex-shrink-0 flex-col border-r border-slate-line bg-slate-panel font-mono text-xs">
      <div role="tablist" aria-label="종목 목록" className="flex flex-shrink-0 border-b border-slate-line">
        {TABS.map((tab, index) => (
          <button
            key={tab.id}
            ref={(el) => {
              tabRefs.current[index] = el;
            }}
            type="button"
            role="tab"
            id={`sidebar-tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            aria-controls={`sidebar-tabpanel-${tab.id}`}
            tabIndex={activeTab === tab.id ? 0 : -1}
            onClick={() => setActiveTab(tab.id)}
            onKeyDown={handleTabKeyDown}
            className={
              activeTab === tab.id
                ? "flex-1 border-b-2 border-ink-primary px-2 py-1.5 text-ink-primary"
                : "flex-1 border-b-2 border-transparent px-2 py-1.5 text-ink-muted hover:text-ink-primary"
            }
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        id={`sidebar-tabpanel-${activeTab}`}
        aria-labelledby={`sidebar-tab-${activeTab}`}
        className="min-h-0 flex-1"
      >
        {activeTab === "watchlist" && <WatchlistTab activeTicker={symbol?.ticker} onSelect={handleSelect} />}
        {activeTab === "holding" && <HoldingTab activeTicker={symbol?.ticker} onSelect={handleSelect} />}
        {activeTab === "screener" && <ScreenerTab />}
      </div>
    </aside>
  );
}
