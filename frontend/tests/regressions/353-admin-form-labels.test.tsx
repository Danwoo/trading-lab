// @vitest-environment jsdom — 관리자 폼 9개를 그대로 렌더해 **입력칸의 이름을 센다**.
//
// https://github.com/Danwoo/trading-lab/issues/353 — 라벨이 옆 칸의 글자로만 있어, 눌러도
// 포커스가 안 가고 스크린 리더는 「편집 텍스트」라고만 읽었다. 실측 37칸 중 31칸이 그랬다.
//
// 세는 것은 **개수 하나**다: 보이는 입력칸 중 접근 가능한 이름이 없는 것. 이름이 어떤 경로로
// 붙었는지(`label[for]`·`aria-label`·감싼 라벨)는 따지지 않는다 — 방식을 박아 두면 다음 사람이
// 다른 옳은 방식을 쓸 때 이 그물이 틀린 빨간불을 낸다.
//
// **fail-closed 두 겹**: 검사한 폼 수가 기대치와 다르면 실패하고, 입력칸을 한 칸도 못 찾아도
// 실패한다. 폼이 사라지거나 렌더가 조용히 죽으면 「위반 0건」이 아니라 빨간불이 된다.

import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";

// 화면 여럿이 `@/components/shared/ui` 배럴을 타고 env.ts 까지 끌고 온다 — CI 에는 .env 가 없다.
process.env.NEXT_PUBLIC_FILE_SERVICE_URL ??= "http://localhost:8000";

vi.mock("axios", () => {
  const request = vi.fn(async () => ({ data: { items: [], data: [], total_count: 0 } }));
  return { default: request, isAxiosError: () => false };
});

const ADMIN_FORMS: Array<{ path: string; load: () => Promise<{ default?: unknown; [key: string]: unknown }> }> = [
  {
    path: "/admin/common/system/adminuser",
    load: () => import("@/components/features/Common/System/AdminUser/AdminUserDetailForm"),
  },
  {
    path: "/admin/common/system/author",
    load: () => import("@/components/features/Common/System/Author/AuthorDetailForm"),
  },
  { path: "/admin/common/system/code", load: () => import("@/components/features/Common/System/Code/CodeDetailForm") },
  { path: "/admin/common/system/menu", load: () => import("@/components/features/Common/System/Menu/MenuDetailForm") },
  {
    path: "/admin/common/system/workspace",
    load: () => import("@/components/features/Common/System/Workspace/WorkspaceDetailForm"),
  },
  { path: "/admin/portfolio", load: () => import("@/components/features/Portfolio/PortfolioDetailForm") },
  {
    path: "/admin/research-document",
    load: () => import("@/components/features/ResearchDocument/ResearchDocumentDetailForm"),
  },
  { path: "/admin/scheduler", load: () => import("@/components/features/Scheduler/SchedulerDetailForm") },
  { path: "/admin/watchlist", load: () => import("@/components/features/Watchlist/WatchlistDetailForm") },
];

/** 「검사 0건은 통과가 아니다」 — 목록이 줄면 이 파일이 조용히 초록이 된다. */
const EXPECTED_FORM_COUNT = 9;

/** 폼 하나에 최소 이만큼은 있어야 한다 — 렌더가 반쯤 죽어 칸이 사라진 것을 통과로 읽지 않게. */
const MIN_INPUTS_PER_FORM = 1;

/** 폼을 통째로 렌더하는 파일이라 vitest 기본 5초는 부하 걸린 머신에서 빠듯하다 (`332-…` 과 같은 판단). */
const RENDER_HEAVY_TIMEOUT_MS = 30_000;

/** 격자 필터·파일 첨부는 이 폼의 라벨 규율 밖이다 (이슈의 전수 조사와 같은 제외 기준). */
function isCountedField(field: HTMLInputElement | HTMLTextAreaElement): boolean {
  if (field.type === "hidden" || field.type === "file") return false;
  const hint = `${field.getAttribute("aria-label") ?? ""} ${field.getAttribute("placeholder") ?? ""}`;
  return !/필터|검색|표시 개수/.test(hint);
}

/** 브라우저가 계산하는 이름을 흉내낸다 — `aria-label` → `label[for]` → `aria-labelledby` → 감싼 라벨. */
function accessibleName(field: HTMLInputElement | HTMLTextAreaElement): string {
  const aria = field.getAttribute("aria-label")?.trim();
  if (aria) return aria;
  if (field.id) {
    const bound = document.querySelector(`label[for="${CSS.escape(field.id)}"]`);
    if (bound?.textContent?.trim()) return bound.textContent.trim();
  }
  if (field.getAttribute("aria-labelledby")) return "aria-labelledby";
  if (field.closest("label")?.textContent?.trim()) return field.closest("label")!.textContent!.trim();
  return "";
}

/**
 * 코드 목록 자리. 어느 키를 물어도 빈 배열을 준다 — 폼마다 다른 키를 쓰는데, 안 주면
 * `SelectMenu` 가 `items.length` 에서 죽는다(그 취약함 자체는 이 이슈의 범위 밖이다).
 */
const EMPTY_CODE_LIST = new Proxy({}, { get: () => [] });

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("#353 — 관리자 폼 입력칸이 이름을 갖는다", () => {
  it("검사 대상 폼 수가 기대치와 같다 (0건 통과 방지)", () => {
    expect(ADMIN_FORMS.length).toBe(EXPECTED_FORM_COUNT);
    expect(new Set(ADMIN_FORMS.map((form) => form.path)).size).toBe(EXPECTED_FORM_COUNT);
  });

  for (const adminForm of ADMIN_FORMS) {
    it(
      `${adminForm.path}: 이름 없는 입력칸이 0개다`,
      async () => {
        const module = await adminForm.load();
        const Form = (module.default ??
          Object.values(module).find((value) => typeof value === "function")) as React.ComponentType<any>;
        render(
          <Form isNew initialData={{}} onSubmit={async () => true} onCancel={() => {}} codeList={EMPTY_CODE_LIST} />,
        );

        const fields = [...document.body.querySelectorAll("input, textarea")].filter(
          (node): node is HTMLInputElement | HTMLTextAreaElement =>
            node instanceof HTMLInputElement || node instanceof HTMLTextAreaElement,
        );
        const counted = fields.filter(isCountedField);
        expect(counted.length).toBeGreaterThanOrEqual(MIN_INPUTS_PER_FORM);

        const unnamed = counted.filter((field) => accessibleName(field) === "");
        expect(unnamed.map((field) => `${field.tagName.toLowerCase()}[${field.type}]`)).toEqual([]);
      },
      RENDER_HEAVY_TIMEOUT_MS,
    );
  }
});
