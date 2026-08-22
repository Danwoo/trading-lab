"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { showToast } from "@/components/shared/Feedback";
import { useNavStore } from "@/stores/shared/navStore";
import { fallbackPathWithReason } from "@/constants/routes";

/**
 * 화면을 안 연 사유 — **「못 읽음」과 「권한 없음」은 다른 사건이다.**
 *
 * - `unreadable` — 메뉴를 못 읽었다. 권한이 있는지 **모르는** 상태라 막을 뿐, 계정 상태와는
 *   무관하다. 되돌리지 않고 셸 안에서 사유를 세운다
 * - `forbidden` — 메뉴를 읽었고, 이 경로가 거기 없다. 계정 상태 이야기라 제품 밖으로 되돌린다
 */
export type MenuGateDenial = "unreadable" | "forbidden";

/** 기본값을 모듈 상수로 둔다 — 인자에 `[]` 리터럴을 쓰면 렌더마다 새 배열이라 이펙트가 무한히 돈다. */
const NO_ALWAYS_ALLOWED_PATHS: readonly string[] = [];

/** 정확히 같거나 슬래시 경계로 시작 (`/admin/foo` 가 `/admin/foobar` 를 먹는 over-match 방지) */
const matchesPath = (pathname: string, allowed: string): boolean =>
  pathname === allowed || pathname.startsWith(allowed + "/");

/**
 * DB 메뉴 기반 화면 접근 게이트 — **fail-closed**.
 *
 * 보안 경계가 아니다. 브라우저에서 도는 UX 게이트일 뿐이고(무엇을 렌더할지 결정), devtools·
 * 응답 변조로 우회할 수 있다. 실제 데이터는 각 API Route 의 `withAuth`(서버측 세션 검증)가
 * 지킨다 — 여기서 `authorized` 를 조작해도 데이터 API 는 401/403 을 낸다(실측: #299).
 *
 * 관리 셸(`app/admin/layout.tsx`)과 제품 셸(`app/(main)/layout.tsx`)이 둘 다 쓴다. 셸이
 * 둘로 갈리면서 게이트도 두 벌이 될 뻔했는데, 두 벌이 되면 한쪽만 고쳐 다른 쪽이 조용히
 * 열리는 사고가 난다(`#68` 이 그 계열이었다) — 그래서 한 자리에 둔다.
 *
 * @param alwaysAllowedPaths DB 메뉴에 없어도 여는 경로. **하위 경로까지 함께 열린다.**
 *   **모듈 상수를 넘겨라** — 렌더마다 새 배열을 만들면 아래 이펙트가 매 렌더 다시 돈다.
 * @param exactAllowedPaths DB 메뉴에 없어도 여는 경로 중 **자기 자신만** 여는 것. 셸의 진입점
 *   (`/admin`)처럼 하위가 전부 메뉴로 게이팅돼야 하는 자리에 쓴다 — 이것을
 *   `alwaysAllowedPaths` 에 넣으면 접두어 매칭이라 `/admin/*` 전체가 게이트 밖으로 나간다.
 */
export function useMenuAccessGate(
  alwaysAllowedPaths: readonly string[] = NO_ALWAYS_ALLOWED_PATHS,
  exactAllowedPaths: readonly string[] = NO_ALWAYS_ALLOWED_PATHS,
) {
  const [authorized, setAuthorized] = useState<boolean | null>(null);
  const [denial, setDenial] = useState<MenuGateDenial | null>(null);
  const pathname = usePathname();
  const router = useRouter();
  const { fetchNav, getAllPaths, loaded, error } = useNavStore();

  useEffect(() => {
    fetchNav();
  }, [fetchNav]);

  useEffect(() => {
    // 다시 읽는 동안(`loaded === false`)에도 직전 판정을 지우지 않는다 — 지우면 셸이 사유
    // 화면을 걷어내고 그 자리가 빈다.
    if (!loaded) return;
    const isAlwaysAllowed =
      exactAllowedPaths.includes(pathname) || alwaysAllowedPaths.some((p) => matchesPath(pathname, p));

    // 네비를 **못 읽은 것**은 fail-closed 로 막되 되돌리지는 않는다 — 세션은 유효하므로
    // 로그인 화면으로 보내면 로그아웃된 것으로 읽힌다. 셸이 이 판정으로 사유 화면을 세운다.
    if (error) {
      setDenial(isAlwaysAllowed ? null : "unreadable");
      setAuthorized(isAlwaysAllowed);
      return;
    }

    const hasAccess = isAlwaysAllowed || getAllPaths().some((p) => matchesPath(pathname, p));
    if (!hasAccess) {
      showToast("접근 권한이 없습니다.", "error");
      setDenial("forbidden");
      setAuthorized(false);
      router.replace(fallbackPathWithReason("forbidden"));
      return;
    }
    setDenial(null);
    setAuthorized(true);
  }, [loaded, error, pathname, getAllPaths, router, alwaysAllowedPaths, exactAllowedPaths]);

  return { loaded, authorized, denial };
}
