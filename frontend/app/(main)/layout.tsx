"use client";

// 보안 경계 아님 — 이 파일 전체가 "use client" 라 아래 인가 체크는 브라우저에서 도는 UX 게이트일
// 뿐이다(메뉴·탭에 뭘 보여줄지 결정). devtools/응답 변조로 얼마든지 우회 가능하고, 우회해도 이
// 컴포넌트가 렌더하는 건 화면 구조(라벨·컬럼 헤더)뿐 — 실제 데이터는 각 API Route 가 개별적으로
// `withAuth`(lib/auth/withAuth.ts, `auth.api.getSession()`)로 서버측 검증한다. 진짜 보안 경계는
// 거기다. 여기서 authorized 를 조작해도 데이터 API 는 여전히 401/403 을 낸다(실측: #299).
import { useState, useEffect, ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Header, Sidebar, GlobalTabs } from "@/components/shared/Layout";
import { showToast } from "@/components/shared/Feedback";
import { useNavStore } from "@/stores/shared/navStore";
import { useTabStore } from "@/stores/shared/tabStore";

// path 매칭: 정확히 같거나 슬래시 경계로 시작 (`/admin/foo` 가 `/admin/foobar` 잘못 매칭하는 over-match 방지)
const matchesPath = (pathname: string, allowed: string): boolean =>
  pathname === allowed || pathname.startsWith(allowed + "/");

// DB 메뉴에 없지만 항상 접근 가능한 경로 + 탭 제목. Object.keys() 가 곧 access 체크용 path 목록.
const ALWAYS_ALLOWED_TABS: Record<string, string> = {
  "/admin/common/mypage": "마이페이지",
};
const ALWAYS_ALLOWED_PATHS = Object.keys(ALWAYS_ALLOWED_TABS);
// 권한 없는 경로 접근 시도 시 admin 밖으로 (URL 직접 입력 같은 비정상 흐름 — 정상 사용자라면 사이드바를 거치므로 여기 도달 안 함)
const FALLBACK_PATH = "/";

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

export default function RootLayout({ children }: { children: ReactNode }) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(true);
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [isEmbed, setIsEmbed] = useState<boolean | null>(null);
  const pathname = usePathname();
  const router = useRouter();
  const { items: navItems, fetchNav, getAllPaths, loaded, error } = useNavStore();
  const openTab = useTabStore((s) => s.openTab);

  // iframe 내부인지 감지 (MDI 탭 콘텐츠로 로드된 경우 chrome 생략)
  useEffect(() => {
    setIsEmbed(window.self !== window.top);
  }, []);

  useEffect(() => {
    fetchNav();
  }, [fetchNav]);

  useEffect(() => {
    if (!loaded) return;
    const isAlwaysAllowed = ALWAYS_ALLOWED_PATHS.some((p) => matchesPath(pathname, p));

    // 네비 로드 실패 시 fail-closed — always-allowed 만 허용, 나머지는 fallback 으로
    if (error) {
      if (isAlwaysAllowed) {
        setAuthorized(true);
      } else {
        showToast("메뉴 정보를 불러오지 못했습니다.", "error");
        setAuthorized(false);
        router.replace(FALLBACK_PATH);
      }
      return;
    }

    const hasAccess = isAlwaysAllowed || getAllPaths().some((p) => matchesPath(pathname, p));
    if (!hasAccess) {
      showToast("접근 권한이 없습니다.", "error");
      setAuthorized(false);
      router.replace(FALLBACK_PATH);
      return;
    }
    setAuthorized(true);
  }, [loaded, error, pathname, getAllPaths, router]);

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
    <>
      <div className="h-screen flex flex-col">
        <div className="flex-shrink-0">
          <Header isDrawerOpen={isDrawerOpen} setIsDrawerOpen={setIsDrawerOpen} />
        </div>
        <div className="flex-1 min-h-0">
          <Sidebar isDrawerOpen={isDrawerOpen}>{authorized ? <GlobalTabs /> : null}</Sidebar>
        </div>
      </div>
    </>
  );
}
