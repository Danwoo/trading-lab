// @vitest-environment jsdom
//
// #434 (B-31) — 같은 폼의 두 문자 칸이 길이를 다르게 다뤘다.
//
//   이름 600자 : 칸에 600자가 그대로 남고, 저장할 때 「최대 100자」라고 말한다 → 고칠 수 있다
//   설명 600자 : `maxlength="500"` 이라 501번째부터 입력이 그냥 사라졌다 → 붙여넣기로 긴 글을
//                넣으면 **잘린 줄 모른 채** 저장되고, 저장은 성공했다고 뜬다
//
// 길이 규칙은 이미 zod 에 있다(`bot_desc` max_length 500). `maxlength` 는 그 문구를 가로채
// 조용히 자르기만 했다. 그것을 걷어내 이름 칸과 같은 동작으로 만든 것이 이 회귀의 대상이다.
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

function givenBot() {
  vi.mocked(selectStrategyCatalog).mockResolvedValue({ items: [FORM], errors: [] } as never);
  vi.mocked(selectBot).mockResolvedValue({
    bot_id: 7,
    bot_nm: "눌림목 봇",
    bot_desc: "",
    bot_role: "SIGNAL",
    use_at: "Y",
    reg_dt: "2026-08-01T09:00:00",
    reg_id: "lead",
    mod_dt: "2026-08-01T09:00:00",
    mod_id: "lead",
    strategies: [
      {
        bot_strategy_id: 1,
        strategy_key: "pullback",
        params: { period: 20 },
        param_sources: { period: "USER" },
        weight: null,
        sort_order: 1,
        form: FORM,
        missing_reason: null,
      },
    ],
  } as never);
}

describe("설명 칸이 말없이 자르지 않는다", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("한도를 넘겨 붙여넣어도 글자가 사라지지 않는다", async () => {
    givenBot();
    render(<BotWorkbench botId={7} />);
    await screen.findByDisplayValue("눌림목 봇");

    const long = "가".repeat(600);
    const desc = screen.getByLabelText("설명") as HTMLTextAreaElement;
    expect(desc).toBeTruthy();

    const user = userEvent.setup();
    await user.click(desc!);
    await user.paste(long);

    // maxlength 가 남아 있으면 여기서 500 이 된다 — 사용자는 100자를 잃고도 모른다.
    await waitFor(() => expect(desc!.value.length).toBe(600));
  });

  it("한도를 넘긴 채 저장하면 조용히 성공하지 않는다 — 저장 경로가 거절한다", async () => {
    // 검증은 서비스 함수 안에 있다(`validateWithZod`). 잘라 주지 않게 된 이상,
    // 한도를 넘긴 값이 조용히 통과하지 않는지는 그 경로를 직접 겨눠야 확인된다.
    const { BotUpdateInSchema } = await import("@/schemas/bot/bot");
    const { validateWithZod } = await import("@/lib/zod/validation");

    const payload = {
      bot_nm: "눌림목 봇",
      bot_desc: "가".repeat(600),
      combine_rule: "AND",
      universe_kind: "POOL",
      bot_role: "READONLY",
      use_at: "Y",
      param_sources: {},
      strategies: [{ strategy_key: "pullback", params: { period: 20 }, param_sources: { period: "USER" } }],
    };

    expect(() => validateWithZod(BotUpdateInSchema, payload)).toThrow();
    // 500자까지는 종전대로 통과한다 — 막는 범위가 넓어지지 않았다.
    expect(() => validateWithZod(BotUpdateInSchema, { ...payload, bot_desc: "가".repeat(500) })).not.toThrow();
  });
});
