"use client";

import { useCallback, useState, type ReactNode } from "react";
import { ProductPanel, ProductRail } from "@/components/shared/Layout";
import { useMenuAccessGate } from "@/hooks/shared/useMenuAccessGate";
import { usePanelOverlaysBoard } from "@/hooks/shared/usePanelOverlaysBoard";
import { RAIL_ITEMS } from "@/constants/shell";

const PANEL_REGION_ID = "product-panel";

/**
 * 제품 셸 — 46px 레일 + 보드 + 패널 (화면 결정 §20).
 *
 * 관리 셸(`app/admin/layout.tsx`)과 **갈라져 있다**. 예전에는 한 레이아웃이 제품·관리를 다
 * 덮으면서 제품 화면에도 MDI 탭 iframe 이 얹혔는데, 그러면 크롬이 두 겹이 된다(§20.3).
 * 여기에는 iframe 이 없다 — 제품 경로에서 `window.self === window.top` 이다.
 *
 * §20.2 「이동 규칙」 셋 중 **첫째가 여기**다: 레일 아이콘은 패널만 여닫고 **보드는 안 바뀐다**
 * (라우팅이 일어나지 않으므로 보드는 리마운트조차 되지 않는다). 나머지 둘(보드↔패널 양방향
 * 선택)은 `stores/shell/benchSelectionStore.ts` 가 소유한다.
 */
export default function ProductLayout({ children }: { children: ReactNode }) {
  const [openPanelId, setOpenPanelId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [focusRailItemId, setFocusRailItemId] = useState<string | null>(null);
  const { loaded, authorized } = useMenuAccessGate();
  // 폭·배분은 CSS 가 정한다. JS 가 아직 답해야 하는 것은 이 하나 — 덮는가(그래서 보드가 죽는가).
  const panelOverlaysBoard = usePanelOverlaysBoard();

  const togglePanel = useCallback((id: string) => {
    setOpenPanelId((current) => (current === id ? null : id));
    // 폭 토글은 패널마다 새로 정한다 — 에이전트를 620 으로 넓혀 두고 다른 패널을 열면
    // 그 패널까지 620 이 되는데, §21.3 이 620 을 준 것은 에이전트뿐이다.
    setExpanded(false);
  }, []);

  const closePanel = useCallback(() => {
    setOpenPanelId((current) => {
      // 닫고 나면 포커스를 연 자리(레일 버튼)로 돌려준다 — 안 돌려주면 사라진 요소에
      // 포커스가 남아 브라우저가 `<body>` 로 떨어뜨리고 키보드 위치를 잃는다.
      if (current) setFocusRailItemId(current);
      return null;
    });
    setExpanded(false);
  }, []);

  if (!loaded || authorized === null) return null;

  const openPanel = RAIL_ITEMS.find((item) => item.id === openPanelId) ?? null;
  const panelCoversBoard = openPanel !== null && panelOverlaysBoard;

  return (
    <div className="flex h-screen bg-slate-void text-ink-primary">
      <ProductRail
        openPanelId={openPanelId}
        onTogglePanel={togglePanel}
        panelRegionId={PANEL_REGION_ID}
        focusItemId={focusRailItemId}
        onFocusHandled={() => setFocusRailItemId(null)}
      />

      {/* 패널은 이 상자 안에서만 논다 — 덮을 때(§21.6)도 레일까지 덮지는 않는다 */}
      <div className="relative flex min-w-0 flex-1">
        <main className="min-w-0 flex-1 overflow-auto" inert={panelCoversBoard || undefined}>
          {authorized ? children : null}
        </main>

        {openPanel && (
          <ProductPanel
            id={PANEL_REGION_ID}
            item={openPanel}
            expanded={expanded}
            onToggleExpanded={() => setExpanded((v) => !v)}
            onClose={closePanel}
          />
        )}
      </div>
    </div>
  );
}
