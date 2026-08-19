// @vitest-environment jsdom
//
// 봇 폼의 입력칸이 **접근 가능한 이름**을 갖는가 (#259).
//
// 눈에는 「이름」·「평균선 기간」이 또렷이 붙어 있었지만 그것이 `<span>` 이라, 보조기술에는
// 이름 없는 칸이었고 라벨을 눌러도 포커스가 안 갔다. 폼 전체에 `<label>` 이 **0개**였다.
//
// 이 그물은 **개수를 센다** — 「이 칸 하나가 라벨을 가졌나」가 아니라 「이름 없는 칸이 0개인가」다.
// 칸이 늘어도 따라오게 하려면 그래야 한다. 검사한 칸 수를 함께 낸다(0이면 실패).
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";

import { BotWorkbench } from "@/components/features/Bot/BotWorkbench";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/services/bot/botAgentService", () => ({
  selectBotAgentReadiness: vi.fn().mockResolvedValue({ ready: false, reasons: [], strategies_dir: "/s" }),
  streamBotAgent: vi.fn(),
}));

/** 전략 하나가 세 종류 컨트롤(숫자·선택·토글)을 다 내게 한다 — 셋 다 라벨이 붙어야 한다.
 *  `vi.mock` 은 끌어올려지므로 카탈로그도 `vi.hoisted` 로 함께 올린다. */
const CATALOG = vi.hoisted(() => ({
  items: [
    {
      key: "ma_pullback",
      name: "이동평균 눌림목",
      summary: "평균선 아래로 눌린 종목이 다시 평균선을 되찾을 때 산다",
      timeframe: "1d",
      fields: [
        { name: "ma_period", label: "평균선 기간", control: "number", default: 20, help: "길수록 큰 흐름만 본다." },
        { name: "mode", label: "판정 방식", control: "select", default: "a", items: ["a", "b"] },
        { name: "recover_confirm", label: "회복 확인", control: "toggle", default: true },
      ],
    },
  ],
  errors: [],
}));

vi.mock("@/services/bot/botService", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/services/bot/botService")>();
  return { ...actual, selectStrategyCatalog: vi.fn() };
});

const { selectStrategyCatalog } = await import("@/services/bot/botService");

beforeAll(() => {
  Element.prototype.scrollTo = () => {};
});

/** 브라우저가 이름을 계산하는 것과 같은 순서로 본다 — placeholder 는 이름이 아니다. */
function accessibleName(element: Element): string {
  const byFor = element.id ? document.querySelector(`label[for="${CSS.escape(element.id)}"]`) : null;
  const wrapping = element.closest("label");
  const labelledBy = (element.getAttribute("aria-labelledby") ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .map((id) => document.getElementById(id)?.textContent ?? "")
    .join(" ");
  // `??` 를 쓰면 빈 문자열에서 사슬이 끊긴다 — 「aria-labelledby 가 없음」이 `""` 라
  // 뒤의 `<label for>` 를 영영 안 본다. 실제로 그 실수로 9칸을 「이름 없음」으로 오판했다.
  return (
    element.getAttribute("aria-label") ||
    labelledBy ||
    byFor?.textContent ||
    wrapping?.textContent ||
    element.getAttribute("title") ||
    ""
  ).trim();
}

describe("봇 폼의 입력칸은 이름을 갖는다", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("이름 없는 입력칸이 0개다 — 전략 파라미터 칸(숫자·선택·토글)까지", async () => {
    vi.mocked(selectStrategyCatalog).mockResolvedValue(CATALOG as never);
    const { container } = render(<BotWorkbench />);
    // 전략을 고르면 선언대로 칸이 생긴다 — 그 칸들까지 세야 의미가 있다
    await waitFor(() => expect(container.querySelector('input[type="number"]')).not.toBeNull());

    const controls = [...container.querySelectorAll("input, textarea, select")];
    expect(controls.length).toBeGreaterThan(0); // fail-closed — 0개면 아무것도 안 본 것이다

    const unnamed = controls.filter((element) => accessibleName(element) === "");
    expect({
      검사한칸: controls.length,
      이름없는칸: unnamed.map((e) => `${e.tagName}/${(e as HTMLInputElement).type}`),
    }).toEqual({ 검사한칸: controls.length, 이름없는칸: [] });
  });

  it("라벨은 `<label for>` 로 컨트롤을 가리킨다 — 눌러서 포커스가 가야 한다", async () => {
    vi.mocked(selectStrategyCatalog).mockResolvedValue(CATALOG as never);
    const { container } = render(<BotWorkbench />);
    await waitFor(() => expect(container.querySelector('input[type="number"]')).not.toBeNull());

    const labels = [...container.querySelectorAll("label[for]")];
    expect(labels.length).toBeGreaterThan(0);

    const dangling = labels.filter((label) => document.getElementById(label.getAttribute("for") ?? "") === null);
    expect(dangling.map((l) => l.textContent)).toEqual([]);
  });
});
