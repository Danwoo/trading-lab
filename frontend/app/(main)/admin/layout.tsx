"use client";

// 보안 경계 아님 — 이 파일 전체가 "use client" 라 아래 인가 체크는 브라우저에서 도는 UX 게이트일
// 뿐이다(메뉴·탭에 뭘 보여줄지 결정). devtools/응답 변조로 얼마든지 우회 가능하고, 우회해도 이
// 컴포넌트가 렌더하는 건 화면 구조(라벨·컬럼 헤더)뿐 — 실제 데이터는 각 API Route 가 개별적으로
// `withAuth`(lib/auth/withAuth.ts, `auth.api.getSession()`)로 서버측 검증한다. 진짜 보안 경계는
// 거기다. 여기서 authorized 를 조작해도 데이터 API 는 여전히 401/403 을 낸다(실측: #299).
import { useState, useEffect, useMemo, ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Header, Sidebar, GlobalTabs } from "@/components/shared/Layout";
import { showToast } from "@/components/shared/Feedback";
import { useNavStore } from "@/stores/shared/navStore";
import { useCodeStore } from "@/stores/shared/codeStore";
import { useTabStore } from "@/stores/shared/tabStore";
import { ADMIN_HOME_PATH } from "@/constants/shell";
import { collectNavPaths, findNavByPath, matchesPath, selectAdminNavItems } from "@/lib/shell/nav";

// DB 메뉴에 없지만 항상 접근 가능한 경로 + 탭 제목. Object.keys() 가 곧 access 체크용 path 목록.
const ALWAYS_ALLOWED_TABS: Record<string, string> = {
  "/admin/common/mypage": "마이페이지",
};
const ALWAYS_ALLOWED_PATHS = Object.keys(ALWAYS_ALLOWED_TABS);
// 권한 없는 경로 접근 시도 시 관리 셸 밖으로 (URL 직접 입력 같은 비정상 흐름 — 정상 사용자라면
// 사이드바를 거치므로 여기 도달 안 함). 로그인 후 착지점과는 다른 상수다 — 착지는
// `constants/shell.ts` 의 `BENCH_PATH` 가 정하고, 여기는 "되돌려 보낼 곳"이라 로그인 화면이다.
const UNAUTHORIZED_REDIRECT_PATH = "/";

export default function AdminLayout({ children }: { children: ReactNode }) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(true);
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [isEmbed, setIsEmbed] = useState<boolean | null>(null);
  const pathname = usePathname();
  const router = useRouter();
  const { items: navItems, fetchNav, loaded, error } = useNavStore();
  const { getGroupCodes } = useCodeStore();
  const openTab = useTabStore((s) => s.openTab);

  // 관리 셸은 자기 화면만 보여준다 — 제품 경로(`/bench`·`/terminal`)는 레일이 목적지로 소유하고
  // 여기 남으면 iframe 탭 안에서 열린다.
  const adminNavItems = useMemo(() => selectAdminNavItems(navItems), [navItems]);

  // iframe 내부인지 감지 (MDI 탭 콘텐츠로 로드된 경우 chrome 생략)
  useEffect(() => {
    setIsEmbed(window.self !== window.top);
  }, []);

  useEffect(() => {
    fetchNav();
  }, [fetchNav]);

  // 코드 데이터 로드
  useEffect(() => {
    getGroupCodes();
  }, [getGroupCodes]);

  useEffect(() => {
    if (!loaded) return;
    // 관리 셸의 진입점(`/admin`) 자체는 메뉴 행이 아니라 섀시다 — 여기서 고를 화면은 사이드바가
    // 개별적으로 게이팅한다.
    const isChassisHome = pathname === ADMIN_HOME_PATH;
    const isAlwaysAllowed = isChassisHome || ALWAYS_ALLOWED_PATHS.some((p) => matchesPath(pathname, p));

    // 네비 로드 실패 시 fail-closed — always-allowed 만 허용, 나머지는 로그인 화면으로
    if (error) {
      if (isAlwaysAllowed) {
        setAuthorized(true);
      } else {
        showToast("메뉴 정보를 불러오지 못했습니다.", "error");
        setAuthorized(false);
        router.replace(UNAUTHORIZED_REDIRECT_PATH);
      }
      return;
    }

    const hasAccess = isAlwaysAllowed || collectNavPaths(navItems).some((p) => matchesPath(pathname, p));
    if (!hasAccess) {
      showToast("접근 권한이 없습니다.", "error");
      setAuthorized(false);
      router.replace(UNAUTHORIZED_REDIRECT_PATH);
      return;
    }
    setAuthorized(true);
  }, [loaded, error, pathname, navItems, router]);

  // URL 직접 접근 시 nav 항목을 탭으로 자동 오픈 (메인 프레임에서만)
  useEffect(() => {
    if (isEmbed || !loaded || !authorized) return;
    const nav = findNavByPath(adminNavItems, pathname);
    if (nav?.path) {
      openTab({ id: nav.id, title: nav.text, path: nav.path });
      return;
    }
    const alwaysTitle = ALWAYS_ALLOWED_TABS[pathname];
    if (alwaysTitle) {
      openTab({ id: pathname, title: alwaysTitle, path: pathname });
    }
  }, [isEmbed, loaded, authorized, pathname, adminNavItems, openTab]);

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
        <Sidebar isDrawerOpen={isDrawerOpen} items={adminNavItems}>
          {authorized ? <GlobalTabs /> : null}
        </Sidebar>
      </div>
    </div>
  );
}
