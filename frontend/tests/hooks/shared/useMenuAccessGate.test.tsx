// @vitest-environment jsdom
//
// 메뉴 게이트의 「예외 경로」 회귀 그물 — **예외가 하위까지 새지 않는가.**
//
// 레일의 「설정」이 `/admin` 으로 가려면 그 경로가 게이트를 통과해야 하는데, `/admin` 은 메뉴
// 행이 아니라 섀시 자체다. 이걸 접두어 매칭 목록(`alwaysAllowedPaths`)에 넣으면 `/admin/*`
// 전체가 게이트 밖으로 나가 관리 화면이 통째로 열린다 — 열리는 쪽으로 고장 나므로 화면만 봐서는
// 아무도 눈치채지 못한다. 그래서 정확 일치 목록(`exactAllowedPaths`)을 따로 두고, 이 파일이
// **두 목록이 서로의 역할을 넘지 않는지**를 본다.
//
// fail-closed: 검사한 경로 수를 단언에 실어, 케이스 표가 비면 통과가 아니라 실패가 되게 한다.
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useMenuAccessGate } from "@/hooks/shared/useMenuAccessGate";
import { useNavStore } from "@/stores/shared/navStore";

const replace = vi.fn();
let pathname = "/";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ replace }),
}));

vi.mock("@/components/shared/Feedback", () => ({
  showToast: vi.fn(),
}));

/** 메뉴에 든 화면 하나짜리 네비게이션 — `/admin/watchlist` 만 권한이 있는 상태. */
const NAV_ITEMS = [
  { id: "mbiz0000", text: "업무관리", items: [{ id: "mbiz1001", text: "관심종목", path: "/admin/watchlist" }] },
];

/** 접두어로 열리는 예외 (하위까지 열린다) */
const PREFIX_ALLOWED = ["/admin/common/mypage"];
/** 자기 자신만 열리는 예외 (하위는 메뉴 게이트가 그대로 본다) */
const EXACT_ALLOWED = ["/admin"];

function Probe() {
  const { authorized } = useMenuAccessGate(PREFIX_ALLOWED, EXACT_ALLOWED);
  return <span data-testid="authorized">{String(authorized)}</span>;
}

/** 경로 하나를 게이트에 통과시켜 판정을 돌려준다. */
async function gate(path: string): Promise<boolean | null> {
  pathname = path;
  render(<Probe />);
  await waitFor(() => expect(screen.getByTestId("authorized").textContent).not.toBe("null"));
  return screen.getByTestId("authorized").textContent === "true";
}

interface Case {
  path: string;
  allowed: boolean;
  why: string;
}

const CASES: Case[] = [
  { path: "/admin", allowed: true, why: "섀시 진입점 — 정확 일치 예외" },
  { path: "/admin/watchlist", allowed: true, why: "메뉴에 있는 화면" },
  { path: "/admin/common/mypage", allowed: true, why: "접두어 예외" },
  { path: "/admin/common/mypage/detail", allowed: true, why: "접두어 예외의 하위" },
  { path: "/admin/common/system/code", allowed: false, why: "메뉴에 없다 — 정확 일치 예외가 새면 여기가 열린다" },
  { path: "/admin/nav", allowed: false, why: "메뉴에 없다 — 정확 일치 예외가 새면 여기가 열린다" },
  { path: "/adminx", allowed: false, why: "`/admin` 의 슬래시 경계 밖 (over-match 방지)" },
];

describe("메뉴 게이트의 예외 경로 (#73 S2 — 레일의 「설정」)", () => {
  beforeEach(() => {
    replace.mockClear();
    useNavStore.setState({ items: NAV_ITEMS, loaded: true, failure: null });
  });

  afterEach(cleanup);

  it("케이스가 0건이 아니다 — 표가 비면 아래 단언들이 조용히 통과한다", () => {
    expect(CASES.length, "검사 경로가 없다").toBeGreaterThan(5);
    expect(CASES.filter((c) => !c.allowed).length, "막혀야 하는 경로가 0건이면 fail-open 을 못 잡는다").toBeGreaterThan(
      0,
    );
    expect(EXACT_ALLOWED.length, "정확 일치 예외 목록이 비었다").toBeGreaterThan(0);
  });

  for (const { path, allowed, why } of CASES) {
    it(`${path} → ${allowed ? "열린다" : "막힌다"} (${why})`, async () => {
      expect(await gate(path)).toBe(allowed);
      if (allowed) {
        expect(replace, `${path} 가 되돌려졌다`).not.toHaveBeenCalled();
      } else {
        // 되돌릴 때 **사유를 실어 보낸다** — 사유 없이 로그인 화면에 도착하면 세션이 멀쩡한
        // 사람이 로그아웃된 줄 안다(#333). 목적지 자체는 종전과 같다.
        expect(replace, `${path} 가 게이트를 그냥 통과했다`).toHaveBeenCalledWith("/?reason=forbidden");
      }
    });
  }

  it("정확 일치 예외는 하위 경로를 열지 않는다 — 접두어 목록에 넣었을 때와 갈린다", async () => {
    // 이 단언이 실패하면 `exactAllowedPaths` 가 접두어 매칭으로 퇴화한 것이다.
    const underChassis = CASES.filter((c) => c.path.startsWith("/admin/") && !c.allowed);
    expect(underChassis.length, "섀시 하위의 차단 케이스가 0건이다").toBeGreaterThan(0);
    for (const c of underChassis) {
      cleanup();
      replace.mockClear();
      expect(await gate(c.path), `${c.path} 가 열렸다`).toBe(false);
    }
  });
});
