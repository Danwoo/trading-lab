// @vitest-environment jsdom
//
// #424 ② — **로그인된 사람이 루트(`/`)에 오면 로그인 폼을 다시 보지 않는다.**
//
// 실측(이슈 본문): 세션이 살아 있는데(`get-session` 200 + user, 2초 간격 9회) `/` 에는
// 마케팅 랜딩과 로그인 폼이 18초 동안 그대로 서 있었다. 다시 로그인하면 들어가므로 차단이
// 아니라 마찰이지만, 화면은 로그아웃된 것처럼 보이고 실험대로 가는 길이 어디에도 없었다.
//
// 여기서 잡는 것 넷:
//   ㉠ 세션이 있으면 **실험대로 보낸다**
//   ㉡ 세션이 없으면 **종전대로 랜딩** — 리다이렉트가 비로그인 방문자를 건드리지 않는다
//   ㉢ 되돌아온 사유를 달고 온 세션은 **보내지 않는다** — 셸이 방금 여기로 되돌린 사람을
//      그 자리로 다시 밀면 왕복이 된다(`useMenuAccessGate` ↔ 이 리다이렉트)
//   ㉣ 그때도 **길은 화면에 남는다** — 「실험대로 가기」. 단 열린 메뉴가 0건이라 되돌아온
//      경우(`no-menu`)는 그 길이 없으므로 내걸지 않는다
//
// **검증 경계** — 세션은 `useSession` 대역이다. 서버가 세션을 실제로 어떻게 판정하는지,
// 리다이렉트 뒤 실험대가 무엇을 그리는지는 보지 않는다.

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Login } from "@/components/features/Common/Auth/Login";
import { BENCH_PATH } from "@/constants/routes";

const replace = vi.hoisted(() => vi.fn());
const searchParams = vi.hoisted(() => ({ current: new URLSearchParams() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  useSearchParams: () => searchParams.current,
}));

const session = vi.hoisted(() => ({ data: null as unknown, isPending: false }));
vi.mock("@/lib/auth/auth-client", () => ({
  authClient: {},
  signIn: { email: vi.fn() },
  signOut: vi.fn(),
  getSession: vi.fn(async () => null),
  useSession: () => ({ ...session, error: null, refetch: vi.fn() }),
}));

vi.mock("@/components/features/Common/Policy/PolicyPopup", () => ({ default: () => null }));
vi.mock("@/stores/shared/messageStore", () => ({ showMessage: vi.fn(async () => true) }));

const LOGGED_IN = { user: { id: "u1", email: "someone@example.com" } };
const BENCH_LINK = "실험대로 가기";

describe("#424 ② 로그인된 사람이 루트에서 로그인 폼을 다시 보지 않는다", () => {
  beforeEach(() => {
    replace.mockClear();
    searchParams.current = new URLSearchParams();
    session.data = null;
    session.isPending = false;
  });

  afterEach(cleanup);

  it("세션이 있으면 실험대로 보낸다", async () => {
    session.data = LOGGED_IN;

    render(<Login />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith(BENCH_PATH));
  });

  it("세션이 있으면 실험대로 가는 길이 화면에 있다", async () => {
    session.data = LOGGED_IN;

    render(<Login />);

    expect(screen.getByRole("link", { name: BENCH_LINK }).getAttribute("href")).toBe(BENCH_PATH);
  });

  it("비로그인은 종전대로 랜딩 — 아무 데로도 보내지 않는다", async () => {
    session.data = null;

    render(<Login />);

    expect(screen.getByRole("heading", { name: "로그인" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: BENCH_LINK })).toBeNull();
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(replace).not.toHaveBeenCalled();
  });

  it("세션 판정 전(isPending)에는 보내지 않는다", async () => {
    session.data = null;
    session.isPending = true;

    render(<Login />);

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(replace).not.toHaveBeenCalled();
  });

  it("사유를 달고 되돌아온 세션은 다시 밀지 않는다 — 왕복 방지", async () => {
    session.data = LOGGED_IN;
    searchParams.current = new URLSearchParams("reason=forbidden");

    render(<Login />);

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(replace).not.toHaveBeenCalled();
    // 사유는 그대로 남고, 실험대로 가는 길은 화면에 있다.
    expect(screen.getByRole("status").textContent).toContain("접근 권한이 없어");
    expect(screen.getByRole("link", { name: BENCH_LINK })).toBeTruthy();
  });

  it("열린 메뉴가 0건이라 되돌아온 경우는 실험대 링크를 내걸지 않는다", async () => {
    session.data = LOGGED_IN;
    searchParams.current = new URLSearchParams("reason=no-menu");

    render(<Login />);

    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(replace).not.toHaveBeenCalled();
    expect(screen.queryByRole("link", { name: BENCH_LINK })).toBeNull();
  });
});
