// @vitest-environment jsdom
//
// #333 — **「메뉴를 못 읽음」·「로그아웃됨」·「접근 권한 없음」은 서로 다른 사건이다.**
//
// 실측(이슈 본문): 세션이 유효한데 메뉴 API 가 500 이면 `/bench` 진입 +485ms 에 `/` 로
// 되돌려졌고, 유일한 사유인 토스트가 2.03초 뒤 사라졌다. 남는 것은 로그인 폼 — 로그인돼
// 있는 사람이 로그인 화면을 보고, 도착지는 왜 왔는지 한 글자도 말하지 않았다.
//
// 실측(#335 리뷰, 브라우저 재현): 그 수정이 401 을 같은 바구니에 담아 **방향만 뒤집힌 거짓**을
// 남겼다. 서버 세션 행을 지우고 쿠키 캐시만 걷은 뒤 `/bench` 를 다시 열면 메뉴 API 가 401 을
// 내는데, 화면은 「로그인은 그대로 유지되고 있습니다」라고 말했고 「다시 시도」는 401 을 다시
// 받아 같은 자리에 머물렀다. 제품 셸에 로그아웃이 없어 나갈 길도 없었다.
//
// 여기서 잡는 것은 넷이다.
//   ㉠ 못 읽었을 때 **되돌리지 않는다** (권한 없음의 출구와 갈린다)
//   ㉠′ **401 은 되돌린다** — 사유를 실어 로그인 화면으로. 못 읽음 문구를 쓰지 않는다
//   ㉡ 사유가 **시간이 지나도 화면에 남는다** (2초 토스트가 아니다)
//   ㉢ 「못 읽음」·「로그아웃됨」·「0건」이 **다른 문구**로 갈리고, 「관리자에게 문의」로 끝나지 않는다
//      (로컬 배포판이라 그 관리자가 화면을 보는 사람 자신이다)
//
// **fail-closed** — 아래 두 표(`FAILURE_CASES`·`GATE_CASES`)가 검사 단위다. 각 케이스는 통과할
// 때 자기 이름을 `checked` 에 남기고, 맨 끝 「검사 건수」 블록이 그 수가 표와 일치하는지 + 표가
// 최소 건수를 넘는지 단언하며 **무엇을 몇 건 검사했는지 출력한다.** 표가 비거나 케이스가 조용히
// 빠지면 통과가 아니라 실패다.
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AxiosError, AxiosHeaders } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ProductLayout from "@/app/(main)/layout";
import AdminLayout from "@/app/admin/layout";
import { MenuUnreadableScreen } from "@/components/shared/Layout/MenuUnreadableScreen";
import { useMenuAccessGate, type MenuGateDenial } from "@/hooks/shared/useMenuAccessGate";
import { resolvePostLoginDestination } from "@/lib/auth/postLoginDestination";
import { useNavStore, type NavFailure } from "@/stores/shared/navStore";
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

/** 통과한 케이스 이름. 맨 끝 블록이 이 수를 표와 대조한다 — 케이스가 조용히 빠지면 실패한다. */
const checked = new Set<string>();

/** `/bench` 하나만 열려 있는 정상 네비게이션. */
const NAV_ITEMS = [{ id: "m1", text: "실험대", path: "/bench" }];

/** 화면에 있으면 안 되는 거짓말 — 401 인데 이 문장이 뜨는 것이 이 리뷰가 잡은 결함이다. */
const FALSE_CLAIM = "로그인은 그대로 유지";

const axiosError = (status: number) =>
  new AxiosError("stub", "ERR_BAD_RESPONSE", undefined, undefined, {
    status,
    statusText: "",
    data: {},
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
  });

// ── 표 ①: 던져진 것 → 사유 축. **실제 `navStore.fetchNav` 의 catch 를 태운다** ────────────
interface FailureCase {
  name: string;
  thrown: unknown;
  axis: NavFailure;
  why: string;
}

const FAILURE_CASES: FailureCase[] = [
  {
    name: "401",
    thrown: axiosError(401),
    axis: "unauthenticated",
    why: "서버가 세션을 거부했다 — 정말로 로그아웃이다",
  },
  {
    name: "403",
    thrown: axiosError(403),
    axis: "unreadable",
    why: "인증은 살아 있다 — 「로그인은 유지된다」가 참이다",
  },
  { name: "400", thrown: axiosError(400), axis: "unreadable", why: "요청이 잘못됐을 뿐 세션 이야기가 아니다" },
  { name: "500", thrown: axiosError(500), axis: "unreadable", why: "이 PR 이 원래 겨냥한 갈래" },
  { name: "503", thrown: axiosError(503), axis: "unreadable", why: "백엔드가 안 떠 있다" },
  {
    name: "네트워크 단절 (응답 없음)",
    thrown: new AxiosError("Network Error", "ERR_NETWORK"),
    axis: "unreadable",
    why: "상태 코드가 아예 없다 — 401 로 오인하면 멀쩡한 세션을 끊는다",
  },
  {
    name: "axios 밖의 예외",
    thrown: new TypeError("boom"),
    axis: "unreadable",
    why: "전송 계층 밖에서 터진 것 — 세션 판정 근거가 없다",
  },
];

// ── 표 ②: 스토어 사유 + 경로 → 게이트 판정 ────────────────────────────────────────────
interface GateCase {
  name: string;
  failure: NavFailure;
  path: string;
  /** 예외 목록(`/settings`)을 쓰는 프로브인가 */
  alwaysAllowed: boolean;
  denial: MenuGateDenial | null;
  authorized: boolean;
  redirectedTo: string | null;
  why: string;
}

const GATE_CASES: GateCase[] = [
  {
    name: "401 · 보통 경로",
    failure: "unauthenticated",
    path: "/bench",
    alwaysAllowed: false,
    denial: "unauthenticated",
    authorized: false,
    redirectedTo: "/?reason=session-expired",
    why: "셸에 로그아웃이 없어 여기서 안 되돌리면 갇힌다",
  },
  {
    name: "401 · 예외 경로(/settings)",
    failure: "unauthenticated",
    path: "/settings",
    alwaysAllowed: true,
    denial: "unauthenticated",
    authorized: false,
    redirectedTo: "/?reason=session-expired",
    why: "예외도 봐주지 않는다 — 그 화면의 API 도 같은 401 을 받는다",
  },
  {
    name: "못 읽음 · 보통 경로",
    failure: "unreadable",
    path: "/bench",
    alwaysAllowed: false,
    denial: "unreadable",
    authorized: false,
    redirectedTo: null,
    why: "세션은 끊기지 않았다 — 되돌리면 로그아웃된 것으로 읽힌다",
  },
  {
    name: "못 읽음 · 예외 경로(/settings)",
    failure: "unreadable",
    path: "/settings",
    alwaysAllowed: true,
    denial: null,
    authorized: true,
    redirectedTo: null,
    why: "종전대로 열린다 — fail-closed 의 구멍을 넓히지 않았다",
  },
];

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

/** 메뉴 API 가 500 인 상태 — 스토어가 앉는 자리(`navStore.ts` 의 catch). */
const unreadable = () => useNavStore.setState({ items: [], loaded: true, failure: "unreadable" });
/** 서버가 세션을 거부한 상태(401). */
const unauthenticated = () => useNavStore.setState({ items: [], loaded: true, failure: "unauthenticated" });

beforeEach(() => {
  replace.mockClear();
  fetchNavigation.mockReset();
  pathname = "/bench";
  useNavStore.setState({ items: [], loaded: false, failure: null });
  viewport ??= installViewport(1440);
});

afterEach(() => {
  cleanup();
  viewport?.restore();
  viewport = null;
});

describe("표 ① 스토어 — 던져진 것이 어느 사유 축에 앉나", () => {
  for (const { name, thrown, axis, why } of FAILURE_CASES) {
    it(`${name} → ${axis} (${why})`, async () => {
      fetchNavigation.mockRejectedValue(thrown);
      await useNavStore.getState().fetchNav();

      const state = useNavStore.getState();
      expect(state.loaded, "실패해도 판정은 끝나야 셸이 멈추지 않는다").toBe(true);
      expect(state.failure, `${name} 이 ${axis} 로 안 앉았다`).toBe(axis);
      checked.add(`failure:${name}`);
    });
  }

  it("성공하면 사유가 없다", async () => {
    fetchNavigation.mockResolvedValue({ items: NAV_ITEMS });
    await useNavStore.getState().fetchNav();
    expect(useNavStore.getState().failure).toBeNull();
    expect(useNavStore.getState().items).toEqual(NAV_ITEMS);
  });
});

describe("표 ② 게이트 — 사유마다 다른 출구로 나간다", () => {
  for (const c of GATE_CASES) {
    it(`${c.name} → denial ${String(c.denial)} / ${c.redirectedTo ?? "되돌리지 않음"} (${c.why})`, async () => {
      pathname = c.path;
      useNavStore.setState({ items: [], loaded: true, failure: c.failure });
      render(c.alwaysAllowed ? <AlwaysAllowedProbe /> : <Probe />);

      await waitFor(() => expect(screen.getByTestId("authorized").textContent).toBe(String(c.authorized)));
      expect(screen.getByTestId("denial").textContent).toBe(String(c.denial));
      if (c.redirectedTo === null) {
        expect(replace, `${c.name} 이 되돌려졌다`).not.toHaveBeenCalled();
      } else {
        expect(replace, `${c.name} 이 사유를 실어 되돌리지 않았다`).toHaveBeenCalledWith(c.redirectedTo);
      }
      checked.add(`gate:${c.name}`);
    });
  }

  it("메뉴를 읽었고 그 경로가 없으면 사유를 실어 되돌린다", async () => {
    useNavStore.setState({ items: [{ id: "m1", text: "관심종목", path: "/admin/watchlist" }], loaded: true });
    render(<Probe />);

    await waitFor(() => expect(screen.getByTestId("denial").textContent).toBe("forbidden"));
    expect(replace).toHaveBeenCalledWith("/?reason=forbidden");
  });
});

describe("㉠′ 401 — 못 읽음 문구를 쓰지 않고 나갈 길을 준다", () => {
  it("제품 셸이 사유 화면을 세우지 않고 로그인 화면으로 되돌린다", async () => {
    unauthenticated();
    render(
      <ProductLayout>
        <p data-testid="board">보드 내용</p>
      </ProductLayout>,
    );

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/?reason=session-expired"));
    expect(screen.queryByRole("alert"), "401 인데 「못 읽음」 사유 화면이 섰다").toBeNull();
    expect(screen.queryByTestId("board")).toBeNull();
    expect(document.body.textContent ?? "", "세션이 끊겼는데 유지된다고 말했다").not.toContain(FALSE_CLAIM);
  });

  it("실제 401 응답에서 끝까지 같은 결론이 난다 — 스토어부터 태운다", async () => {
    fetchNavigation.mockRejectedValue(axiosError(401));
    render(
      <ProductLayout>
        <p data-testid="board">보드 내용</p>
      </ProductLayout>,
    );

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/?reason=session-expired"));
    expect(document.body.textContent ?? "").not.toContain(FALSE_CLAIM);
  });

  it("관리 셸도 같은 곳으로 나간다 — 섀시는 서되 사유 화면은 안 선다", async () => {
    pathname = "/admin/common/system/code";
    unauthenticated();
    render(
      <AdminLayout>
        <p data-testid="admin-body">관리 화면</p>
      </AdminLayout>,
    );

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/?reason=session-expired"));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByTestId("admin-body")).toBeNull();
  });
});

describe("㉡ 제품 셸 — 못 읽었을 때 사유가 화면에 남는다", () => {
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
    expect(text, "로그인은 유지된다는 사실이 화면에 있어야 한다").toContain(FALSE_CLAIM);
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

  it("「다시 시도」가 401 을 받으면 그때는 로그인 화면으로 나간다", async () => {
    unreadable();
    fetchNavigation.mockRejectedValue(axiosError(401));
    render(<ProductLayout>{CHILD}</ProductLayout>);
    await screen.findByRole("alert");

    await userEvent.click(screen.getByRole("button", { name: "다시 시도" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/?reason=session-expired"));
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("㉡′ 관리 셸 — 같은 게이트를 쓰므로 같은 자리로 간다", () => {
  beforeEach(() => {
    pathname = "/admin/common/system/code";
  });

  it("메뉴 500 이면 섀시 대신 사유가 선다 — 되돌리지 않는다", async () => {
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

  it("「다시 시도」로 다시 읽는 동안에도 사유가 화면에 남는다 — 빈 화면으로 안 바뀐다", async () => {
    unreadable();
    // 응답을 붙들어 「다시 읽는 중」(`loaded === false`) 구간을 관측 가능하게 만든다.
    let release = () => {};
    fetchNavigation.mockImplementation(
      () =>
        new Promise((resolve) => {
          release = () => resolve({ items: [{ id: "m2", text: "코드", path: pathname }] });
        }),
    );
    render(
      <AdminLayout>
        <p data-testid="admin-body">관리 화면</p>
      </AdminLayout>,
    );
    await screen.findByRole("alert");

    await userEvent.click(screen.getByRole("button", { name: "다시 시도" }));

    await waitFor(() => expect(useNavStore.getState().loaded).toBe(false));
    expect(screen.queryByRole("alert"), "다시 읽는 동안 사유 화면이 걷혔다").not.toBeNull();

    // 관리 셸의 본문은 iframe 탭이라 `children` 을 그리지 않는다 — 재조회 성공의 관측점은
    // 사유 화면이 걷히고 섀시가 서는 것이다.
    await act(async () => {
      release();
    });
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    expect(replace, "재조회가 성공했는데 되돌렸다").not.toHaveBeenCalled();
  });
});

describe("㉢ 로그인 직후 — 사유마다 다른 문구로 갈린다", () => {
  const unreadableDest = resolvePostLoginDestination({ items: [], failure: "unreadable" });
  const expiredDest = resolvePostLoginDestination({ items: [], failure: "unauthenticated" });
  const emptyDest = resolvePostLoginDestination({ items: [], failure: null });

  it("못 읽었으면 그렇게 말하고, 로그인 화면에 세워 두지 않는다", () => {
    expect(unreadableDest.kind).toBe("menu-unreadable");
    expect(unreadableDest.lines?.join(" ")).toContain("메뉴를 읽지 못했습니다");
    expect(unreadableDest.path, "못 읽음의 출구가 로그인 화면이면 #333 그대로다").toBe("/bench");
  });

  it("서버가 세션을 거부했으면 제품 안으로 들여보내지 않는다", () => {
    expect(expiredDest.kind).toBe("session-expired");
    expect(expiredDest.path).toBe("/?reason=session-expired");
    expect(expiredDest.lines?.join(" ")).toContain("세션을 받지 않았습니다");
    expect(expiredDest.lines?.join(" "), "0건이라고 오진하면 #333 이 방향만 바뀐 채 남는다").not.toContain(
      "열려 있는 화면이 없습니다",
    );
  });

  it("진짜로 0건이면 종전대로 계정 상태를 말하고 되돌린다", () => {
    expect(emptyDest.kind).toBe("no-menu");
    expect(emptyDest.path).toBe("/?reason=no-menu");
    expect(emptyDest.lines?.join(" ")).toContain("열려 있는 화면이 없습니다");
  });

  it("세 문구가 서로 다르고, 어느 것도 「관리자에게 문의」로 끝나지 않는다", () => {
    const texts = [unreadableDest, expiredDest, emptyDest].map((d) => d.lines?.join(" ") ?? "");
    for (const text of texts) {
      expect(text.length, "문구가 비었다").toBeGreaterThan(0);
      expect(text, "로컬 배포판에서 문의할 관리자는 이 화면을 보는 사람 자신이다").not.toContain("관리자에게 문의");
    }
    expect(new Set(texts).size, "사유가 다른데 같은 문구를 쓴다").toBe(texts.length);
  });

  it("열린 화면이 있으면 그냥 들어간다", () => {
    expect(resolvePostLoginDestination({ items: NAV_ITEMS, failure: null })).toEqual({
      kind: "landing",
      path: "/bench",
    });
  });
});

describe("검사 건수 (fail-closed)", () => {
  it("사유 화면이 문장·다음 걸음을 다 갖는다 — 빈 상자가 통과하지 않게", () => {
    render(<MenuUnreadableScreen />);
    const text = screen.getByRole("alert").textContent ?? "";

    // 「사유 · 지금 상태 · 다음 걸음」 셋이 다 있어야 사유 화면이다.
    expect(text).toContain("메뉴를 읽지 못했습니다");
    expect(text).toContain("데이터베이스와 백엔드가 떠 있는지");
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeTruthy();
    expect(text.length, "사유가 한 줄도 없다").toBeGreaterThan(50);
  });

  // 제목에 건수를 박는다 — 기본 리포터는 통과한 테스트의 `console.log` 를 안 보여주므로,
  // 「몇 건을 봤나」가 출력에 남으려면 이름에 있어야 한다(`--reporter=verbose`·CI 목록).
  it(`표 ${FAILURE_CASES.length + GATE_CASES.length}건을 전수 실행했다 — 사유분류 ${FAILURE_CASES.length}건(401 ${
    FAILURE_CASES.filter((c) => c.axis === "unauthenticated").length
  } / 그 밖 ${FAILURE_CASES.filter((c) => c.axis === "unreadable").length}) + 게이트 판정 ${GATE_CASES.length}건`, () => {
    // 표 자체가 비면 위 루프가 0회 돌고도 초록이 된다 — 최소 건수를 못박는다.
    expect(FAILURE_CASES.length, "사유 분류 표가 비었다").toBeGreaterThanOrEqual(7);
    expect(GATE_CASES.length, "게이트 판정 표가 비었다").toBeGreaterThanOrEqual(4);

    // 두 축 모두 한쪽으로 쏠리면 대조가 안 된다 — 축마다 최소 1건씩 있어야 한다.
    for (const axis of ["unauthenticated", "unreadable"] as const) {
      expect(FAILURE_CASES.filter((c) => c.axis === axis).length, `${axis} 케이스가 0건이다`).toBeGreaterThan(0);
      expect(GATE_CASES.filter((c) => c.failure === axis).length, `${axis} 게이트 케이스가 0건이다`).toBeGreaterThan(0);
    }
    expect(GATE_CASES.filter((c) => c.redirectedTo !== null).length, "되돌리는 케이스가 0건이다").toBeGreaterThan(0);
    expect(GATE_CASES.filter((c) => c.redirectedTo === null).length, "안 되돌리는 케이스가 0건이다").toBeGreaterThan(0);

    // 표에 있는데 안 돈 케이스가 있으면 여기서 드러난다.
    const expected = [...FAILURE_CASES.map((c) => `failure:${c.name}`), ...GATE_CASES.map((c) => `gate:${c.name}`)];
    const missed = expected.filter((name) => !checked.has(name));
    expect(missed, `표에 있는데 안 돈 케이스: ${missed.join(", ")}`).toEqual([]);
  });
});
