"use client";

import { useState, useEffect, ReactNode } from "react";
import { usePathname } from "next/navigation";
import { Header, Sidebar, GlobalTabs } from "@/components/shared/Layout";
import { useMenuAccessGate } from "@/hooks/shared/useMenuAccessGate";
import { useCodeStore } from "@/stores/shared/codeStore";
import { useNavStore } from "@/stores/shared/navStore";
import { useTabStore } from "@/stores/shared/tabStore";

// DB 메뉴에 없지만 항상 접근 가능한 경로 + 탭 제목. Object.keys() 가 곧 access 체크용 path 목록.
const ALWAYS_ALLOWED_TABS: Record<string, string> = {
  "/admin/common/mypage": "마이페이지",
};
const ALWAYS_ALLOWED_PATHS = Object.keys(ALWAYS_ALLOWED_TABS);

interface NavItem {
  id: string;
  text: string;
  icon?: string;
  path?: string;
  items?: NavItem[];
}

function findNavByPath(items: NavItem[], path: string): NavItem | null {
  for (const item of items) {
    if (item.path === path) return item;
    if (item.items) {
      const found = findNavByPath(item.items, path);
      if (found) return found;
    }
  }
  return null;
}

/**
 * 관리 셸 — MDI 탭 섀시(`Header` + `Sidebar` + `GlobalTabs` iframe).
 *
 * 이 섀시는 `/admin` **에만** 있다(결정 로그 2026-07-28, 화면 결정 §20.3). 제품 화면은
 * `app/(main)/layout.tsx` 의 레일 셸을 쓰고 iframe 을 쓰지 않는다 — 크롬 두 겹을 피하려는
 * 것이라 두 셸은 한 파일을 공유하지 않는다(공유하는 것은 메뉴 게이트 하나뿐이다).
 *
 * `isEmbed` 분기가 이 구조의 핵심이다: 탭 콘텐츠는 자기 자신을 iframe 으로 다시 로드하므로
 * (`GlobalTabs` 의 `<iframe src={tab.path}>`), 안쪽 인스턴스는 크롬 없이 페이지만 그려야 한다.
 * 이 분기가 없으면 탭 안에 헤더·사이드바·탭바가 한 겹 더 그려진다.
 */
export default function AdminLayout({ children }: { children: ReactNode }) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(true);
  const [isEmbed, setIsEmbed] = useState<boolean | null>(null);
  const pathname = usePathname();
  const { getGroupCodes } = useCodeStore();
  const navItems = useNavStore((s) => s.items);
  const openTab = useTabStore((s) => s.openTab);
  const { loaded, authorized } = useMenuAccessGate(ALWAYS_ALLOWED_PATHS);

  // iframe 내부인지 감지 (MDI 탭 콘텐츠로 로드된 경우 chrome 생략)
  useEffect(() => {
    setIsEmbed(window.self !== window.top);
  }, []);

  useEffect(() => {
    getGroupCodes();
  }, [getGroupCodes]);

  // URL 직접 접근 시 nav 항목을 탭으로 자동 오픈 (메인 프레임에서만)
  useEffect(() => {
    if (isEmbed || !loaded || !authorized) return;
    const nav = findNavByPath(navItems, pathname);
    if (nav?.path) {
      openTab({ id: nav.id, title: nav.text, path: nav.path });
      return;
    }
    const alwaysTitle = ALWAYS_ALLOWED_TABS[pathname];
    if (alwaysTitle) {
      openTab({ id: pathname, title: alwaysTitle, path: pathname });
    }
  }, [isEmbed, loaded, authorized, pathname, navItems, openTab]);

  if (isEmbed === null || !loaded || authorized === null) return null;

  // iframe 내부: chrome 없이 페이지만 렌더 (탭 콘텐츠)
  if (isEmbed) {
    return (
      <>
        <style>{`nextjs-portal { display: none !important; }`}</style>
        <div className="h-screen">{authorized ? children : null}</div>
      </>
    );
  }

  // 메인 프레임: Header + Sidebar + MDI 탭 섀시
  return (
    <div className="h-screen flex flex-col">
      <div className="flex-shrink-0">
        <Header isDrawerOpen={isDrawerOpen} setIsDrawerOpen={setIsDrawerOpen} />
      </div>
      <div className="flex-1 min-h-0">
        <Sidebar isDrawerOpen={isDrawerOpen}>{authorized ? <GlobalTabs /> : null}</Sidebar>
      </div>
    </div>
  );
}
