// @vitest-environment jsdom
//
// 미디어쿼리(`sm:`·`lg:`)는 **뷰포트**를 본다 — 컨테이너가 아니다. 그래서 넓은 화면에서
// 372px 패널 안에 작업대를 넣으면 `lg:` 가 켜져 대화와 폼이 나란히 서고, `sm:` 이 켜져
// 라벨이 폭을 다 가져간다. 실제로 그렇게 깨졌다(글자가 한 자씩 끊기고 컨트롤이 「관 ▼」로 잘림).
//
// 컨테이너 쿼리를 쓸 수 있으면 그게 답이지만 이 레포의 Tailwind 3.4 에는 그 플러그인이 없다.
// 그래서 **폭을 재는 대신 구조 사실**(패널 안인가)로 가른다. 이 그물은 그 배선이 사라지는 것을 막는다.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import { BotWorkbench } from "@/components/features/Bot/BotWorkbench";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/services/bot/botService", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/services/bot/botService")>();
  return { ...actual, selectStrategyCatalog: vi.fn().mockResolvedValue({ items: [], errors: [] }) };
});
vi.mock("@/services/bot/botAgentService", () => ({
  selectBotAgentReadiness: vi.fn().mockResolvedValue({ ready: false, reasons: [], strategies_dir: "/s" }),
  streamBotAgent: vi.fn(),
}));

beforeAll(() => {
  Element.prototype.scrollTo = () => {};
});

/** 대화·폼을 담는 격자 — 작업대 본문의 바로 그 상자. 카탈로그를 받아야 그려진다. */
async function bodyGrid(container: HTMLElement): Promise<HTMLElement> {
  return waitFor(() => {
    const grid = container.querySelector<HTMLElement>("div.grid.min-h-0");
    if (grid === null) throw new Error("본문 격자가 아직 없다");
    return grid;
  });
}

describe("작업대가 패널 안에 들어가면 한 단으로 쌓인다", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("패널 안에서는 뷰포트 브레이크포인트로 두 단이 되지 않는다", async () => {
    const { container } = render(<BotWorkbench inPanel />);

    const grid = await bodyGrid(container);
    expect(grid.className).toContain("grid-cols-1");
    expect(grid.className).not.toContain("lg:grid-cols-");
  });

  it("페이지에서는 넓을 때 두 단으로 간다", async () => {
    const { container } = render(<BotWorkbench />);

    expect((await bodyGrid(container)).className).toContain("lg:grid-cols-");
  });

  it("패널 안에서는 폼 한 줄도 라벨을 위로 올린다", async () => {
    const { container } = render(<BotWorkbench inPanel />);

    await bodyGrid(container);
    const rows = container.querySelectorAll<HTMLElement>("[data-row]");
    expect(rows.length).toBeGreaterThan(0);
    // 좁은 자리 표식은 조상에 달린다 — 자손 선택자가 `sm:` 격자를 덮는다.
    expect(container.querySelector("[class*='data-row']")).not.toBeNull();
  });

  it("패널 안에서는 페이지 제목을 두 번 세우지 않는다", async () => {
    render(<BotWorkbench inPanel />);

    expect(screen.queryByRole("heading", { name: /봇 만들기|봇 고치기/ })).toBeNull();
  });
});
