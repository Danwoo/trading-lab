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
    // 좁은 폭에서는 화면 폭을 다 쓰고 패널 열 **위**에 눕는다(#425) — `w-64` 를 가로로 두면
    // 390 폭에서 차트가 설 자리가 88px 밖에 안 남는다. 누운 높이는 서 있을 때 쓰던 폭과 같은
    // 값을 준다: 목록은 그 안에서 스크롤하고 아래 패널이 밀려나지 않는다.
    <aside className="flex h-64 w-full flex-shrink-0 flex-col border-b border-line bg-bg-panel font-mono text-xs lg:h-full lg:w-64 lg:border-b-0 lg:border-r">
      <div role="tablist" aria-label="종목 목록" className="flex flex-shrink-0 border-b border-line">
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
                ? "flex-1 border-b-2 border-ink-strong px-2 py-1.5 text-ink"
                : "flex-1 border-b-2 border-transparent px-2 py-1.5 text-ink-muted hover:text-ink"
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
