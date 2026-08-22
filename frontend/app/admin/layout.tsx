"use client";

import { useState, useEffect, ReactNode } from "react";
import { usePathname } from "next/navigation";
import { Header, Sidebar, GlobalTabs } from "@/components/shared/Layout";
import { MenuUnreadableScreen } from "@/components/shared/Layout/MenuUnreadableScreen";
import { useMenuAccessGate } from "@/hooks/shared/useMenuAccessGate";
import { useCodeStore } from "@/stores/shared/codeStore";
import { useNavStore } from "@/stores/shared/navStore";
import { useTabStore } from "@/stores/shared/tabStore";
import { ADMIN_PATH } from "@/constants/routes";

// DB 메뉴에 없지만 항상 접근 가능한 경로 + 탭 제목. Object.keys() 가 곧 access 체크용 path 목록.
const ALWAYS_ALLOWED_TABS: Record<string, string> = {
  "/admin/common/mypage": "마이페이지",
};
const ALWAYS_ALLOWED_PATHS = Object.keys(ALWAYS_ALLOWED_TABS);

/**
 * 섀시의 진입점 — 레일의 「설정」이 오는 자리. 메뉴 행이 아니므로 게이트가 따로 열어야 한다.
 *
 * `ALWAYS_ALLOWED_TABS` 에 넣지 않는 이유가 둘이다. 첫째, 그 목록은 **접두어**로 매칭돼
 * `/admin/*` 전체가 게이트 밖으로 나간다. 둘째, 그 목록의 값은 탭 제목이라 여기에 넣으면
 * 셸이 자기 자신을 iframe 탭으로 연다. 여기서 고를 화면은 사이드바가 개별로 게이팅한다.
 */
const CHASSIS_HOME_PATHS = [ADMIN_PATH];

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
  const { loaded, authorized, denial } = useMenuAccessGate(ALWAYS_ALLOWED_PATHS, CHASSIS_HOME_PATHS);

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

  // 메뉴를 못 읽으면 섀시를 세우지 않는다 — 사이드바·탭이 전부 메뉴로 그려져 빈 크롬만 남는다.
  //
  // **아래 로딩 분기보다 먼저 본다.** 「다시 시도」는 `loaded` 를 false 로 내렸다가 다시 올리는데,
  // 로딩 분기가 앞서면 그 사이 사유 화면이 빈 라이트 화면으로 바뀌었다가 실패하면 되돌아온다 —
  // 게이트가 직전 판정을 보존하는 이유(`useMenuAccessGate` 주석)가 여기서 무효가 된다.
  // 제품 셸은 이미 이 순서다(`app/(main)/layout.tsx` — `denial` 을 `settled` 보다 먼저 본다).
  if (denial === "unreadable")
    return (
      <div data-theme="light" className="h-screen bg-bg-base text-ink">
        <MenuUnreadableScreen />
      </div>
    );

  // 게이트가 열리기 전에도 **라이트 바탕을 깐다.** `null` 을 돌려주면 그 구간의 문서 캔버스가
  // 보이는데, `:root` 의 `color-scheme: dark` 때문에 그 캔버스는 어둡다 — 라이트 셸이 뜨는
  // 순간 화면이 검정에서 흰색으로 튄다.
  if (isEmbed === null || !loaded || authorized === null)
    return <div data-theme="light" className="h-screen bg-bg-base" />;

  // **관리 화면은 라이트다** — 그 사실을 선언한다.
  //
  // 토큰(`--ink`·`--bg-*`)은 `:root` 가 다크 기본이고 `[data-theme="light"]` 가 라이트다
  // (`styles/globals.css:64,204`). 이 셸이 그 선언을 안 해서, 공용 프리미티브가 토큰을 못 쓰고
  // 원시 색(`bg-white`·`text-gray-900`)을 박아 왔다 — 그 프리미티브가 다크 보드에서 재사용되자
  // 흰 상자가 됐다. 선언 한 줄이 그 갈래를 없앤다.
  //
  // iframe 내부: chrome 없이 페이지만 렌더 (탭 콘텐츠)
  //
  // **탭 본문은 앱 배경이 아니라 패널이다.** 이 안의 상세 폼은 자기 바탕을 안 칠해서, 공용
  // 입력의 그릇이 여기까지 그대로 내려온다(실측: 입력 위로 투명한 조상 23개). 여기를
  // `--bg-base` 로 두면 그 입력의 채움(`--bg-base`)과 **같은 색**이 된다. 앱 배경은 아래
  // 메인 프레임 섀시가 칠하고, 탭 본문은 그 위에 얹힌 패널이라 `--bg-panel` 이 맞다.
  if (isEmbed) {
    return (
      <>
        <style>{`nextjs-portal { display: none !important; }`}</style>
        <div data-theme="light" className="h-screen bg-bg-panel text-ink">
          {authorized ? children : null}
        </div>
      </>
    );
  }

  // 메인 프레임: Header + Sidebar + MDI 탭 섀시
  return (
    <div data-theme="light" className="h-screen flex flex-col bg-bg-base text-ink">
      <div className="flex-shrink-0">
        <Header isDrawerOpen={isDrawerOpen} setIsDrawerOpen={setIsDrawerOpen} />
      </div>
      <div className="flex-1 min-h-0">
        <Sidebar isDrawerOpen={isDrawerOpen}>{authorized ? <GlobalTabs /> : null}</Sidebar>
      </div>
    </div>
  );
}
