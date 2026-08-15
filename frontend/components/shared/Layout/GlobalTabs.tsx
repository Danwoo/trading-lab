"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useTabStore, OpenedTab } from "@/stores/shared/tabStore";
import { Icon } from "@/components/shared/ui/primitives/icons";
import { cn } from "@/components/shared/ui/primitives/cn";

/**
 * 열린 화면 탭 바 (#341 — DevExtreme `Tabs` + `Sortable` 이관).
 *
 * 이관 전에는 DevExtreme `Tabs` 를 `Sortable` 로 감싸고, 그 위에 100줄이 넘는 `!important` CSS 로
 * 라이브러리 기본 스타일을 되돌리고 있었다. 탭 목록은 결국 "가로 스크롤되는 버튼 줄 + 드래그
 * 재정렬"이라 네이티브 HTML5 드래그로 그대로 옮기고 그 CSS 블록은 통째로 사라졌다.
 *
 * 접근성: `role="tablist"`/`tab` 을 직접 붙이고 ←→·Home·End 로 탭을 옮긴다(이관 전에는
 * 키보드로 탭을 옮길 수 없었다). 닫기는 각 탭 안의 실제 `<button>` 이라 Tab 으로 도달한다.
 * 드래그는 마우스 전용 보조 수단이라 키보드 대체 경로가 필요 없다(순서 변경은 편의 기능이고,
 * 모든 탭은 순서와 무관하게 도달 가능하다).
 */
export function GlobalTabs() {
  const router = useRouter();
  const tabs = useTabStore((s) => s.tabs);
  const activeId = useTabStore((s) => s.activeId);
  const setActive = useTabStore((s) => s.setActive);
  const reorderTabs = useTabStore((s) => s.reorderTabs);

  const dragFromIndex = useRef<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  // 드래그 재정렬 시 iframe이 reload되지 않도록 DOM 순서 고정
  const iframeTabs = useMemo(() => [...tabs].sort((a, b) => a.id.localeCompare(b.id)), [tabs]);

  const openTab = useCallback(
    (tab: OpenedTab) => {
      if (tab.id === activeId) return;
      setActive(tab.id);
      router.replace(tab.path);
    },
    [router, setActive, activeId],
  );

  const handleCloseClick = useCallback(
    (e: React.MouseEvent, tab: OpenedTab) => {
      e.stopPropagation();
      e.preventDefault();
      const { tabs: currentTabs, activeId: currentActiveId, closeTab: doClose } = useTabStore.getState();
      const idx = currentTabs.findIndex((t) => t.id === tab.id);
      doClose(tab.id);
      if (currentActiveId === tab.id) {
        const next = useTabStore.getState();
        const nextTab = next.tabs[Math.min(idx, next.tabs.length - 1)] ?? null;
        if (nextTab) router.replace(nextTab.path);
      }
    },
    [router],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, index: number) => {
      const move = (nextIndex: number) => {
        e.preventDefault();
        const target = tabs[nextIndex];
        if (target) openTab(target);
      };
      if (e.key === "ArrowRight") move((index + 1) % tabs.length);
      else if (e.key === "ArrowLeft") move((index - 1 + tabs.length) % tabs.length);
      else if (e.key === "Home") move(0);
      else if (e.key === "End") move(tabs.length - 1);
    },
    [tabs, openTab],
  );

  return (
    <div className="flex h-full flex-col">
      {tabs.length > 0 && (
        <div role="tablist" aria-label="열린 화면" className="flex flex-none overflow-x-auto border-t bg-gray-100">
          {tabs.map((tab, index) => {
            const isActive = tab.id === activeId;
            return (
              <div
                key={tab.id}
                role="tab"
                aria-selected={isActive}
                tabIndex={isActive ? 0 : -1}
                title={tab.title}
                draggable
                onDragStart={() => {
                  dragFromIndex.current = index;
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOverIndex(index);
                }}
                onDragLeave={() => setDragOverIndex((current) => (current === index ? null : current))}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOverIndex(null);
                  const from = dragFromIndex.current;
                  dragFromIndex.current = null;
                  if (from !== null && from !== index) reorderTabs(from, index);
                }}
                onDragEnd={() => {
                  dragFromIndex.current = null;
                  setDragOverIndex(null);
                }}
                onClick={() => openTab(tab)}
                onKeyDown={(e) => handleKeyDown(e, index)}
                className={cn(
                  "flex w-[130px] min-w-[130px] cursor-pointer items-center gap-1 border-b-2 px-2.5 py-1 text-sm",
                  "focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500/40",
                  isActive
                    ? "border-blue-500 bg-white text-gray-900"
                    : "border-transparent text-gray-600 hover:bg-white/50 hover:border-gray-400",
                  dragOverIndex === index ? "border-l-2 border-l-gray-400" : "",
                )}
              >
                <span className="min-w-0 flex-1 truncate text-left">{tab.title}</span>
                <button
                  type="button"
                  aria-label={`${tab.title} 닫기`}
                  className="ml-auto flex-shrink-0 rounded p-0.5 hover:bg-gray-300"
                  onClick={(e) => handleCloseClick(e, tab)}
                >
                  <Icon name="close" size={11} />
                </button>
              </div>
            );
          })}
        </div>
      )}
      <div className="relative min-h-0 flex-1 bg-gray-50">
        {iframeTabs.map((tab) => {
          const isActive = tab.id === activeId;
          return (
            <iframe
              key={tab.id}
              src={tab.path}
              className="absolute inset-0 h-full w-full border-0"
              style={{ visibility: isActive ? "visible" : "hidden", zIndex: isActive ? 1 : 0 }}
              title={tab.title}
            />
          );
        })}
      </div>
    </div>
  );
}
