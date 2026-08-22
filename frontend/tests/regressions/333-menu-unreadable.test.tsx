// @vitest-environment jsdom
//
// #333 — **「메뉴를 못 읽음」과 「접근 권한 없음」은 다른 사건이다.**
//
// 실측(이슈 본문): 세션이 유효한데 메뉴 API 가 500 이면 `/bench` 진입 +485ms 에 `/` 로
// 되돌려졌고, 유일한 사유인 토스트가 2.03초 뒤 사라졌다. 남는 것은 로그인 폼 — 로그인돼
// 있는 사람이 로그인 화면을 보고, 도착지는 왜 왔는지 한 글자도 말하지 않았다.
//
// 여기서 잡는 것은 셋이다.
//   ㉠ 못 읽었을 때 **되돌리지 않는다** (권한 없음의 출구와 갈린다)
//   ㉡ 사유가 **시간이 지나도 화면에 남는다** (2초 토스트가 아니다)
//   ㉢ 「못 읽음」과 「0건」이 **다른 문구**로 갈리고, 둘 다 「관리자에게 문의」로 끝나지 않는다
//      (로컬 배포판이라 그 관리자가 화면을 보는 사람 자신이다)
//
// fail-closed: 검사한 케이스 수를 단언에 실어, 표가 비면 통과가 아니라 실패가 되게 한다.
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ProductLayout from "@/app/(main)/layout";
import AdminLayout from "@/app/admin/layout";
import { MenuUnreadableScreen } from "@/components/shared/Layout/MenuUnreadableScreen";
import { useMenuAccessGate } from "@/hooks/shared/useMenuAccessGate";
import { resolvePostLoginDestination } from "@/lib/auth/postLoginDestination";
import { useNavStore } from "@/stores/shared/navStore";
import { installViewport, type Viewport } from "@/tests/utils/viewport";

const replace = vi.fn();
let pathname = "/bench";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ replace, push: vi.fn() }),
}));

vi.mock("@/components/shared/Feedback", () => ({ showToast: vi.fn() }));

const fetchNavigation = vi.hoisted(() => vi.fn());
vi.mock("@/services/common/menuService", () => ({ fetchNavigation }));

// 관리 셸이 마운트하자마자 공통코드를 부른다 — 이 그물이 보는 것은 게이트지 코드 조회가 아니다.
vi.mock("@/stores/shared/codeStore", () => ({ useCodeStore: () => ({ getGroupCodes: vi.fn() }) }));

// 관리 셸의 크롬은 배럴(`@/components/shared/Layout`)로 들어오고, 그 배럴은 `fileService →
// env.ts` 까지 끌고 와 테스트 환경에서 env 검증으로 죽는다(#341 ②와 같은 자리). 못 읽었을 때
// 세우지 **않는** 것들이라 여기서는 빈 껍데기로 둔다.
vi.mock("@/components/shared/Layout", () => ({
  Header: () => null,
  Sidebar: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  GlobalTabs: () => null,
}));

/** `/bench` 하나만 열려 있는 정상 네비게이션. */
const NAV_ITEMS = [{ id: "m1", text: "실험대", path: "/bench" }];

/** 메뉴 API 가 500 인 상태 — 스토어가 앉는 자리(`navStore.ts` 의 catch). */
const unreadable = () => useNavStore.setState({ items: [], loaded: true, error: true });

let viewport: Viewport | null = null;

function Probe() {
  const { authorized, denial } = useMenuAccessGate();
  return (
    <>
      <span data-testid="authorized">{String(authorized)}</span>
      <span data-testid="denial">{String(denial)}</span>
    </>
  );
}

/** 제품 셸이 메뉴 행 없이 여는 자리(`/settings`)와 같은 예외 목록. 모듈 상수여야 한다 — 훅 주석 참조. */
const SHELL_ENTRY_PATHS = ["/settings"] as const;
const NO_PREFIX_ALLOWED: readonly string[] = [];

function AlwaysAllowedProbe() {
  const { authorized, denial } = useMenuAccessGate(NO_PREFIX_ALLOWED, SHELL_ENTRY_PATHS);
  return (
    <>
      <span data-testid="authorized">{String(authorized)}</span>
      <span data-testid="denial">{String(denial)}</span>
    </>
  );
}

beforeEach(() => {
  replace.mockClear();
  fetchNavigation.mockReset();
  pathname = "/bench";
  useNavStore.setState({ items: [], loaded: false, error: false });
  viewport ??= installViewport(1440);
});

afterEach(() => {
  cleanup();
  viewport?.restore();
  viewport = null;
});

describe("㉠ 게이트 — 못 읽음과 권한 없음이 다른 출구로 나간다", () => {
  it("못 읽으면 막되 되돌리지 않는다 — 세션은 유효하다", async () => {
    unreadable();
    render(<Probe />);

    await waitFor(() => expect(screen.getByTestId("authorized").textContent).toBe("false"));
    expect(screen.getByTestId("denial").textContent).toBe("unreadable");
    expect(replace, "못 읽었다고 로그인 화면으로 되돌렸다").not.toHaveBeenCalled();
  });

  it("메뉴를 읽었고 그 경로가 없으면 사유를 실어 되돌린다", async () => {
    useNavStore.setState({ items: [{ id: "m1", text: "관심종목", path: "/admin/watchlist" }], loaded: true });
    render(<Probe />);

    await waitFor(() => expect(screen.getByTestId("denial").textContent).toBe("forbidden"));
    expect(replace).toHaveBeenCalledWith("/?reason=forbidden");
  });

  it("못 읽어도 예외 경로는 종전대로 열린다 — fail-closed 의 구멍을 넓히지 않았다", async () => {
    pathname = "/settings";
    unreadable();
    render(<AlwaysAllowedProbe />);

    await waitFor(() => expect(screen.getByTestId("authorized").textContent).toBe("true"));
    expect(screen.getByTestId("denial").textContent).toBe("null");
  });
});

describe("㉡ 제품 셸 — 사유가 화면에 남는다", () => {
  const CHILD = <p data-testid="board">보드 내용</p>;

  it("메뉴 500 이면 셸 안에 사유가 서고 보드는 안 열린다", async () => {
    unreadable();
    render(<ProductLayout>{CHILD}</ProductLayout>);

    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("메뉴를 읽지 못했습니다"));
    expect(screen.queryByTestId("board"), "못 읽었는데 보드가 열렸다").toBeNull();
    expect(screen.getByRole("navigation"), "레일까지 사라지면 앱이 죽은 것으로 보인다").toBeTruthy();
    expect(replace).not.toHaveBeenCalled();
  });

  it("사유는 10초가 지나도 남는다 — 토스트는 2.03초에 사라졌다", async () => {
    unreadable();
    render(<ProductLayout>{CHILD}</ProductLayout>);
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());

    vi.useFakeTimers();
    try {
      act(() => void vi.advanceTimersByTime(10_000));
      expect(screen.getByRole("alert").textContent).toContain("메뉴를 읽지 못했습니다");
    } finally {
      vi.useRealTimers();
    }
  });

  it("화면이 「로그인」도 「관리자에게 문의」도 말하지 않는다", async () => {
    unreadable();
    render(<ProductLayout>{CHILD}</ProductLayout>);

    const text = (await screen.findByRole("alert")).textContent ?? "";
    expect(text).not.toContain("관리자에게 문의");
    expect(text).not.toContain("접근 권한");
    expect(text, "로그인은 유지된다는 사실이 화면에 있어야 한다").toContain("로그인은 그대로 유지");
  });

  it("「다시 시도」가 실제로 다시 읽는다 — 성공하면 사유가 걷히고 보드가 열린다", async () => {
    unreadable();
    fetchNavigation.mockResolvedValue({ items: NAV_ITEMS });
    render(<ProductLayout>{CHILD}</ProductLayout>);
    await screen.findByRole("alert");

    await userEvent.click(screen.getByRole("button", { name: "다시 시도" }));

    await waitFor(() => expect(screen.getByTestId("board")).toBeTruthy());
    expect(fetchNavigation).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("㉡′ 관리 셸 — 같은 게이트를 쓰므로 같은 자리로 간다", () => {
  it("메뉴 500 이면 섀시 대신 사유가 선다 — 되돌리지 않는다", async () => {
    pathname = "/admin/common/system/code";
    unreadable();
    render(
      <AdminLayout>
        <p data-testid="admin-body">관리 화면</p>
      </AdminLayout>,
    );

    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("메뉴를 읽지 못했습니다"));
    expect(screen.queryByTestId("admin-body")).toBeNull();
    expect(replace).not.toHaveBeenCalled();
  });
});

describe("㉢ 로그인 직후 — 「못 읽음」과 「0건」이 다른 문구로 갈린다", () => {
  const unreadableDest = resolvePostLoginDestination({ items: [], error: true });
  const emptyDest = resolvePostLoginDestination({ items: [], error: false });

  it("못 읽었으면 그렇게 말하고, 로그인 화면에 세워 두지 않는다", () => {
    expect(unreadableDest.kind).toBe("menu-unreadable");
    expect(unreadableDest.lines?.join(" ")).toContain("메뉴를 읽지 못했습니다");
    expect(unreadableDest.path, "못 읽음의 출구가 로그인 화면이면 #333 그대로다").toBe("/bench");
  });

  it("진짜로 0건이면 종전대로 계정 상태를 말하고 되돌린다", () => {
    expect(emptyDest.kind).toBe("no-menu");
    expect(emptyDest.path).toBe("/?reason=no-menu");
    expect(emptyDest.lines?.join(" ")).toContain("열려 있는 화면이 없습니다");
  });

  it("두 문구가 서로 다르고, 어느 쪽도 「관리자에게 문의」로 끝나지 않는다", () => {
    const unreadableText = unreadableDest.lines?.join(" ") ?? "";
    const emptyText = emptyDest.lines?.join(" ") ?? "";
    expect(unreadableText.length, "문구가 비었다").toBeGreaterThan(0);
    expect(emptyText.length, "문구가 비었다").toBeGreaterThan(0);
    expect(unreadableText).not.toBe(emptyText);
    for (const text of [unreadableText, emptyText]) {
      expect(text, "로컬 배포판에서 문의할 관리자는 이 화면을 보는 사람 자신이다").not.toContain("관리자에게 문의");
    }
  });

  it("열린 화면이 있으면 그냥 들어간다", () => {
    expect(resolvePostLoginDestination({ items: NAV_ITEMS, error: false })).toEqual({
      kind: "landing",
      path: "/bench",
    });
  });
});

describe("그물이 실제로 무엇을 봤나", () => {
  it("사유 화면이 문장·다음 걸음을 다 갖는다 — 빈 상자가 통과하지 않게", () => {
    render(<MenuUnreadableScreen />);
    const text = screen.getByRole("alert").textContent ?? "";

    // 「사유 · 지금 상태 · 다음 걸음」 셋이 다 있어야 사유 화면이다.
    expect(text).toContain("메뉴를 읽지 못했습니다");
    expect(text).toContain("데이터베이스와 백엔드가 떠 있는지");
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeTruthy();
    expect(text.length, "사유가 한 줄도 없다").toBeGreaterThan(50);
  });
});
