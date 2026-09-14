// @vitest-environment jsdom
//
// F18 — 백엔드(#345)가 「평균선 기간」: 5일~120일 범위여야 합니다 (받은 값 3일) 로 칸을 짚어
// 답하는데, 화면은 그 문장을 토스트로 잠깐 띄우고 끝났다(실측: 4초 뒤 잔존 0, 칸의
// aria-invalid null). 폼이 열 칸이 넘어 토스트가 사라지면 어디를 고칠지 남는 것이 없다.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { BotWorkbench } from "@/components/features/Bot/BotWorkbench";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/services/bot/botService", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/services/bot/botService")>();
  return { ...actual, selectStrategyCatalog: vi.fn(), createBot: vi.fn() };
});
vi.mock("@/services/bot/botAgentService", () => ({
  selectBotAgentReadiness: vi.fn().mockResolvedValue({ ready: false, reasons: [], strategies_dir: "/s" }),
  streamBotAgent: vi.fn(),
}));

const { selectStrategyCatalog, createBot } = await import("@/services/bot/botService");

beforeAll(() => {
  Element.prototype.scrollTo = () => {};
});

const FORM = {
  key: "ma_pullback",
  name: "이동평균 눌림목",
  summary: null,
  timeframe: "1d",
  fields: [
    { name: "ma_period", label: "평균선 기간", control: "number" as const, default: 20, unit: "일" },
    { name: "pullback_pct", label: "눌림 깊이", control: "number" as const, default: 3 },
  ],
};

const SERVER_MESSAGE = "「평균선 기간」: 5일~120일 범위여야 합니다 (받은 값 3일)";

/** `apiCall` 이 던지는 axios 오류의 모양 — `getApiErrorMessage` 가 `detail` 문자열을 그대로 낸다. */
function rejectedByServer(detail: string) {
  return Object.assign(new Error(detail), { response: { status: 400, data: { detail } } });
}

async function openNewBotForm() {
  vi.mocked(selectStrategyCatalog).mockResolvedValue({ items: [FORM], errors: [] } as never);
  render(<BotWorkbench />);
  await screen.findByLabelText("평균선 기간");
}

describe("F18 서버가 짚은 칸에 오류가 남는다", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("저장이 라벨 오류로 실패하면 그 칸이 aria-invalid 가 되고 문장이 칸에 붙는다", async () => {
    await openNewBotForm();
    vi.mocked(createBot).mockRejectedValue(rejectedByServer(SERVER_MESSAGE));
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("이름"), "c5 F18");
    await user.click(screen.getByRole("button", { name: "저장" }));

    const input = screen.getByLabelText("평균선 기간");
    await waitFor(() => expect(input.getAttribute("aria-invalid")).toBe("true"));
    const described = (input.getAttribute("aria-describedby") ?? "")
      .split(/\s+/)
      .filter(Boolean)
      .map((id) => document.getElementById(id)?.textContent ?? "")
      .join(" ");
    expect(described).toContain("5일~120일 범위여야 합니다");
    // 다른 칸은 멀쩡하다 — 엉뚱한 칸까지 빨갛게 하지 않는다.
    expect(screen.getByLabelText("눌림 깊이").getAttribute("aria-invalid")).toBeNull();
  });

  it("그 칸을 다시 손대면 오류가 지워진다 — 옛 오류가 새 값 위에 남지 않는다", async () => {
    await openNewBotForm();
    vi.mocked(createBot).mockRejectedValue(rejectedByServer(SERVER_MESSAGE));
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("이름"), "c5 F18");
    await user.click(screen.getByRole("button", { name: "저장" }));
    const input = screen.getByLabelText("평균선 기간");
    await waitFor(() => expect(input.getAttribute("aria-invalid")).toBe("true"));

    await user.clear(input);
    await user.type(input, "20");

    await waitFor(() => expect(input.getAttribute("aria-invalid")).toBeNull());
  });

  it("라벨을 안 짚은 오류는 어느 칸도 빨갛게 하지 않는다", async () => {
    await openNewBotForm();
    vi.mocked(createBot).mockRejectedValue(rejectedByServer("같은 이름의 봇이 있습니다"));
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("이름"), "c5 F18");
    await user.click(screen.getByRole("button", { name: "저장" }));

    await waitFor(() => expect(createBot).toHaveBeenCalled());
    expect(document.querySelectorAll("[aria-invalid='true']").length).toBe(0);
  });
});
