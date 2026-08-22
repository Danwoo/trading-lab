"use client";

import { type ReactNode } from "react";
// 배럴(`@/components/shared/Layout`)로 들어오면 그 안의 모든 것이 딸려 온다 — 제품 셸은
// 모든 화면이 지나가는 자리라 그 비용이 전 화면에 실린다. 직접 경로로 집는다 (#341 ②와 같은 사유).
import { MenuUnreadableScreen } from "@/components/shared/Layout/MenuUnreadableScreen";
import { ProductPanel } from "@/components/shared/Layout/ProductPanel";
import { ProductRail } from "@/components/shared/Layout/ProductRail";
import { RAIL_PANEL_CONTENT } from "@/components/shared/Layout/railPanelContent";
import { useMenuAccessGate } from "@/hooks/shared/useMenuAccessGate";
import { usePanelOverlaysBoard } from "@/hooks/shared/usePanelOverlaysBoard";
import { useProductPanelStore } from "@/stores/shell/productPanelStore";
import { RAIL_ITEMS } from "@/constants/shell";
import { SETTINGS_PATH } from "@/constants/routes";

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
/**
 * DB 메뉴 행 없이도 열리는 셸 진입점 — **자기 자신만** 열린다(하위 경로는 안 열린다).
 *
 * `/settings` 가 여기 있는 이유: 이 화면은 **어느 키가 비어 있는지**를 보이는 자리라,
 * 설치 직후·메뉴가 아직 없는 상태에서 가장 필요하다. 메뉴 행에 매달면 그 행은 `seed.sql`
 * 에만 있고 재시드는 계정을 지우므로, **이미 설치한 사람에게는 영영 안 보인다**
 * (리드 결정 2026-08-19 — 키 화면은 메뉴 게이트 뒤에 두지 않는다).
 *
 * 키 **값**은 이 화면에 오지 않으므로 읽기 권한을 넓게 두어도 새는 것이 없다. 값을 넣는
 * 경로가 생기면 그때는 권한을 따로 판정한다.
 */
const SHELL_ENTRY_PATHS = [SETTINGS_PATH] as const;

/** 접두어로 여는 경로는 없다 — 하나라도 넣으면 그 아래 전부가 게이트 밖으로 나간다. */
const NO_PREFIX_ALLOWED: readonly string[] = [];

export default function ProductLayout({ children }: { children: ReactNode }) {
  const openPanelId = useProductPanelStore((s) => s.openPanelId);
  const expanded = useProductPanelStore((s) => s.expanded);
  const focusRailItemId = useProductPanelStore((s) => s.focusRailItemId);
  const togglePanel = useProductPanelStore((s) => s.toggle);
  const closePanel = useProductPanelStore((s) => s.close);
  const toggleExpanded = useProductPanelStore((s) => s.toggleExpanded);
  const clearFocusRequest = useProductPanelStore((s) => s.clearFocusRequest);
  const { loaded, authorized, denial } = useMenuAccessGate(NO_PREFIX_ALLOWED, SHELL_ENTRY_PATHS);
  // 폭·배분은 CSS 가 정한다. JS 가 아직 답해야 하는 것은 이 하나 — 덮는가(그래서 보드가 죽는가).
  const panelOverlaysBoard = usePanelOverlaysBoard();

  // **셸은 인가 응답을 기다리지 않는다.** 종전에는 이 자리에서 `return null` 이라 레일 46px
  // 까지 화면 전체가 백지였다 — `loaded` 를 켜는 것은 클라이언트 이펙트의 메뉴 조회 하나뿐이라
  // 그 왕복 내내 아무것도 안 보인다. 마일스톤 2 수용 첫 칸(기동→로그인→실험대가 열림)이 그
  // 백지를 지난다. 골조를 먼저 세우고, 판정이 필요한 것은 `<main>` 안쪽에서만 가른다.
  const settled = loaded && authorized !== null;

  const openPanel = RAIL_ITEMS.find((item) => item.id === openPanelId) ?? null;
  // 레지스트리에 없으면 `ProductPanel` 이 `item.pending` 을 대신 보여준다.
  const PanelContent = openPanel === null ? undefined : RAIL_PANEL_CONTENT[openPanel.id];
  const panelCoversBoard = openPanel !== null && panelOverlaysBoard;

  return (
    <div className="flex h-screen bg-bg-base text-ink">
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
          {/* 못 읽은 것은 셸 **안에서** 말한다 — 되돌리면 로그인 화면이 사유 없이 뜬다(#333). */}
          {denial === "unreadable" ? <MenuUnreadableScreen /> : settled && authorized ? children : null}
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
