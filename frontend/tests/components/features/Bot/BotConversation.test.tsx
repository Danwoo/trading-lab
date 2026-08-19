// @vitest-environment jsdom
//
// 스트림이 시작된 **뒤** 난 실패는 예외로 오지 않는다 — 서버가 `{type:"error", message}` 이벤트로
// 보낸다(`StreamingResponse` 가 이미 헤더를 보낸 뒤라 표준 예외 핸들러가 못 잡는다).
//
// **이 그물은 `fetch` 를 세운다 — 서비스 층을 모킹하지 않는다.** 앞선 판에서는
// `streamBotAgent` 를 통째로 모킹해 `onEvent` 를 직접 불렀는데, 실제 경로에서는 `fetchSSE` 가
// 그 이벤트를 가로채 예외로 바꾸므로 **컴포넌트의 이벤트 분기에는 영영 닿지 않는다.** 그때
// 테스트는 초록이었지만 화면은 여전히 실패를 삼켰다. 모킹 경계를 한 칸 내려 그 우회를 없앤다.
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { BotConversation } from "@/components/features/Bot/BotConversation";

/**
 * **준비 조회만** 결정론적으로 세운다 — 스트림 경로는 실제 `fetch` 를 그대로 태운다.
 *
 * 준비 조회는 `apiCall`(axios) 이라 jsdom 에서 XHR 어댑터를 타므로 `fetch` 스텁이 못 잡는다.
 * 그래서 그 호출이 **진짜로 실패할 때까지** 기다린 뒤에야 `ready` 가 정해졌고, 그 사이 입력창은
 * `readOnly` 라 타이핑이 통째로 삼켜졌다 — 병렬 실행에서 무작위로 빨개진 원인이 이것이다.
 * (버튼을 기다리는 것으로는 못 막는다: 입력이 삼켜지면 `draft` 가 비어 버튼이 끝내 안 열린다.)
 */
vi.mock("@/services/bot/botAgentService", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/services/bot/botAgentService")>();
  return {
    ...actual,
    selectBotAgentReadiness: vi.fn(async () => ({ ready: true, reasons: [], strategies_dir: "/s" })),
  };
});

beforeAll(() => {
  Element.prototype.scrollTo = () => {};
});

/** SSE 본문 한 벌을 그대로 흘려보내는 응답 — 줄 단위 `data:` 프레임이다. */
function sseResponse(lines: string[]): Response {
  const body = lines.map((line) => `data: ${line}\n\n`).join("");
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(body));
      controller.close();
    },
  });
  return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

function givenServer(streamLines: string[]) {
  // 준비 조회는 위에서 모킹했다 — 여기 `fetch` 는 스트림 경로 전용이다.
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => sseResponse(streamLines)),
  );
}

async function send(text: string) {
  const user = userEvent.setup();
  const textbox = screen.getByRole("textbox") as HTMLTextAreaElement;
  // 준비 조회가 끝나기 전에는 입력창이 `readOnly` 라 타이핑이 통째로 삼켜진다 — 게이트는
  // 버튼이 아니라 **입력창**이다. 여기서 단언해 두면 그 실패가 자기 이름을 갖는다.
  await waitFor(() => expect(textbox.readOnly).toBe(false));
  await user.type(textbox, text);
  expect(textbox.value).toBe(text);
  await user.click(screen.getByRole("button", { name: /보내기/ }));
}

describe("BotConversation — 스트림 중 실패가 사라지지 않는다 (실제 SSE 경로)", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("서버가 보낸 사유가 그대로 화면에 남는다 — 일반 문구로 뭉개지 않는다", async () => {
    givenServer([
      JSON.stringify({ type: "text", text: "생각하는 중" }),
      JSON.stringify({ type: "error", message: "에이전트 호출이 한도를 넘었습니다" }),
    ]);

    render(<BotConversation formState={{ strategy_key: null, params: {} }} />);
    await send("눌림목 봇 만들어줘");

    await waitFor(() => {
      expect(screen.getByText(/에이전트 호출이 한도를 넘었습니다/)).toBeTruthy();
    });
  });

  it("실패한 턴은 성공한 턴과 다르게 그려진다 — 조용히 섞이지 않는다", async () => {
    givenServer([JSON.stringify({ type: "error", message: "연결이 끊겼습니다" })]);

    render(<BotConversation formState={{ strategy_key: null, params: {} }} />);
    await send("안녕");

    await waitFor(() => {
      expect(screen.getByText(/연결이 끊겼습니다/).className).toContain("text-danger");
    });
  });

  it("성공한 턴은 실패로 그리지 않는다", async () => {
    givenServer([JSON.stringify({ type: "text", text: "이렇게 만들어 봤습니다" })]);

    render(<BotConversation formState={{ strategy_key: null, params: {} }} />);
    await send("만들어줘");

    await waitFor(() => {
      expect(screen.getByText(/이렇게 만들어 봤습니다/).className).not.toContain("text-danger");
    });
  });
});
