"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { RAIL_ITEMS, RAIL_FOOTER_ITEMS, RAIL_WIDTH_PX, type RailItem } from "@/constants/shell";
import { matchesPath } from "@/lib/shell/nav";
import { Icon } from "@/components/shared/ui/primitives/icons";
import { cn } from "@/components/shared/ui/primitives/cn";

interface Props {
  /** 지금 열려 있는 패널의 `RailItem.id`. 없으면 `null`. */
  openPanelId: string | null;
  /** 패널 항목을 눌렀을 때. 같은 id 를 다시 누르면 닫는 것은 호출자가 정한다. */
  onTogglePanel: (id: string) => void;
  /** 패널 자리 엘리먼트의 id — `aria-controls` 로 잇는다. */
  panelRegionId: string;
}

/**
 * 제품 셸의 46px 아이콘 레일 (화면 설계 §20.2).
 *
 * 항목은 세 갈래다 — **목적지**는 전체 폭 화면으로 이동하고, **패널**은 옆의 372px 자리를
 * 열고 닫으며(보드는 안 바뀐다), **준비 중**은 확정된 순서에 자리만 잡고 있다. 준비 중 항목을
 * 숨기지 않는 이유는 §20.2 가 정한 순서가 화면에서 사라지지 않게 하기 위해서다.
 *
 * 접근성: 폭이 46px 라 글자를 못 싣는다 — 접근명은 `aria-label` 이 지고 마우스에는 `title` 이
 * 뜬다. 목적지는 `<Link>`(Enter), 패널·준비 중은 `<button>`(Enter·Space)이라 키보드로 전부
 * 닿는다. 열린 패널은 `aria-pressed` 와 `aria-controls` 로 자리와 이어진다. 준비 중은
 * `disabled` 가 아니라 `aria-disabled` 다 — `disabled` 는 포커스에서 빠져 스크린리더 사용자에게
 * 그 자리가 통째로 안 보인다.
 */
export function AppRail({ openPanelId, onTogglePanel, panelRegionId }: Props) {
  const pathname = usePathname();

  const renderItem = (item: RailItem) => {
    const iconClass = "flex-none";

    if (item.kind === "destination") {
      const isActive = matchesPath(pathname, item.path);
      return (
        <Link
          key={item.id}
          href={item.path}
          aria-label={item.label}
          aria-current={isActive ? "page" : undefined}
          title={item.label}
          className={cn(
            "flex h-[38px] w-[38px] items-center justify-center rounded",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-primary/40",
            isActive
              ? "bg-slate-line text-ink-primary"
              : "text-ink-muted hover:bg-slate-line/60 hover:text-ink-primary",
          )}
        >
          <Icon name={item.icon} size={20} className={iconClass} />
        </Link>
      );
    }

    if (item.kind === "panel") {
      const isOpen = openPanelId === item.id;
      return (
        <button
          key={item.id}
          type="button"
          aria-label={item.label}
          aria-pressed={isOpen}
          aria-controls={panelRegionId}
          title={item.label}
          onClick={() => onTogglePanel(item.id)}
          className={cn(
            "flex h-[38px] w-[38px] items-center justify-center rounded",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-primary/40",
            isOpen ? "bg-slate-line text-ink-primary" : "text-ink-muted hover:bg-slate-line/60 hover:text-ink-primary",
          )}
        >
          <Icon name={item.icon} size={20} className={iconClass} />
        </button>
      );
    }

    return (
      <button
        key={item.id}
        type="button"
        aria-label={`${item.label} — ${item.note}`}
        aria-disabled
        title={`${item.label} — ${item.note}`}
        // aria-disabled 는 눌림을 막지 않는다 — 실제 무동작은 여기서 만든다.
        onClick={(event) => event.preventDefault()}
        className={cn(
          "flex h-[38px] w-[38px] cursor-default items-center justify-center rounded text-ink-muted/50",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-primary/40",
        )}
      >
        <Icon name={item.icon} size={20} className={iconClass} />
      </button>
    );
  };

  return (
    <nav
      aria-label="주요 화면"
      style={{ width: RAIL_WIDTH_PX }}
      className="flex h-full flex-none flex-col items-center gap-1 border-r border-slate-line bg-slate-panel py-2"
    >
      {RAIL_ITEMS.map((item, index) =>
        item === null ? (
          <hr key={`divider-${index}`} aria-hidden className="my-1 w-[26px] border-t border-slate-line" />
        ) : (
          renderItem(item)
        ),
      )}
      <div className="mt-auto flex flex-col items-center gap-1">{RAIL_FOOTER_ITEMS.map(renderItem)}</div>
    </nav>
  );
}
