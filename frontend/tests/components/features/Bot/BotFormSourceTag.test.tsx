// @vitest-environment jsdom
//
// 설정 한 줄의 출처 꼬리표가 **세 갈래 다 사람 말**인가 (#319).
//
// 셋 중 둘은 「내가 정함」·「AI 제안 수락」인데 나머지 하나만 「선언 기본값」이었다 — 「선언」은
// 전략 파일의 코드 어휘라, 셋을 나란히 읽으면 층이 어긋난다. 화면에 그려진 텍스트로 판정한다:
// 상수를 비교하면 문구를 바꿔도 그대로 통과한다.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";

import { BotWorkbench } from "@/components/features/Bot/BotWorkbench";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/services/bot/botAgentService", () => ({
  selectBotAgentReadiness: vi.fn().mockResolvedValue({ ready: false, reasons: [], strategies_dir: "/s" }),
  streamBotAgent: vi.fn(),
}));

const CATALOG = vi.hoisted(() => ({
  items: [
    {
      key: "ma_pullback",
      name: "이동평균 눌림목",
      summary: "평균선 아래로 눌린 종목이 다시 평균선을 되찾을 때 산다",
      timeframe: "1d",
      fields: [{ name: "ma_period", label: "평균선 기간", control: "number", default: 20, min: 5, max: 60 }],
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

describe("봇 폼의 출처 꼬리표는 사람 말이다", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("손대지 않은 전략 설정은 「기본값 그대로」로 읽히고, 화면에 「선언」이 없다", async () => {
    vi.mocked(selectStrategyCatalog).mockResolvedValue(CATALOG as never);
    const { container } = render(<BotWorkbench />);
    await waitFor(() => expect(container.querySelector('input[type="number"]')).not.toBeNull());

    const shown = container.textContent ?? "";
    expect(shown.length).toBeGreaterThan(0); // fail-closed — 빈 화면을 통과로 세지 않는다
    expect(shown).toContain("기본값 그대로");
    expect(shown).not.toContain("선언");
  });
});
