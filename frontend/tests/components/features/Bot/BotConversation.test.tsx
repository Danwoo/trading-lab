// @vitest-environment jsdom
//
// 스트림이 시작된 **뒤** 난 실패는 예외로 오지 않는다 — 서버가 `{type:"error"}` 이벤트로 보낸다
// (`StreamingResponse` 가 이미 헤더를 보낸 뒤라 표준 예외 핸들러가 못 잡는다). 그래서 `catch`
// 블록만으로는 이 경로가 안 잡히고, 프론트가 이 타입을 무시하면 **실패가 빈 턴으로 사라진다.**
// 여기서 지키는 것은 그 하나다 — 실패가 화면에 실패로 남는가.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { BotConversation } from "@/components/features/Bot/BotConversation";
import type { BotAgentEvent } from "@/services/bot/botAgentService";

vi.mock("@/services/bot/botAgentService", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/services/bot/botAgentService")>();
  return { ...actual, streamBotAgent: vi.fn(), selectBotAgentReadiness: vi.fn() };
});

const { streamBotAgent, selectBotAgentReadiness } = await import("@/services/bot/botAgentService");

/** 지정한 이벤트들을 순서대로 흘려보내는 스트림 한 벌. */
function streamOf(...events: BotAgentEvent[]) {
  return async (_message: string, onEvent: (e: BotAgentEvent) => void) => {
    for (const event of events) onEvent(event);
  };
}

async function send(text: string) {
  const user = userEvent.setup();
  await user.type(screen.getByRole("textbox"), text);
  await user.click(screen.getByRole("button", { name: /보내기/ }));
}

// jsdom 은 `Element.scrollTo` 를 구현하지 않는다 — 대화 로그가 매 턴 바닥으로 내리는 코드가 이걸 쓴다.
beforeAll(() => {
  Element.prototype.scrollTo = () => {};
});

describe("BotConversation — 스트림 중 실패가 사라지지 않는다", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("`error` 이벤트의 사유가 화면에 남는다", async () => {
    vi.mocked(selectBotAgentReadiness).mockResolvedValue({ ready: true, reasons: [], strategies_dir: "/strategies" });
    vi.mocked(streamBotAgent).mockImplementation(
      streamOf({ type: "text", text: "생각하는 중" }, { type: "error", message: "에이전트 호출이 한도를 넘었습니다" }),
    );

    render(<BotConversation formState={{ strategy_key: null, params: {} }} />);
    await send("눌림목 봇 만들어줘");

    await waitFor(() => {
      expect(screen.getByText("에이전트 호출이 한도를 넘었습니다")).toBeTruthy();
    });
  });

  it("실패한 턴은 성공한 턴과 다르게 그려진다 — 조용히 섞이지 않는다", async () => {
    vi.mocked(selectBotAgentReadiness).mockResolvedValue({ ready: true, reasons: [], strategies_dir: "/strategies" });
    vi.mocked(streamBotAgent).mockImplementation(streamOf({ type: "error", message: "연결이 끊겼습니다" }));

    render(<BotConversation formState={{ strategy_key: null, params: {} }} />);
    await send("안녕");

    await waitFor(() => {
      expect(screen.getByText("연결이 끊겼습니다").className).toContain("text-danger");
    });
  });
});
