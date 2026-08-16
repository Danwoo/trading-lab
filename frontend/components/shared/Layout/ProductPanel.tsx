"use client";

import { useEffect, useRef, type KeyboardEvent, type ReactNode } from "react";
import { Icon } from "@/components/shared/ui/primitives/icons";
import { cn } from "@/components/shared/ui/primitives/cn";
import { useBenchSelectionStore } from "@/stores/shell/benchSelectionStore";
import { type RailItem } from "@/constants/shell";

interface Props {
  item: RailItem;
  /** 에이전트 전용 620px 토글의 현재 상태 (§21.3) */
  expanded: boolean;
  onToggleExpanded: () => void;
  onClose: () => void;
  /** 레일 버튼의 `aria-controls` 가 가리키는 값과 같아야 한다 */
  id: string;
  children?: ReactNode;
}

/**
 * 폭 구간별 패널 폭 (§21.6) — **전부 CSS 다.**
 *
 * - 기본(1024 미만): `absolute inset-0` 로 보드를 **덮는다**. 자리를 차지하지 않고 위에 얹힌다
 * - `lg`(1024~1280): 형제로 돌아와 300
 * - `xl`(1280 이상): 372, 에이전트를 넓히면 620
 *
 * 두 `xl:w-*` 를 **삼항으로 갈라** 한쪽만 나오게 한다 — `cn` 은 단순 join 이라(tailwind-merge
 * 아님) 둘을 함께 실으면 어느 쪽이 이길지 생성된 CSS 의 순서가 정하고, 그건 클래스 문자열을
 * 읽어서는 알 수 없다.
 */
function panelWidthClass(expanded: boolean): string {
  return expanded ? "xl:w-shell-panel-expanded" : "xl:w-shell-panel";
}

/**
 * 레일이 여는 패널 — **모달이 아니다. 보드를 덮지 않고 옆으로 민다**(화면 결정 §20.2).
 *
 * 덮지 않는 것이 이 패널의 존재 이유다. 패널에서 본 것을 보드에 바로 적용하는 것이 제품의
 * 핵심이라, 덮으면 「보고 → 닫고 → 다시 찾고」가 된다. 그래서 `flex` 형제로 앉는다.
 *
 * **1024 미만에서만 덮는다**(§21.6) — 그 폭에서는 나란히 두면 둘 다 못 읽는다. 덮는 것도
 * 폭도 CSS 가 정하지만, 덮을 때 성격이 모달에 가까워지는 것까지는 못 한다 — 보드를 `inert`
 * 로 만드는 것은 호출자가 `usePanelOverlaysBoard()` 로 판단한다.
 *
 * 접근성: 열릴 때 패널로 포커스가 들어가고 `Escape` 로 닫히며 포커스는 레일 버튼으로 돌아간다
 * (`onClose` 를 부른 뒤의 포커스 복귀는 호출자 몫 — 레일 버튼을 쥐고 있는 쪽이 거기다).
 */
export function ProductPanel({ item, expanded, onToggleExpanded, onClose, id, children }: Props) {
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

  return (
    <aside
      ref={containerRef}
      id={id}
      tabIndex={-1}
      aria-labelledby={headingId}
      onKeyDown={handleKeyDown}
      className={cn(
        "flex h-full min-w-0 flex-col border-l border-slate-line bg-slate-panel focus:outline-none",
        "absolute inset-0 z-20 lg:static lg:w-shell-panel-compact lg:flex-none",
        panelWidthClass(expanded),
      )}
    >
      <div className="flex flex-none items-center gap-2 border-b border-slate-line px-3 py-2">
        <h2 id={headingId} className="min-w-0 flex-1 truncate text-sm font-medium text-ink-primary">
          {item.label}
        </h2>

        {/*
          620 토글은 1280 이상에만 낸다 — §21.6 이 620 을 허용한 것이 거기뿐이다. 그 아래에서
          `display:none` 이라 접근성 트리에서도 사라진다: 누를 수는 있는데 폭은 안 바뀌고
          `aria-pressed` 만 눌림으로 도는 거짓 상태가 생기지 않는다.
        */}
        {item.expandable && (
          <button
            type="button"
            aria-pressed={expanded}
            aria-label={expanded ? `${item.label} 패널 좁히기` : `${item.label} 패널 넓히기`}
            onClick={onToggleExpanded}
            className="hidden rounded p-1 text-ink-muted hover:bg-slate-line hover:text-ink-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted xl:block"
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
