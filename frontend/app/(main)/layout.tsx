"use client";

import { type ReactNode } from "react";
import { ProductPanel, ProductRail } from "@/components/shared/Layout";
import { RAIL_PANEL_CONTENT } from "@/components/shared/Layout/railPanelContent";
import { useMenuAccessGate } from "@/hooks/shared/useMenuAccessGate";
import { usePanelOverlaysBoard } from "@/hooks/shared/usePanelOverlaysBoard";
import { useProductPanelStore } from "@/stores/shell/productPanelStore";
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
 *
 * 무엇이 열려 있나는 `stores/shell/productPanelStore.ts` 가 갖는다 — 보드의 빈 상태가 주는
 * 길(§21.4)도 패널을 열어야 해서, 셸의 지역 상태로 두면 보드에서 닿을 수 없다.
 */
export default function ProductLayout({ children }: { children: ReactNode }) {
  const openPanelId = useProductPanelStore((s) => s.openPanelId);
  const expanded = useProductPanelStore((s) => s.expanded);
  const focusRailItemId = useProductPanelStore((s) => s.focusRailItemId);
  const togglePanel = useProductPanelStore((s) => s.toggle);
  const closePanel = useProductPanelStore((s) => s.close);
  const toggleExpanded = useProductPanelStore((s) => s.toggleExpanded);
  const clearFocusRequest = useProductPanelStore((s) => s.clearFocusRequest);
  const { loaded, authorized } = useMenuAccessGate();
  // 폭·배분은 CSS 가 정한다. JS 가 아직 답해야 하는 것은 이 하나 — 덮는가(그래서 보드가 죽는가).
  const panelOverlaysBoard = usePanelOverlaysBoard();

  if (!loaded || authorized === null) return null;

  const openPanel = RAIL_ITEMS.find((item) => item.id === openPanelId) ?? null;
  // 레지스트리에 없으면 `ProductPanel` 이 `item.pending` 을 대신 보여준다.
  const PanelContent = openPanel === null ? undefined : RAIL_PANEL_CONTENT[openPanel.id];
  const panelCoversBoard = openPanel !== null && panelOverlaysBoard;

  return (
    <div className="flex h-screen bg-slate-void text-ink-primary">
      <ProductRail
        openPanelId={openPanelId}
        onTogglePanel={togglePanel}
        panelRegionId={PANEL_REGION_ID}
        focusItemId={focusRailItemId}
        onFocusHandled={clearFocusRequest}
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
            onToggleExpanded={toggleExpanded}
            onClose={closePanel}
          >
            {PanelContent ? <PanelContent /> : undefined}
          </ProductPanel>
        )}
      </div>
    </div>
  );
}
