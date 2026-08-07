// @vitest-environment jsdom — 실제 화면 컴포넌트를 렌더해 어떤 행이 DOM 에 나오는지 읽는다.
//
// PR #417 독립 리뷰 차단급 ① — `showPaging={false} clientSidePaging={true}` 인 디테일 그리드
// 7곳에서 **16행째부터 도달할 방법이 사라졌다**.
//
// 사슬: `useDetailGridData`(pageSize = PAGE_SIZE.DETAIL = 15) → `DetailGridPanel`
// (`paginate: !clientSidePaging`) → `useServerTable` clientSide 모드 → `applyClientQuery` 가
// `slice(skip, skip+15)` 로 로컬 절단 → `DetailGrid` 가 `showPager={showPaging}` → `DataTable`
// 이 페이저를 아예 안 그림. 에러도 빈 상태도 아니고 **조용히 잘린 목록**이라 사용자가 알아챌
// 수단이 없었다.
//
// 이관 전에는 `showPaging=false` 가 `<Paging>`/`<Pager>` JSX 만 생략했고, DevExtreme 의
// `pager visible: "auto"` 기본값이 한 페이지를 넘으면 페이저를 띄웠다 — 즉 **base 에서는 도달
// 가능했다**. 수정은 그 기본값을 커널에 되살린다: `DataTable` 이 `totalCount > pageSize` 면
// `showPager` 와 무관하게 페이저를 그린다.
//
// 이 테스트는 커널을 직접 두들기지 않고 **7개 화면 컴포넌트를 그대로 렌더**한다 — 커널만
// 검증하면 "그 7곳이 정말 이 설정을 쓰는가"가 다시 검증 밖으로 나가기 때문이다. 각 화면의
// 서비스 모듈만 20행짜리 응답으로 갈아끼운다.
//
// 배치: 단일 소스 파일이 아니라 화면 7개 + 패널 + 커널을 관통하는 회귀라 tests/regressions/ 에 둔다.

import React from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// jsdom 은 레이아웃을 계산하지 않아 모든 요소의 rect 가 0 이고 ResizeObserver 도 없다.
// `@tanstack/react-virtual` 은 그 상태에서 "보이는 행 0개"로 판단해 `<tbody>` 를 비운 채 두므로,
// 폴리필 없이는 행 텍스트를 하나도 읽을 수 없다(가상 스크롤 자체는 이 테스트의 관심사가 아니다).
// 스크롤 컨테이너에 실제 높이를 주고 관찰자를 한 번 발화시켜, 커널이 **현재 페이지에 준 행**을
// 그대로 DOM 에 그리게 한다.
const VIEWPORT_HEIGHT_PX = 800;
const ROW_HEIGHT_PX = 33; // DataTable 의 ESTIMATED_ROW_HEIGHT_PX 와 같은 값 — 15행이 한 화면에 다 들어간다.

beforeAll(() => {
  if (!("ResizeObserver" in globalThis)) {
    (globalThis as { ResizeObserver?: unknown }).ResizeObserver = class {
      constructor(private readonly callback: (entries: unknown[]) => void) {}
      observe() {
        // 관찰자는 entries 배열을 받는다 — 비워서 부르면 virtual-core 가 스스로
        // getBoundingClientRect 로 되돌아간다(위에서 그 값을 실제 높이로 채워 뒀다).
        this.callback([]);
      }
      unobserve() {}
      disconnect() {}
    };
  }
  // virtual-core 는 스크롤 컨테이너 크기를 `offsetWidth`/`offsetHeight` 로 읽는다
  // (getBoundingClientRect 가 아니다 — 실측으로 확인). jsdom 은 둘 다 항상 0 이라
  // "뷰포트 0px = 그릴 행 0개"가 된다.
  // 같은 속성으로 스크롤 컨테이너 높이와 **행 높이**를 둘 다 읽으므로(measureElement) 태그로
  // 가른다 — 행까지 800px 로 보고하면 한 화면에 한두 줄만 들어가 15행을 다 못 읽는다.
  Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
    configurable: true,
    get(this: HTMLElement) {
      return this.tagName === "TR" ? ROW_HEIGHT_PX : VIEWPORT_HEIGHT_PX;
    },
  });
  Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
    configurable: true,
    get: () => 1000,
  });
});

// 화면 3곳(AdminUserSessionGrid·AdminUserAuthorGrid·MenuAuthorGrid)이 `@/components/shared/ui`
// 배럴에서 Button/SelectBox 를 가져오는데, 그 배럴은 FileListDisplay → services/common/fileService
// → env.ts 까지 끌고 온다(#341 ② 배럴 fan-out — 아직 남은 자리). jsdom 에는 window 가 있어
// @t3-oss/env-nextjs 는 클라이언트 변수만 검증하므로 이 한 줄이면 실제 화면 코드를 그대로
// 렌더할 수 있다. `.env.development` 를 읽지 않는 CI 에서도 같다.
process.env.NEXT_PUBLIC_FILE_SERVICE_URL ??= "http://localhost:8000";

const ROW_COUNT = 20; // PAGE_SIZE.DETAIL(15) 을 넘긴다 — 16~20행이 2페이지로 밀린다.
const FIRST_ROW_MARK = "항목-01";
const LAST_FIRST_PAGE_MARK = "항목-15";
const OVERFLOW_ROW_MARK = "항목-16"; // 이 텍스트에 도달할 수 있는가가 이 파일의 전부다.

/** `항목-01` … `항목-20` 라벨. 1-based, 두 자리 고정 — `항목-1` 이 `항목-16` 에 부분매칭하지 않게. */
function labels(): string[] {
  return Array.from({ length: ROW_COUNT }, (_, i) => `항목-${String(i + 1).padStart(2, "0")}`);
}

// ── 서비스 모킹 ────────────────────────────────────────────────────────────────
// 화면마다 응답 모양이 달라 각자 만든다. 공통점은 하나 — 20건을 돌려준다.
vi.mock("@/services/common/authorService", () => ({
  selectAuthorUsers: vi.fn(async () => ({
    authorUsers: labels().map((label) => ({
      user_id: label,
      user_nm: label,
      workspace_nm: "ws",
      use_at: "Y",
      appr_at: "Y",
    })),
  })),
  selectAuthorMenus: vi.fn(async () => ({
    authorMenus: labels().map((label) => ({ menu_id: label, menu: { menu_nm: label, use_at: "Y" } })),
  })),
  selectAuthorOptions: vi.fn(async () => ({ items: [] })),
}));

vi.mock("@/services/common/workspaceService", () => ({
  selectWorkspaceMenus: vi.fn(async () => ({
    workspaceMenus: labels().map((label) => ({ menu_id: label, menu: { menu_nm: label, use_at: "Y" }, reg_dt: null })),
  })),
}));

vi.mock("@/services/common/adminUserService", () => ({
  selectUserAuthors: vi.fn(async () => ({
    items: labels().map((label) => ({ author_id: label, author_nm: label })),
  })),
  selectUserSessions: vi.fn(async () => ({
    items: labels().map((label, index) => ({
      id: label,
      rn: index + 1,
      createdAt: null,
      expiresAt: null,
      ipAddress: "127.0.0.1",
      userAgent: label,
    })),
  })),
  revokeUserSession: vi.fn(async () => ({ message: "" })),
}));

vi.mock("@/services/common/menuService", () => ({
  selectMenuAuthors: vi.fn(async () => ({
    items: labels().map((label) => ({ author_id: label, author_nm: label })),
  })),
  addMenuAuthor: vi.fn(async () => ({ message: "" })),
  removeMenuAuthor: vi.fn(async () => ({ message: "" })),
}));

vi.mock("@/services/scheduler/schedulerService", () => ({
  selectSchedulerMembers: vi.fn(async () => ({
    items: labels().map((label) => ({ git_id: label, name: label, email: `${label}@example.com` })),
  })),
}));

// ── 대상 7곳 ───────────────────────────────────────────────────────────────────
// 전부 `showPaging={false} clientSidePaging={true}` — 리뷰가 지목한 그 목록 그대로다.
const SCREENS: Array<{
  name: string;
  load: () => Promise<{ default: React.ComponentType<any> }>;
  props: Record<string, unknown>;
}> = [
  {
    name: "AuthorUserGrid",
    load: () => import("@/components/features/Common/System/Author/AuthorUserGrid"),
    props: { authorId: "AUTH1" },
  },
  {
    name: "AuthorMenuGrid",
    load: () => import("@/components/features/Common/System/Author/AuthorMenuGrid"),
    props: { authorId: "AUTH1" },
  },
  {
    name: "WorkspaceMenuGrid",
    load: () => import("@/components/features/Common/System/Workspace/WorkspaceMenuGrid"),
    props: { workspaceId: 1 },
  },
  {
    name: "AdminUserSessionGrid",
    load: () => import("@/components/features/Common/System/AdminUser/AdminUserSessionGrid"),
    props: { email: "a@b.c" },
  },
  {
    name: "AdminUserAuthorGrid",
    load: () => import("@/components/features/Common/System/AdminUser/AdminUserAuthorGrid"),
    props: { email: "a@b.c" },
  },
  {
    name: "MenuAuthorGrid",
    load: () => import("@/components/features/Common/System/Menu/MenuAuthorGrid"),
    props: { menuId: "M1" },
  },
  {
    name: "SchedulerMemberGrid",
    load: () => import("@/components/features/Scheduler/SchedulerMemberGrid"),
    props: { schedulerId: "S1" },
  },
];

afterEach(() => {
  cleanup();
});

// **타임아웃 상한 주의**: 이 파일은 화면 컴포넌트 7개를 jsdom 에 통째로 렌더한다 — vitest 기본
// 5초는 CI·병렬 실행처럼 부하가 걸린 머신에서 빠듯하다(워커 2개가 독립적으로 각 2회 관측,
// 단독 실행은 항상 통과). 느린 것을 감추는 게 아니라 **정당하게 무거운 테스트에 맞는 상한**을
// 준다 — 실패 원인이 "회귀"인지 "머신이 바빴다"인지 구분되지 않으면 그물이 신호를 잃는다.
const RENDER_HEAVY_TIMEOUT_MS = 30_000;

describe("#417 — clientSidePaging + showPaging=false 그리드에서 16행째 도달 가능성", () => {
  for (const screenDef of SCREENS) {
    it(
      `${screenDef.name}: 20행을 넣으면 페이저가 뜨고 16행째에 도달한다`,
      async () => {
        const user = userEvent.setup();
        const { default: Component } = await screenDef.load();
        render(<Component {...screenDef.props} />);

        // 1페이지 — 15행까지만 보인다(커널이 자르는 것 자체는 정상 동작).
        await waitFor(() => expect(screen.getAllByText(FIRST_ROW_MARK).length).toBeGreaterThan(0));
        expect(screen.getAllByText(LAST_FIRST_PAGE_MARK).length).toBeGreaterThan(0);
        expect(screen.queryByText(OVERFLOW_ROW_MARK)).toBeNull();

        // 페이저가 있어야 한다 — `showPaging={false}` 지만 잘리고 있으므로.
        // 이 단정이 수정 전에는 실패했다(페이저 자체가 렌더되지 않았다).
        const nextButton = screen.getByRole("button", { name: "다음 페이지" });
        expect(screen.getByText(`총 ${ROW_COUNT}건`)).toBeTruthy();
        expect(screen.getByText("1 / 2")).toBeTruthy();

        // 2페이지 — 16행째가 실제로 나온다.
        await user.click(nextButton);
        await waitFor(() => expect(screen.getAllByText(OVERFLOW_ROW_MARK).length).toBeGreaterThan(0));
        expect(screen.getByText("2 / 2")).toBeTruthy();
      },
      RENDER_HEAVY_TIMEOUT_MS,
    );
  }

  it(
    "한 페이지에 다 들어가면 페이저는 여전히 숨는다 — showPaging=false 의 원래 뜻",
    async () => {
      const { selectSchedulerMembers } = await import("@/services/scheduler/schedulerService");
      vi.mocked(selectSchedulerMembers).mockResolvedValueOnce({
        items: labels()
          .slice(0, 10)
          .map((label) => ({ git_id: label, name: label, email: `${label}@example.com` })),
      } as never);

      const { default: SchedulerMemberGrid } = await import("@/components/features/Scheduler/SchedulerMemberGrid");
      render(<SchedulerMemberGrid schedulerId="S1" />);

      await waitFor(() => expect(screen.getAllByText(FIRST_ROW_MARK).length).toBeGreaterThan(0));
      expect(screen.queryByRole("button", { name: "다음 페이지" })).toBeNull();
    },
    RENDER_HEAVY_TIMEOUT_MS,
  );
});
