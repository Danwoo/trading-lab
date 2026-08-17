// @vitest-environment jsdom
//
// **셸은 인가 응답을 기다리지 않는다.** 종전에는 레이아웃이 통째로 `return null` 이라
// 레일 46px 까지 화면 전체가 백지였다 — `loaded` 를 켜는 것은 클라이언트 이펙트의 메뉴 조회
// 하나뿐이라 그 왕복 내내 아무것도 안 보인다. 마일스톤 2 수용 첫 칸(기동 → 로그인 →
// 실험대가 열림)이 그 백지를 지난다.
//
// 여기서 지키는 것은 둘이다: ㉠ 판정 전에도 골조가 있다 ㉡ **판정 전에 내용이 새지 않는다**.
// ㉡ 이 없으면 「골조를 먼저 그린다」가 「권한 없는 사람에게 화면을 보여준다」가 된다.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import Layout from "@/app/(main)/layout";

const gate = vi.hoisted(() => ({ value: { loaded: false, authorized: null as boolean | null } }));

vi.mock("next/navigation", () => ({
  usePathname: () => "/bench",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));
vi.mock("@/hooks/shared/useMenuAccessGate", () => ({ useMenuAccessGate: () => gate.value }));
vi.mock("@/hooks/shared/usePanelOverlaysBoard", () => ({ usePanelOverlaysBoard: () => false }));

function given(next: { loaded: boolean; authorized: boolean | null }) {
  gate.value = next;
}

const CHILD = <p data-testid="board">보드 내용</p>;

describe("제품 셸 — 인가 응답 전에도 골조가 선다", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("아직 못 읽었을 때도 레일이 보인다 — 백지가 아니다", () => {
    given({ loaded: false, authorized: null });
    render(<Layout>{CHILD}</Layout>);

    // 레일은 §20 의 46px 항해 장치다. 이것이 없으면 사용자는 앱이 죽은 줄 안다.
    expect(screen.getByRole("navigation")).toBeTruthy();
    expect(screen.getByRole("main")).toBeTruthy();
  });

  it("판정 전에는 내용이 새지 않는다", () => {
    given({ loaded: false, authorized: null });
    render(<Layout>{CHILD}</Layout>);

    expect(screen.queryByTestId("board")).toBeNull();
  });

  it("인가되지 않은 사용자에게도 내용이 새지 않는다", () => {
    given({ loaded: true, authorized: false });
    render(<Layout>{CHILD}</Layout>);

    expect(screen.getByRole("navigation")).toBeTruthy();
    expect(screen.queryByTestId("board")).toBeNull();
  });

  it("인가되면 내용이 뜬다", () => {
    given({ loaded: true, authorized: true });
    render(<Layout>{CHILD}</Layout>);

    expect(screen.getByTestId("board")).toBeTruthy();
  });
});
