// @vitest-environment jsdom
//
// #315 회귀 그물 — **화면 조작만으로 봇을 지울 수 있다.**
//
// 삭제는 백엔드 라우터·프론트 프록시·서비스 함수까지 다 있었는데 그것을 부르는 화면만 없었다
// (`grep -rn deleteBot frontend` 가 `botService.ts` 하나만 냈다). 소비자가 없다는 것은 타입도
// 린트도 빌드도 통과시키므로, 조작부가 다시 사라지면 잡을 것이 이 파일밖에 없다.
//
// 확인 단계는 **실물로** 돌린다 — `showMessage` 를 모킹해 버리면 「확인 없이 지운다」는 회귀가
// 그대로 통과한다. `messageStore` 와 `MessagePopup` 을 그대로 쓰고, jsdom 에서 관측이 안 되는
// Radix 포털만 스텁으로 바꾼다 (`MessagePopup.test.tsx` 와 같은 경계).
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { BotList } from "@/components/features/Bot/BotList";
import { BotWorkbench } from "@/components/features/Bot/BotWorkbench";
import { MessagePopup } from "@/components/shared/Feedback/MessagePopup";
import { useMessageStore } from "@/stores/shared/messageStore";

vi.mock("@/components/shared/ui/Popup", () => ({
  Popup: ({ visible, title, children }: { visible: boolean; title?: string; children?: React.ReactNode }) =>
    visible ? (
      <div data-testid="popup">
        <h2>{title}</h2>
        {children}
      </div>
    ) : null,
}));

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: (...args: unknown[]) => push(...args) }) }));

vi.mock("@/services/bot/botService", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/services/bot/botService")>();
  return {
    ...actual,
    selectBotList: vi.fn(),
    selectBot: vi.fn(),
    selectStrategyCatalog: vi.fn(),
    deleteBot: vi.fn(),
  };
});
vi.mock("@/services/bot/botAgentService", () => ({
  selectBotAgentReadiness: vi.fn().mockResolvedValue({ ready: false, reasons: [], strategies_dir: "/s" }),
  streamBotAgent: vi.fn(),
}));
vi.mock("@/services/backtest/backtestService", () => ({
  selectBacktestRunsByBot: vi.fn().mockResolvedValue({ items: [], total_count: 0 }),
}));

const { selectBotList, selectBot, selectStrategyCatalog, deleteBot } = await import("@/services/bot/botService");

beforeAll(() => {
  Element.prototype.scrollTo = () => {};
});

const FORM = {
  key: "pullback",
  name: "눌림목",
  fields: [{ name: "period", label: "기간", control: "number" as const, default: 20 }],
};

function givenBots(names: [number, string][]) {
  vi.mocked(selectBotList).mockResolvedValue({
    items: names.map(([bot_id, bot_nm]) => ({
      bot_id,
      bot_nm,
      bot_role: "READONLY",
      use_at: "Y",
    })),
    total_count: names.length,
  } as never);
}

function givenBotDetail(botId: number, name: string) {
  vi.mocked(selectStrategyCatalog).mockResolvedValue({ items: [FORM], errors: [] } as never);
  vi.mocked(selectBot).mockResolvedValue({
    bot_id: botId,
    bot_nm: name,
    bot_desc: "",
    bot_role: "READONLY",
    use_at: "Y",
    strategies: [
      {
        bot_strategy_id: 1,
        strategy_key: "pullback",
        params: { period: 20 },
        param_sources: {},
        weight: null,
        sort_order: 0,
        form: FORM,
        missing_reason: null,
      },
    ],
  } as never);
}

beforeEach(() => {
  useMessageStore.setState({ messages: [], currentMessage: null });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  useMessageStore.setState({ messages: [], currentMessage: null });
});

describe("내 봇 목록에서 지운다 (#315)", () => {
  it("행마다 삭제가 있고, 확인을 누르면 그 봇만 지워지고 목록에서 사라진다", async () => {
    const user = userEvent.setup();
    givenBots([
      [4, "S1 검증용 봇"],
      [5, "남겨둘 봇"],
    ]);
    vi.mocked(deleteBot).mockResolvedValue({ message: "삭제가 완료되었습니다." } as never);

    render(
      <>
        <BotList />
        <MessagePopup />
      </>,
    );

    await user.click(await screen.findByRole("button", { name: "S1 검증용 봇 삭제" }));

    // 확인이 먼저다 — 이 시점에 서버로 나갔으면 「되돌릴 수 없는 동작에 확인」이 깨진 것이다.
    await screen.findByTestId("popup");
    expect(vi.mocked(deleteBot)).not.toHaveBeenCalled();

    // 행의 버튼 이름은 「<봇 이름> 삭제」라, 정확히 「삭제」인 것은 팝업의 확인 버튼뿐이다.
    await user.click(screen.getByRole("button", { name: "삭제" }));

    await waitFor(() => expect(vi.mocked(deleteBot)).toHaveBeenCalledWith(4));
    await waitFor(() => expect(screen.queryByText("S1 검증용 봇")).toBeNull());
    // 지운 봇만 빠진다 — 목록 전체가 날아가면 지운 뒤 화면이 빈 것으로 오인된다.
    expect(screen.getByText("남겨둘 봇")).toBeTruthy();
  });

  it("확인 문구가 함께 사라지는 것과 남는 것을 갈라 말한다", async () => {
    const user = userEvent.setup();
    givenBots([[4, "S1 검증용 봇"]]);

    render(
      <>
        <BotList />
        <MessagePopup />
      </>,
    );

    await user.click(await screen.findByRole("button", { name: "S1 검증용 봇 삭제" }));
    await screen.findByTestId("popup");

    expect(screen.getByText(/되돌릴 수 없습니다/)).toBeTruthy();
    expect(screen.getByText(/실린 전략과 그 설정이 함께 지워집니다/)).toBeTruthy();
    // 검증 기록은 FK 가 없어 지워지지 않는다 — 「함께 지워진다」로 뭉치면 문구가 거짓이 된다.
    expect(screen.getByText(/검증 기록은 남지만/)).toBeTruthy();
  });

  it("취소하면 서버로 나가지 않고 목록이 그대로다", async () => {
    const user = userEvent.setup();
    givenBots([[4, "S1 검증용 봇"]]);

    render(
      <>
        <BotList />
        <MessagePopup />
      </>,
    );

    await user.click(await screen.findByRole("button", { name: "S1 검증용 봇 삭제" }));
    await screen.findByTestId("popup");
    await user.click(screen.getByRole("button", { name: "취소" }));

    await waitFor(() => expect(useMessageStore.getState().currentMessage).toBeNull());
    expect(vi.mocked(deleteBot)).not.toHaveBeenCalled();
    expect(screen.getByText("S1 검증용 봇")).toBeTruthy();
  });
});

describe("봇 고치기에서 지운다 (#315)", () => {
  it("저장된 봇에는 삭제가 서고, 지운 뒤 목록으로 돌아간다", async () => {
    const user = userEvent.setup();
    givenBotDetail(4, "S1 검증용 봇");
    vi.mocked(deleteBot).mockResolvedValue({ message: "삭제가 완료되었습니다." } as never);

    render(
      <>
        <BotWorkbench botId={4} />
        <MessagePopup />
      </>,
    );
    await screen.findByDisplayValue("S1 검증용 봇");

    // 폼의 이름을 고쳐 두고 지운다 — 확인창이 말해야 하는 것은 **저장된** 봇이지 타이핑 중인
    // 이름이 아니다.
    const nameBox = screen.getByDisplayValue("S1 검증용 봇");
    await user.clear(nameBox);
    await user.type(nameBox, "아직 저장 안 한 이름");

    await user.click(screen.getByRole("button", { name: "삭제" }));
    await screen.findByTestId("popup");
    expect(screen.getByText(/「S1 검증용 봇」 봇을 지웁니다/)).toBeTruthy();
    // 팝업의 확인 버튼도 「삭제」다 — 뒤에 뜬 쪽(팝업)을 집는다.
    const confirmButtons = screen.getAllByRole("button", { name: "삭제" });
    await user.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => expect(vi.mocked(deleteBot)).toHaveBeenCalledWith(4));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/bench/bot"));
  });

  it("새 봇 만들기에는 삭제가 서지 않는다 — 지울 대상이 없다", async () => {
    vi.mocked(selectStrategyCatalog).mockResolvedValue({ items: [FORM], errors: [] } as never);

    render(<BotWorkbench />);
    await screen.findByRole("button", { name: "저장" });

    expect(screen.queryByRole("button", { name: "삭제" })).toBeNull();
  });

  // 지운 뒤 뒤로가기로 그 주소에 되돌아오면 봇은 없는데 화면은 열린다. 삭제가 그대로 서 있으면
  // 확인창이 이름 없는 봇(「」)을 지운다고 말하고, 404 가 뻔한 요청이 나간다 (실측 #315).
  it("없는 봇의 주소에서는 삭제가 서지 않는다", async () => {
    vi.mocked(selectStrategyCatalog).mockResolvedValue({ items: [FORM], errors: [] } as never);
    vi.mocked(selectBot).mockRejectedValue(new Error("데이터를 찾을 수 없습니다."));

    render(<BotWorkbench botId={3} />);
    await screen.findByRole("button", { name: "저장" });

    expect(screen.queryByRole("button", { name: "삭제" })).toBeNull();
    expect(screen.getByText(/데이터를 찾을 수 없습니다/)).toBeTruthy();
  });
});
