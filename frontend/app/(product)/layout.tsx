"use client";

// 보안 경계 아님 — 이 파일 전체가 "use client" 라 아래 인가 체크는 브라우저에서 도는 UX 게이트일
// 뿐이다(레일과 본문에 뭘 보여줄지 결정). devtools/응답 변조로 우회 가능하고, 우회해도 이
// 컴포넌트가 렌더하는 건 화면 구조뿐 — 실제 데이터는 각 API Route 가 개별적으로
// `withAuth`(lib/auth/withAuth.ts)로 서버측 검증한다. 진짜 보안 경계는 거기다(실측: #299).
import { useState, useEffect, ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AppRail } from "@/components/shared/Layout";
import { showToast } from "@/components/shared/Feedback";
import { useNavStore } from "@/stores/shared/navStore";
import { RAIL_ITEMS, PANEL_WIDTH_PX } from "@/constants/shell";
import { collectNavPaths, matchesPath } from "@/lib/shell/nav";

// 권한 없는 경로 접근 시 되돌려 보낼 곳(로그인 화면). 로그인 후 착지점과는 다른 상수다 —
// 착지는 `constants/shell.ts` 의 `BENCH_PATH` 가 정한다.
const UNAUTHORIZED_REDIRECT_PATH = "/";

/** 레일이 여는 패널 자리의 DOM id — 레일 버튼의 `aria-controls` 가 이걸 가리킨다. */
const PANEL_REGION_ID = "product-panel";

/**
 * 제품 셸 — 46px 아이콘 레일 + 본문 + 372px 패널 자리 (화면 설계 §20.2).
 *
 * 관리 셸(`app/(main)/admin/layout.tsx`)과 다른 점이 셋이다: **iframe 이 없고**(제품 화면은
 * 언제나 최상위 문서다), **MDI 탭이 없으며**, 이동은 레일이 한다. 메뉴 게이트(fail-closed)만
 * 두 셸이 같이 쓴다 — `tn_menu` 에 없는 경로는 여기서도 열리지 않는다.
 *
 * 이 단계(S2)가 만드는 것은 **자리와 토글**까지다. 패널 내용과 §20.2 의 이동 규칙 3행
 * (보드↔패널 양방향 선택)은 S3 이 채운다.
 */
export default function ProductShellLayout({ children }: { children: ReactNode }) {
  const [openPanelId, setOpenPanelId] = useState<string | null>(null);
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const pathname = usePathname();
  const router = useRouter();
  const { items: navItems, fetchNav, loaded, error } = useNavStore();

  useEffect(() => {
    fetchNav();
  }, [fetchNav]);

  useEffect(() => {
    if (!loaded) return;

    // 네비 로드 실패 시 fail-closed — 제품 경로에는 예외가 없다.
    if (error) {
      showToast("메뉴 정보를 불러오지 못했습니다.", "error");
      setAuthorized(false);
      router.replace(UNAUTHORIZED_REDIRECT_PATH);
      return;
    }

    if (!collectNavPaths(navItems).some((p) => matchesPath(pathname, p))) {
      showToast("접근 권한이 없습니다.", "error");
      setAuthorized(false);
      router.replace(UNAUTHORIZED_REDIRECT_PATH);
      return;
    }
    setAuthorized(true);
  }, [loaded, error, pathname, navItems, router]);

  if (!loaded || authorized === null) return null;

  const openPanel = RAIL_ITEMS.find((item) => item !== null && item.kind === "panel" && item.id === openPanelId);

  return (
    <div className="flex h-screen bg-slate-void text-ink-primary">
      <AppRail
        openPanelId={openPanelId}
        onTogglePanel={(id) => setOpenPanelId((current) => (current === id ? null : id))}
        panelRegionId={PANEL_REGION_ID}
      />
      <main className="min-w-0 flex-1 overflow-hidden">{authorized ? children : null}</main>
      {openPanel != null && openPanel.kind === "panel" && (
        <aside
          id={PANEL_REGION_ID}
          aria-label={openPanel.label}
          style={{ width: PANEL_WIDTH_PX }}
          className="flex h-full flex-none flex-col gap-2 border-l border-slate-line bg-slate-panel p-4"
        >
          <h2 className="text-sm font-medium text-ink-primary">{openPanel.label}</h2>
          <p className="text-sm text-ink-muted">여기에 {openPanel.comingUp}이(가) 옵니다.</p>
        </aside>
      )}
    </div>
  );
}
