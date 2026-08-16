// @vitest-environment jsdom
//
// 이 화면은 전략을 하나만 다루는데, 저장은 전략 배열을 **통째로 갈아 끼운다**
// (백엔드 `_replace_strategies` 가 `DELETE … WHERE bot_id` 후 받은 배열만 다시 넣는다).
// 그래서 전략이 여럿인 봇을 열어 아무것도 안 고치고 「저장」만 눌러도 나머지가 조용히 사라진다.
//
// 「이 화면에서 여러 전략을 못 고친다」는 계획대로다. **「부순다」가 문제다** — 그 하나만 막는다.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { BotWorkbench } from "@/components/features/Bot/BotWorkbench";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/services/bot/botService", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/services/bot/botService")>();
  return { ...actual, selectStrategyCatalog: vi.fn(), selectBot: vi.fn(), updateBot: vi.fn() };
});
vi.mock("@/services/bot/botAgentService", () => ({
  selectBotAgentReadiness: vi.fn().mockResolvedValue({ ready: false, reasons: [], strategies_dir: "/s" }),
  streamBotAgent: vi.fn(),
}));

const { selectStrategyCatalog, selectBot, updateBot } = await import("@/services/bot/botService");

beforeAll(() => {
  Element.prototype.scrollTo = () => {};
});

const FORM = {
  key: "pullback",
  name: "눌림목",
  fields: [{ name: "period", label: "기간", control: "number" as const, default: 20 }],
};

function strategyOf(key: string, order: number) {
  return {
    bot_strategy_id: order,
    strategy_key: key,
    params: { period: 20 },
    param_sources: { period: "USER" },
    weight: null,
    sort_order: order,
    form: FORM,
    missing_reason: null,
  };
}

function givenBot(strategyKeys: string[]) {
  vi.mocked(selectStrategyCatalog).mockResolvedValue({ items: [FORM], errors: [] } as never);
  vi.mocked(selectBot).mockResolvedValue({
    bot_id: 7,
    bot_nm: "다전략 봇",
    bot_desc: "",
    bot_role: "SIGNAL",
    use_at: "Y",
    reg_dt: "2026-08-01T09:00:00",
    reg_id: "lead",
    mod_dt: "2026-08-01T09:00:00",
    mod_id: "lead",
    strategies: strategyKeys.map(strategyOf),
  } as never);
}

describe("다전략 봇을 이 화면이 부수지 않는다", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("전략이 여럿이면 열자마자 이유를 보여준다", async () => {
    givenBot(["pullback", "breakout", "meanrev"]);

    render(<BotWorkbench botId={7} />);

    expect(await screen.findByText(/전략이 3개 실려 있는데/)).toBeTruthy();
  });

  it("전략이 여럿이면 저장해도 서버로 안 보낸다 — 나머지가 지워지는 것을 막는다", async () => {
    givenBot(["pullback", "breakout"]);

    render(<BotWorkbench botId={7} />);
    await screen.findByText(/전략이 2개 실려 있는데/);

    await userEvent.setup().click(screen.getByRole("button", { name: "저장" }));

    await waitFor(() => expect(vi.mocked(updateBot)).not.toHaveBeenCalled());
  });

  it("전략이 하나면 종전대로 저장된다 — 막는 범위가 넓어지지 않았다", async () => {
    givenBot(["pullback"]);
    vi.mocked(updateBot).mockResolvedValue({ bot_id: 7 } as never);

    render(<BotWorkbench botId={7} />);
    await screen.findByDisplayValue("다전략 봇");

    await userEvent.setup().click(screen.getByRole("button", { name: "저장" }));

    await waitFor(() => expect(vi.mocked(updateBot)).toHaveBeenCalledTimes(1));
    // 보낸 payload 의 전략은 정확히 하나다 — 이 화면이 다루는 범위 그대로.
    expect(vi.mocked(updateBot).mock.calls[0][1].strategies).toHaveLength(1);
  });
});
