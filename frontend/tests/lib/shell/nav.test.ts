import { describe, expect, it } from "vitest";
import {
  collectNavPaths,
  findFirstNavPath,
  findNavByPath,
  matchesPath,
  selectAdminNavItems,
  type NavItem,
} from "@/lib/shell/nav";

/** 실제 시드가 만드는 모양 — 대분류 둘, 그 아래 제품 경로와 관리 경로가 섞여 있다. */
const tree: NavItem[] = [
  {
    id: "mbiz0000",
    text: "업무관리",
    items: [
      { id: "mbiz1009", text: "실험대", path: "/bench" },
      { id: "mbiz1008", text: "시세", path: "/terminal" },
      { id: "mbiz1001", text: "관심종목", path: "/admin/watchlist" },
    ],
  },
  {
    id: "msys0000",
    text: "시스템관리",
    items: [{ id: "msys1001", text: "코드관리", path: "/admin/common/system/code" }],
  },
];

describe("matchesPath", () => {
  it("정확히 같으면 맞다", () => {
    expect(matchesPath("/admin", "/admin")).toBe(true);
  });

  it("슬래시 경계로만 시작을 인정한다 — /admin/foobar 는 /admin/foo 가 아니다", () => {
    expect(matchesPath("/admin/foo/bar", "/admin/foo")).toBe(true);
    expect(matchesPath("/admin/foobar", "/admin/foo")).toBe(false);
  });
});

describe("collectNavPaths", () => {
  it("트리 전체의 경로를 평평하게 모은다", () => {
    expect(collectNavPaths(tree)).toEqual(["/bench", "/terminal", "/admin/watchlist", "/admin/common/system/code"]);
  });

  it("빈 트리는 빈 목록 — 게이트가 fail-closed 로 동작하는 근거다", () => {
    expect(collectNavPaths([])).toEqual([]);
  });
});

describe("selectAdminNavItems", () => {
  it("제품 경로를 잘라낸다 — 관리 셸의 iframe 탭으로 열리면 안 되는 것들", () => {
    const admin = selectAdminNavItems(tree);
    expect(collectNavPaths(admin)).toEqual(["/admin/watchlist", "/admin/common/system/code"]);
  });

  it("부모는 살리되 잎이 하나도 안 남으면 함께 사라진다", () => {
    const productOnly: NavItem[] = [
      { id: "p", text: "업무관리", items: [{ id: "b", text: "실험대", path: "/bench" }] },
    ];
    expect(selectAdminNavItems(productOnly)).toEqual([]);
  });

  it("원본을 바꾸지 않는다", () => {
    const before = JSON.stringify(tree);
    selectAdminNavItems(tree);
    expect(JSON.stringify(tree)).toBe(before);
  });

  it("`/administration` 처럼 접두어만 같은 경로는 관리 경로가 아니다", () => {
    const trap: NavItem[] = [{ id: "t", text: "덫", path: "/administration" }];
    expect(selectAdminNavItems(trap)).toEqual([]);
  });
});

describe("findNavByPath / findFirstNavPath", () => {
  it("경로로 잎을 찾는다", () => {
    expect(findNavByPath(tree, "/terminal")?.text).toBe("시세");
    expect(findNavByPath(tree, "/없는경로")).toBeNull();
  });

  it("앞에서부터 처음 만나는 경로를 준다 — 착지점 폴백", () => {
    expect(findFirstNavPath(tree)).toBe("/bench");
    expect(findFirstNavPath([])).toBeNull();
  });
});
