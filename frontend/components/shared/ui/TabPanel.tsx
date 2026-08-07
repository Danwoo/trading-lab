// components/shared/ui/TabPanel.tsx
//
// 탭 네비게이션 (#341 ② — Radix `Tabs`).
//
// **왜 `TabContent` 가 Radix `Tabs.Content` 를 그대로 쓰지 않는가**: 이 레포의 탭 콘텐츠는
// 그리드·폼처럼 마운트 비용이 있는 화면이고, 이관 전 구현은 "한 번 열린 탭은 언마운트하지 않고
// `display:none` 으로 숨긴다"였다(아래 `mounted` 상태). Radix 는 기본적으로 비활성 탭을
// 언마운트하고 `forceMount` 를 주면 **처음부터 전부** 마운트한다 — 둘 다 기존 동작과 다르다
// (전자는 탭을 옮길 때마다 그리드가 재요청, 후자는 첫 렌더에 모든 탭이 데이터를 요청).
// 그래서 `forceMount` + 자체 지연 마운트로 이관 전 동작을 그대로 유지한다.
"use client";

import React, { createContext, useContext, useState } from "react";
import { Tabs as TabsPrimitive } from "radix-ui";
import { cn } from "./primitives/cn";
import { Icon } from "./primitives/icons";

interface TabItem {
  id: string;
  text: string;
  /**
   * 아이콘 **이름**(`"edit"`·`"group"` 등, `primitives/icons.tsx` 의 `ICON_COMPONENTS` 키).
   * CSS 클래스 문자열이 아니다 — 이관 전에는 `dx-icon-<name>` 폰트 클래스였고, 그 폰트가
   * `dx.light.css` 와 함께 사라졌다(#341).
   */
  icon?: string;
  badge?: string;
  disabled?: boolean;
}

interface Props {
  items: TabItem[];
  children: React.ReactNode;
  defaultTab?: string;
  onSelectionChanged?: (selectedItem: any) => void;
  className?: string;
}

const TabPanelContext = createContext<{ activeTab: string }>({ activeTab: "" });
const useTabPanelContext = () => useContext(TabPanelContext);

/**
 * 탭 헤더와 콘텐츠를 통합 관리하는 탭 패널 컴포넌트
 *
 * Radix `Tabs` 가 `role="tablist"`/`tab`/`tabpanel` 과 방향키 순회(←→·Home·End)를 배선한다 —
 * 이관 전 DevExtreme `Tabs` 는 `focusStateEnabled={false}` 로 켜져 있어 키보드로 탭을 옮길 수
 * 없었다(이번 이관에서 함께 살아난 접근성).
 */
export function TabPanel({ items, children, defaultTab, onSelectionChanged, className }: Props) {
  const [activeTab, setActiveTab] = useState(defaultTab || items[0]?.id || "");

  return (
    <TabPanelContext.Provider value={{ activeTab }}>
      <TabsPrimitive.Root
        value={activeTab}
        onValueChange={(next) => {
          setActiveTab(next);
          const item = items.find((entry) => entry.id === next);
          if (item) onSelectionChanged?.(item);
        }}
        className="flex h-full flex-col"
      >
        <div className="mb-2 flex-shrink-0">
          <TabsPrimitive.List className={cn("flex w-full", className)}>
            {items.map((item) => (
              <TabsPrimitive.Trigger
                key={item.id}
                value={item.id}
                disabled={item.disabled}
                className={cn(
                  "flex flex-1 items-center justify-center gap-1 border-none px-3 py-2 text-sm",
                  "bg-gray-200 text-gray-700 hover:bg-gray-100",
                  "focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500/40",
                  "data-[state=active]:bg-white data-[state=active]:font-medium data-[state=active]:text-gray-900",
                  "disabled:cursor-not-allowed disabled:bg-gray-100 disabled:opacity-60",
                )}
              >
                {/* 옆에 `item.text` 가 보이므로 아이콘은 장식이다 — `label` 을 안 주면
                    `Icon` 이 스스로 `aria-hidden` 을 붙인다. Button·Sidebar·GlobalTabs 와
                    같은 경로다(이 컴포넌트만 이관에서 빠져 있었다). */}
                {item.icon && <Icon name={item.icon} />}
                <span>{item.text}</span>
                {item.badge && (
                  <span className="ml-1 rounded-full bg-blue-600 px-1.5 text-xs text-white">{item.badge}</span>
                )}
              </TabsPrimitive.Trigger>
            ))}
          </TabsPrimitive.List>
        </div>
        <div className="min-h-0 flex-1">{children}</div>
      </TabsPrimitive.Root>
    </TabPanelContext.Provider>
  );
}

/**
 * 탭 콘텐츠 컴포넌트
 *
 * 한 번 열린 탭은 숨기기만 하고 언마운트하지 않는다 — 탭을 오갈 때 그리드가 매번 재요청하지
 * 않게 하려는 이관 전 동작을 그대로 유지한다(파일 상단 주석 참조).
 */
export const TabContent = ({
  tabId,
  children,
  className = "h-full",
}: {
  tabId: string;
  children: React.ReactNode;
  className?: string;
}) => {
  const { activeTab } = useTabPanelContext();
  const isActive = activeTab === tabId;
  const [mounted, setMounted] = React.useState(isActive);

  React.useEffect(() => {
    if (isActive && !mounted) setMounted(true);
  }, [isActive, mounted]);

  return (
    <TabsPrimitive.Content
      value={tabId}
      forceMount
      className={className}
      style={!isActive ? { display: "none" } : undefined}
    >
      {mounted ? children : null}
    </TabsPrimitive.Content>
  );
};
