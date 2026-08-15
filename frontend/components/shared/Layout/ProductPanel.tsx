"use client";

import { useEffect, useRef, type KeyboardEvent, type ReactNode } from "react";
import { Icon } from "@/components/shared/ui/primitives/icons";
import { cn } from "@/components/shared/ui/primitives/cn";
import { useBenchSelectionStore } from "@/stores/shell/benchSelectionStore";
import { PANEL_COMPACT_WIDTH_PX, PANEL_EXPANDED_WIDTH_PX, PANEL_WIDTH_PX, type RailItem } from "@/constants/shell";
import type { ViewportBand } from "@/hooks/shared/useViewportBand";

interface Props {
  item: RailItem;
  band: ViewportBand;
  /** 에이전트 전용 620px 토글의 현재 상태 (§21.3) */
  expanded: boolean;
  onToggleExpanded: () => void;
  onClose: () => void;
  /** 레일 버튼의 `aria-controls` 가 가리키는 값과 같아야 한다 */
  id: string;
  children?: ReactNode;
}

/**
 * 폭 구간별 패널 폭 (§21.6). `overlay` 는 폭을 주지 않는다 — 보드를 **덮으므로** 자리를
 * 차지하는 것이 아니라 위에 얹힌다.
 */
function panelWidthPx(band: ViewportBand, expanded: boolean): number | null {
  if (band === "overlay") return null;
  if (band === "compact") return PANEL_COMPACT_WIDTH_PX;
  return expanded ? PANEL_EXPANDED_WIDTH_PX : PANEL_WIDTH_PX;
}

/**
 * 620px 토글이 있는 구간 — §21.6 이 620 을 허용한 것은 **1280 이상뿐**이다.
 * 그 아래에서는 `panelWidthPx` 가 `expanded` 를 무시하므로, 버튼을 보이면 누를 수는 있는데
 * 아무 일도 안 일어나고 `aria-pressed` 만 눌림으로 바뀐다 — 스크린리더에게 거짓말이 된다.
 */
function canExpand(item: RailItem, band: ViewportBand): boolean {
  return item.expandable === true && band === "wide";
}

/**
 * 레일이 여는 372px 패널 — **모달이 아니다. 보드를 덮지 않고 옆으로 민다**(화면 결정 §20.2).
 *
 * 덮지 않는 것이 이 패널의 존재 이유다. 패널에서 본 것을 보드에 바로 적용하는 것이 제품의
 * 핵심이라, 덮으면 「보고 → 닫고 → 다시 찾고」가 된다. 그래서 `flex` 형제로 앉는다.
 *
 * **1024 미만에서만 덮는다**(§21.6) — 그 폭에서는 나란히 두면 둘 다 못 읽는다. 덮을 때는
 * 성격이 모달에 가까워지므로 호출자가 보드를 `inert` 로 만든다.
 *
 * 접근성: 열릴 때 패널로 포커스가 들어가고 `Escape` 로 닫히며 포커스는 레일 버튼으로 돌아간다
 * (`onClose` 를 부른 뒤의 포커스 복귀는 호출자 몫 — 레일 버튼을 쥐고 있는 쪽이 거기다).
 */
export function ProductPanel({ item, band, expanded, onToggleExpanded, onClose, id, children }: Props) {
  const containerRef = useRef<HTMLElement>(null);
  const headingId = `${id}-heading`;
  const selection = useBenchSelectionStore((s) => s.selection);
  const clearSelection = useBenchSelectionStore((s) => s.clear);

  // 열릴 때 패널로 포커스를 옮긴다 — 레일에서 연 사람은 그것을 쓰려고 연 것이고, 안 옮기면
  // 레일 버튼 대여섯 개를 Tab 으로 지나야 패널에 닿는다.
  useEffect(() => {
    containerRef.current?.focus();
  }, [item.id]);

  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key !== "Escape") return;
    event.preventDefault();
    onClose();
  };

  const width = panelWidthPx(band, expanded);

  return (
    <aside
      ref={containerRef}
      id={id}
      tabIndex={-1}
      aria-labelledby={headingId}
      onKeyDown={handleKeyDown}
      style={width === null ? undefined : { flex: `0 0 ${width}px` }}
      className={cn(
        "flex h-full flex-col border-l border-slate-line bg-slate-panel focus:outline-none",
        band === "overlay" && "absolute inset-0 z-20",
      )}
    >
      <div className="flex flex-none items-center gap-2 border-b border-slate-line px-3 py-2">
        <h2 id={headingId} className="min-w-0 flex-1 truncate text-sm font-medium text-ink-primary">
          {item.label}
        </h2>

        {canExpand(item, band) && (
          <button
            type="button"
            aria-pressed={expanded}
            aria-label={expanded ? `${item.label} 패널 좁히기` : `${item.label} 패널 넓히기`}
            onClick={onToggleExpanded}
            className="rounded p-1 text-ink-muted hover:bg-slate-line hover:text-ink-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
          >
            <Icon name={expanded ? "arrowright" : "arrowleft"} size={14} />
          </button>
        )}

        <button
          type="button"
          aria-label={`${item.label} 패널 닫기`}
          onClick={onClose}
          className="rounded p-1 text-ink-muted hover:bg-slate-line hover:text-ink-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
        >
          <Icon name="close" size={14} />
        </button>
      </div>

      {/* §20.2 「보드에서 고르기 = 열린 패널의 내용이 그 선택으로 좁혀짐」 */}
      {selection && (
        <div className="flex flex-none items-center gap-2 border-b border-slate-line px-3 py-1.5 text-xs text-ink-muted">
          <span className="min-w-0 flex-1 truncate">
            {selection.origin === "board" ? "보드에서 고른 " : "여기서 고른 "}
            <span className="text-ink-primary">{selection.label}</span>
            {selection.origin === "board" ? " 로 좁혀져 있습니다" : " 을 보드가 표시하고 있습니다"}
          </span>
          <button
            type="button"
            onClick={clearSelection}
            className="flex-none rounded px-1 underline hover:text-ink-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
          >
            전체 보기
          </button>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-auto p-3 text-sm text-ink-muted">{children ?? item.pending}</div>
    </aside>
  );
}
