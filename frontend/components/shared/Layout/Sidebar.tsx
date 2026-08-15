"use client";

import { useRouter, usePathname } from "next/navigation";
import { ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { useTabStore } from "@/stores/shared/tabStore";
import type { NavItem } from "@/lib/shell/nav";
import { Icon } from "@/components/shared/ui/primitives/icons";
import { cn } from "@/components/shared/ui/primitives/cn";

interface Props {
  isDrawerOpen: boolean;
  /** 그릴 메뉴 트리. 셸이 골라서 넘긴다 — 관리 셸은 자기 화면만 넘긴다(`selectAdminNavItems`). */
  items: NavItem[];
  children: ReactNode;
}

/**
 * 관리자 좌측 메뉴 (#341 — DevExtreme `Drawer` + `TreeView` 이관).
 *
 * `Drawer` 의 `openedStateMode="shrink"` 는 "열리면 본문을 그만큼 밀어낸다"였다 — 폭이
 * 0↔250px 로 바뀌는 flex 칸으로 그대로 옮겼다(`revealMode="slide"` 의 미끄러지는 느낌은
 * `transition-[width]` 가 대신하고, `prefers-reduced-motion` 사용자에겐 `motion-safe:` 로
 * 꺼진다).
 *
 * `TreeView` 는 명령형이었다 — ref 로 인스턴스를 잡아 `expandItem()`/`selectItem()` 을 부르고,
 * 선택 여부를 `getSelectedItems()` 로 되물어 렌더 중에 읽었다(렌더가 위젯 내부 상태에 의존하는
 * 형태라 선택 표시가 한 박자 늦게 반영됐다). 여기서는 현재 경로에서 **파생**한다 — 별도의 선택
 * 상태가 없으므로 어긋날 수가 없다. 펼침 상태만 사용자가 바꿀 수 있어 state 로 둔다.
 *
 * 접근성: `<nav>` 랜드마크 + `role="tree"`/`treeitem` 과 `aria-expanded`·`aria-selected` 를
 * 붙인다. 그룹은 실제 `<button>` 이라 Tab·Enter·Space 로 펼칠 수 있다.
 */
export function Sidebar({ isDrawerOpen, items: navItems, children }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const openTab = useTabStore((s) => s.openTab);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  /** 현재 경로에 해당하는 잎 노드와 그 조상들. 선택 표시·자동 펼침의 단일 출처다. */
  const activeTrail = useMemo(() => {
    const trail: string[] = [];
    const walk = (items: NavItem[], parents: string[]): boolean => {
      for (const item of items) {
        if (item.path && (item.path === pathname || pathname.endsWith(item.path))) {
          trail.push(...parents, item.id);
          return true;
        }
        if (item.items && walk(item.items, [...parents, item.id])) return true;
      }
      return false;
    };
    walk(navItems, []);
    return trail;
  }, [navItems, pathname]);

  // 현재 경로로 가는 길목은 자동으로 펼친다. 사용자가 따로 펼쳐 둔 것은 지우지 않는다.
  useEffect(() => {
    if (activeTrail.length <= 1) return;
    setExpandedIds((prev) => new Set([...prev, ...activeTrail.slice(0, -1)]));
  }, [activeTrail]);

  const handleLeafClick = useCallback(
    (item: NavItem) => {
      if (!item.path) return;
      openTab({ id: item.id, title: item.text, path: item.path });
      router.replace(item.path);
    },
    [router, openTab],
  );

  const renderItems = (items: NavItem[], depth: number): ReactNode => (
    <ul role={depth === 0 ? "tree" : "group"} className="w-full">
      {items.map((item) => {
        const hasChildren = !!item.items && item.items.length > 0;
        const isExpanded = expandedIds.has(item.id);
        const isSelected = activeTrail[activeTrail.length - 1] === item.id;

        return (
          <li key={item.id} role="none" className="w-full">
            <button
              type="button"
              role="treeitem"
              aria-expanded={hasChildren ? isExpanded : undefined}
              aria-selected={isSelected}
              onClick={() => {
                if (hasChildren) {
                  setExpandedIds((prev) => {
                    const next = new Set(prev);
                    if (next.has(item.id)) next.delete(item.id);
                    else next.add(item.id);
                    return next;
                  });
                  return;
                }
                handleLeafClick(item);
              }}
              style={{ paddingLeft: 8 + depth * 14 }}
              className={cn(
                "flex w-full items-center rounded px-2 py-1.5 text-left text-[15px] transition-colors",
                "focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500/40",
                isSelected ? "bg-blue-500 text-white hover:bg-blue-600" : "text-gray-900 hover:bg-gray-200",
              )}
            >
              {hasChildren && (
                <Icon
                  name={isExpanded ? "chevrondown" : "chevronright"}
                  size={14}
                  className={cn("mr-1 flex-shrink-0", isSelected ? "text-blue-100" : "text-gray-500")}
                />
              )}
              {item.icon && (
                <Icon
                  name={item.icon}
                  size={16}
                  className={cn("mr-2 flex-shrink-0", isSelected ? "text-blue-100" : "text-gray-500")}
                />
              )}
              <span className="truncate">{item.text}</span>
            </button>
            {hasChildren && isExpanded && renderItems(item.items!, depth + 1)}
          </li>
        );
      })}
    </ul>
  );

  return (
    <div className="flex h-full w-full">
      <nav
        aria-label="주 메뉴"
        // 닫힐 때 폭만 0 으로 줄이면 안쪽 내용이 삐져나온다 — `overflow-hidden` 이 잘라낸다.
        className={cn(
          "h-full flex-none overflow-hidden bg-[#F0F1F2] motion-safe:transition-[width] motion-safe:duration-200",
          isDrawerOpen ? "w-[250px]" : "w-0",
        )}
        // 닫힌 서랍은 화면에도 스크린리더에도 없어야 한다(Tab 이 보이지 않는 링크로 들어가지 않게).
        aria-hidden={!isDrawerOpen}
        inert={!isDrawerOpen}
      >
        <div className="h-full w-[250px] overflow-y-auto p-2">{renderItems(navItems, 0)}</div>
      </nav>
      <div className="h-full min-w-0 flex-1 overflow-x-hidden">{children}</div>
    </div>
  );
}
