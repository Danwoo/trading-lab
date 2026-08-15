"use client";

import { usePathname, useRouter } from "next/navigation";
import { showToast } from "@/components/shared/Feedback";
import { Icon } from "@/components/shared/ui/primitives/icons";
import { cn } from "@/components/shared/ui/primitives/cn";
import { RAIL_ITEMS, RAIL_WIDTH_PX, type RailItem } from "@/constants/shell";

interface Props {
  /** 지금 열려 있는 패널 항목 id. 닫혀 있으면 null */
  openPanelId: string | null;
  /** 패널 항목을 눌렀을 때 — 같은 id 를 다시 누르면 닫는다 */
  onTogglePanel: (id: string) => void;
  /** 패널이 그려지는 영역의 DOM id (`aria-controls`) */
  panelRegionId: string;
}

/**
 * 46px 아이콘 레일 — 제품 셸의 세로줄 하나 (화면 결정 §20).
 *
 * 항목은 두 갈래다(§20.2 이동 규칙): `route` 는 화면을 바꾸고, `panel` 은 보드를 그대로 둔 채
 * 옆 패널만 여닫는다. **화면이 아직 없는 항목도 지운 대신 남겨 둔다** — 지우면 「원래 없는 것」
 * 으로 읽히는데 실제로는 「아직 안 만든 것」이고, 둘은 다르다(§25.2 ①의 같은 논지).
 * 그래서 누르면 아무 일도 안 일어나는 대신 무엇이 없는지 토스트로 말한다.
 *
 * 접근성: 항목은 전부 실제 `<button>` 이라 Tab 으로 닿고 Enter/Space 로 동작한다.
 * 아이콘만 있으므로 각 버튼에 `aria-label` 로 이름을 준다. 패널 토글은 `aria-expanded` +
 * `aria-controls` 로 패널 영역을 가리키고, 화면 전환 항목은 현재 경로일 때 `aria-current="page"`
 * 를 단다. 아직 없는 자리는 `disabled` 대신 `aria-disabled` 다 — `disabled` 는 포커스를 못 받아
 * 「왜 안 되는지」에 키보드로 도달할 방법이 사라진다.
 */
export function ProductRail({ openPanelId, onTogglePanel, panelRegionId }: Props) {
  const router = useRouter();
  const pathname = usePathname();

  const isRouteActive = (item: RailItem) =>
    !!item.path && (pathname === item.path || pathname.startsWith(item.path + "/"));

  const handleClick = (item: RailItem) => {
    if (item.kind === "panel") {
      onTogglePanel(item.id);
      return;
    }
    if (!item.path) {
      showToast(item.pending, "info");
      return;
    }
    router.push(item.path);
  };

  const renderItem = (item: RailItem) => {
    const isPanel = item.kind === "panel";
    const isOpen = isPanel && openPanelId === item.id;
    const isActive = !isPanel && isRouteActive(item);
    const isPending = !isPanel && !item.path;

    return (
      <li key={item.id}>
        <button
          type="button"
          aria-label={item.label}
          title={item.pending ? `${item.label} — ${item.pending}` : item.label}
          aria-current={isActive ? "page" : undefined}
          aria-expanded={isPanel ? isOpen : undefined}
          aria-controls={isPanel ? panelRegionId : undefined}
          aria-disabled={isPending || undefined}
          onClick={() => handleClick(item)}
          className={cn(
            "flex h-[30px] w-[30px] items-center justify-center rounded-lg border border-transparent transition-colors",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted",
            isActive && "border-ink-primary/30 bg-slate-line text-ink-primary",
            isOpen && "border-slate-line bg-slate-line text-signal-warn",
            !isActive && !isOpen && "text-ink-muted hover:bg-slate-line hover:text-ink-primary",
            isPending && "opacity-60",
          )}
        >
          <Icon name={item.icon} size={18} />
        </button>
      </li>
    );
  };

  const mainItems = RAIL_ITEMS.filter((item) => !item.footer);
  const footerItems = RAIL_ITEMS.filter((item) => item.footer);

  const renderGroup = (items: readonly RailItem[]) => {
    const rendered: React.ReactNode[] = [];
    items.forEach((item) => {
      rendered.push(renderItem(item));
      if (item.dividerAfter) {
        rendered.push(
          <li key={`${item.id}-divider`} aria-hidden className="my-1 w-[22px] border-t border-slate-line" />,
        );
      }
    });
    return rendered;
  };

  return (
    <nav
      aria-label="제품 레일"
      style={{ flex: `0 0 ${RAIL_WIDTH_PX}px` }}
      className="flex h-full flex-col items-center gap-1 border-r border-slate-line bg-slate-panel py-2"
    >
      <ul className="flex flex-col items-center gap-1">{renderGroup(mainItems)}</ul>
      <ul className="mt-auto flex flex-col items-center gap-1">{renderGroup(footerItems)}</ul>
    </nav>
  );
}
