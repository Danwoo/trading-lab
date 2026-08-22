// @vitest-environment jsdom — 관리자 화면을 그대로 렌더해 **화면에 남는 문장**을 읽는다.
//
// https://github.com/Danwoo/trading-lab/issues/332 — 격자가 「못 읽음」을 「총 0건」이라 말했다.
// (파일명·본문의 332 는 이 레포의 이슈다. 코드 주석에 남아 있던 옛 레포 `#332` 와 다르다.)
//
// 실측이었던 것: `/admin/watchlist` 를 ㉠ 연결 거부 ㉡ 정상 200 + 빈 목록으로 각각 열었더니
// **스크린샷 SHA 가 같았다**. 두 진실이 픽셀 단위로 구별되지 않았다. 유일한 신호인 토스트는
// 2초 뒤 사라지고, 그 뒤 화면에 남는 유일한 주장이 거짓인 「총 0건」이었다.
//
// 이 파일은 토스트를 보지 않는다 — **컨테이너만 렌더**하므로 여기서 읽히는 문장은 전부 화면에
// 영구히 남는 것이다. 그래서 "토스트가 사라진 뒤에도 사유가 남는가"가 그대로 단언이 된다.
//
// 사슬: 서비스(`apiCall` → axios) → `useServerTable` → `DataTable`/`DataTableBody`/`DataTablePager`.
// axios 만 갈아끼워 **그 사슬 전체를 실제로 통과**시킨다 — 훅만 두들기면 "그 9개 화면이 정말 이
// 사슬을 타는가"가 다시 검증 밖으로 나간다(#417 테스트와 같은 이유).
//
// 실패 두 갈래를 다 본다:
//   ㉠ 연결 거부 — axios 가 던진다.
//   ㉡ `{success:false}` — `apiCall` 이 `null` 로 돌려준다. 던지지 않으므로 이쪽이 더 조용하다.

import React from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import { LIST_UNREADABLE_TEXT } from "@/components/shared/DataTable/DataTableBody";

// 화면 여럿이 `@/components/shared/ui` 배럴을 타고 services/common/fileService → env.ts 까지
// 끌고 온다(#341 ② 배럴 fan-out — 아직 남은 자리). `.env.development` 를 읽지 않는 CI 에서도
// 실제 화면 코드를 그대로 렌더하려면 이 한 줄이 필요하다.
process.env.NEXT_PUBLIC_FILE_SERVICE_URL ??= "http://localhost:8000";

// ── 응답 주입 ─────────────────────────────────────────────────────────────────
// `apiCall` 은 `axios({...})` 를 그대로 부른다. 여기서 갈아끼우면 서비스·훅·그리드는 전부 실물이다.
type Mode = "dead" | "successFalse" | "empty0";
let mode: Mode = "dead";

/**
 * 죽이는 것은 **목록 요청**이다. 화면이 곁들여 부르는 룩업(상위메뉴·워크스페이스·권한 옵션)은
 * 살려 둔다 — 그 호출부 4곳이 `.catch()` 없이 `.then()` 만 달고 있어서 함께 죽이면 처리되지 않은
 * 거부가 나고, **다른 클래스의 결함이 이 그물의 색을 정하게 된다**(그 4곳은 PR 「발견」에 적었다).
 */
function isLookupRequest(config: { url?: string; params?: Record<string, unknown> }): boolean {
  return String(config?.url ?? "").endsWith("/options") || config?.params?.parent_options !== undefined;
}

vi.mock("axios", () => {
  const request = vi.fn(async (config: { url?: string; params?: Record<string, unknown> }) => {
    if (isLookupRequest(config)) return { data: { items: [], data: [] } };
    if (mode === "dead") throw Object.assign(new Error("Network Error"), { code: "ERR_NETWORK" });
    if (mode === "successFalse") return { data: { success: false } };
    return { data: { items: [], total_count: 0 } };
  });
  return { default: request, isAxiosError: () => false };
});

const EMPTY_TEXT = "표시할 데이터가 없습니다.";
const ZERO_COUNT_TEXT = "총 0건";
const WATCHLIST_EMPTY_TEXT = "관심종목이 없습니다 — 여기에 종목을 등록하면 차트·호가가 그 종목으로 채워집니다.";
const WATCHLIST_UNREADABLE_TEXT = "관심종목을 불러오지 못했습니다 — 잠시 후 다시 시도하세요.";

// jsdom 에는 ResizeObserver 가 없다 — @tanstack/react-virtual 이 마운트 시점에 요구한다.
beforeAll(() => {
  if (!("ResizeObserver" in globalThis)) {
    (globalThis as { ResizeObserver?: unknown }).ResizeObserver = class {
      constructor(private readonly callback: (entries: unknown[]) => void) {}
      observe() {
        this.callback([]);
      }
      unobserve() {}
      disconnect() {}
    };
  }
});

// ── 대상 화면 ─────────────────────────────────────────────────────────────────
// 이슈의 전수 스윕이 `falseEmpty` 로 지목한 관리자 화면 9개 그대로다.
const ADMIN_SCREENS: Array<{ path: string; load: () => Promise<{ default: React.ComponentType<any> }> }> = [
  {
    path: "/admin/common/system/adminuser",
    load: () => import("@/components/features/Common/System/AdminUser/AdminUserContainer"),
  },
  {
    path: "/admin/common/system/author",
    load: () => import("@/components/features/Common/System/Author/AuthorContainer"),
  },
  { path: "/admin/common/system/code", load: () => import("@/components/features/Common/System/Code/CodeContainer") },
  { path: "/admin/common/system/menu", load: () => import("@/components/features/Common/System/Menu/MenuContainer") },
  {
    path: "/admin/common/system/workspace",
    load: () => import("@/components/features/Common/System/Workspace/WorkspaceContainer"),
  },
  { path: "/admin/portfolio", load: () => import("@/components/features/Portfolio/PortfolioContainer") },
  {
    path: "/admin/research-document",
    load: () => import("@/components/features/ResearchDocument/ResearchDocumentContainer"),
  },
  { path: "/admin/scheduler", load: () => import("@/components/features/Scheduler/SchedulerContainer") },
  { path: "/admin/watchlist", load: () => import("@/components/features/Watchlist/WatchlistContainer") },
];

// 「검사 0건은 통과가 아니다」 — 목록이 비거나 줄어들면 이 파일이 조용히 초록이 된다.
const EXPECTED_ADMIN_SCREEN_COUNT = 9;

// 컨테이너를 통째로 렌더하는 파일이라 vitest 기본 5초는 부하 걸린 머신에서 빠듯하다(#417 과 같은 판단).
const RENDER_HEAVY_TIMEOUT_MS = 30_000;

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("#332 — 관리자 격자가 실패를 「총 0건」이라 말하지 않는다", () => {
  it("검사 대상 화면 수가 기대치와 같다 (0건 통과 방지)", () => {
    expect(ADMIN_SCREENS.length).toBe(EXPECTED_ADMIN_SCREEN_COUNT);
    expect(new Set(ADMIN_SCREENS.map((s) => s.path)).size).toBe(EXPECTED_ADMIN_SCREEN_COUNT);
  });

  for (const failureMode of ["dead", "successFalse"] as const) {
    describe(failureMode === "dead" ? "연결 거부" : "{success:false} → null", () => {
      beforeEach(() => {
        mode = failureMode;
      });

      for (const adminScreen of ADMIN_SCREENS) {
        it(
          `${adminScreen.path}: 「없다」고 말하지 않고 못 읽었다고 말한다`,
          async () => {
            const { default: Container } = await adminScreen.load();
            render(<Container />);

            await waitFor(() => expect(screen.getByText(LIST_UNREADABLE_TEXT)).toBeTruthy());
            expect(screen.getByRole("button", { name: "다시 시도" })).toBeTruthy();
            // 못 센 수를 0으로 적지 않는다 — 빈 상태 문구도 총건수도 화면에 없어야 한다.
            expect(screen.queryByText(EMPTY_TEXT)).toBeNull();
            expect(screen.queryByText(ZERO_COUNT_TEXT)).toBeNull();
          },
          RENDER_HEAVY_TIMEOUT_MS,
        );
      }
    });
  }

  it(
    "정상 200 + 빈 목록은 그대로 빈 상태다 — 실패 문구를 쓰지 않는다",
    async () => {
      mode = "empty0";
      const { default: Container } = await ADMIN_SCREENS[8].load(); // /admin/watchlist
      render(<Container />);

      await waitFor(() => expect(screen.getByText(EMPTY_TEXT)).toBeTruthy());
      expect(screen.getByText(ZERO_COUNT_TEXT)).toBeTruthy();
      expect(screen.queryByText(LIST_UNREADABLE_TEXT)).toBeNull();
    },
    RENDER_HEAVY_TIMEOUT_MS,
  );

  // `/terminal` 관심종목 탭도 같은 커널을 탄다 — 여기만 「없다」고 말하면서 **없는 것을 등록하러
  // 가라**고 내밀었다. 옆자리 `HoldingTab` 이 이미 갈라 말하던 그 방식으로 맞춘다.
  describe("/terminal 관심종목 탭", () => {
    for (const failureMode of ["dead", "successFalse"] as const) {
      it(
        `${failureMode}: 「관심종목이 없습니다」도 등록 링크도 내밀지 않는다`,
        async () => {
          mode = failureMode;
          const { WatchlistTab } = await import("@/components/features/Terminal/WatchlistTab");
          render(<WatchlistTab activeTicker={undefined} onSelect={() => {}} />);

          await waitFor(() => expect(screen.getByText(WATCHLIST_UNREADABLE_TEXT)).toBeTruthy());
          expect(screen.queryByText(WATCHLIST_EMPTY_TEXT)).toBeNull();
          expect(screen.queryByRole("link", { name: "관심종목 등록하러 가기" })).toBeNull();
        },
        RENDER_HEAVY_TIMEOUT_MS,
      );
    }

    it(
      "정상 200 + 빈 목록이면 그대로 「없습니다」와 등록 링크다",
      async () => {
        mode = "empty0";
        const { WatchlistTab } = await import("@/components/features/Terminal/WatchlistTab");
        render(<WatchlistTab activeTicker={undefined} onSelect={() => {}} />);

        await waitFor(() => expect(screen.getByText(WATCHLIST_EMPTY_TEXT)).toBeTruthy());
        expect(screen.getByRole("link", { name: "관심종목 등록하러 가기" })).toBeTruthy();
        expect(screen.queryByText(WATCHLIST_UNREADABLE_TEXT)).toBeNull();
      },
      RENDER_HEAVY_TIMEOUT_MS,
    );
  });

  it(
    "죽은 소스와 정상 0건의 화면 텍스트가 갈린다 (스크린샷 SHA 가 같았던 그 자리)",
    async () => {
      mode = "dead";
      const { default: Container } = await ADMIN_SCREENS[8].load();
      const deadRender = render(<Container />);
      await waitFor(() => expect(screen.getByText(LIST_UNREADABLE_TEXT)).toBeTruthy());
      const deadText = deadRender.container.textContent ?? "";
      cleanup();

      mode = "empty0";
      const emptyRender = render(<Container />);
      await waitFor(() => expect(screen.getByText(EMPTY_TEXT)).toBeTruthy());
      const emptyText = emptyRender.container.textContent ?? "";

      expect(deadText).not.toBe(emptyText);
    },
    RENDER_HEAVY_TIMEOUT_MS,
  );
});
