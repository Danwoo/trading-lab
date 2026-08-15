"use client";

import { useCallback, useState, type ReactNode } from "react";
import { ProductRail } from "@/components/shared/Layout";
import { Icon } from "@/components/shared/ui/primitives/icons";
import { useMenuAccessGate } from "@/hooks/shared/useMenuAccessGate";
import { PANEL_WIDTH_PX, RAIL_ITEMS } from "@/constants/shell";

const PANEL_REGION_ID = "product-panel";

/**
 * 제품 셸 — 46px 레일 + 본문 + 372px 패널 자리 (화면 결정 §20).
 *
 * 관리 셸(`app/admin/layout.tsx`)과 **갈라져 있다**. 예전에는 한 레이아웃이 제품·관리를 다
 * 덮으면서 제품 화면에도 MDI 탭 iframe 이 얹혔는데, 그러면 크롬이 두 겹이 된다(§20.3).
 * 여기에는 iframe 이 없다 — 제품 경로에서 `window.self === window.top` 이다.
 *
 * **S2 가 만드는 것은 자리와 토글까지다.** 패널이 열리고 닫히고 폭을 차지하는 것까지가
 * 여기이고, 패널 내용과 §20.2 의 이동 규칙 세 줄(보드↔패널 양방향 선택)은 S3 다.
 * 그래서 지금 패널 본문은 무엇이 올 자리인지만 적는다 — 비워 두면 고장으로 읽힌다(§21.4).
 */
export default function ProductLayout({ children }: { children: ReactNode }) {
  const [openPanelId, setOpenPanelId] = useState<string | null>(null);
  const { loaded, authorized } = useMenuAccessGate();

  const togglePanel = useCallback((id: string) => {
    setOpenPanelId((current) => (current === id ? null : id));
  }, []);

  const closePanel = useCallback(() => setOpenPanelId(null), []);

  if (!loaded || authorized === null) return null;

  const openPanel = RAIL_ITEMS.find((item) => item.id === openPanelId) ?? null;

  return (
    <div className="flex h-screen bg-slate-void text-ink-primary">
      <ProductRail openPanelId={openPanelId} onTogglePanel={togglePanel} panelRegionId={PANEL_REGION_ID} />

      <main className="min-w-0 flex-1 overflow-auto">{authorized ? children : null}</main>

      {/* 패널은 모달이 아니다 — 보드를 덮지 않고 옆으로 민다(§20.2). 그래서 flex 형제다. */}
      {openPanel && (
        <aside
          id={PANEL_REGION_ID}
          aria-label={openPanel.label}
          style={{ flex: `0 0 ${PANEL_WIDTH_PX}px` }}
          className="flex h-full flex-col border-l border-slate-line bg-slate-panel"
        >
          <div className="flex flex-none items-center gap-2 border-b border-slate-line px-3 py-2">
            <h2 className="min-w-0 flex-1 truncate text-sm font-medium text-ink-primary">{openPanel.label}</h2>
            <button
              type="button"
              aria-label={`${openPanel.label} 패널 닫기`}
              onClick={closePanel}
              className="rounded p-1 text-ink-muted hover:bg-slate-line hover:text-ink-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
            >
              <Icon name="close" size={14} />
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-auto p-3 text-sm text-ink-muted">{openPanel.pending}</div>
        </aside>
      )}
    </div>
  );
}
