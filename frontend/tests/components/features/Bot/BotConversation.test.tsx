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
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).includes("readiness")) {
        return new Response(JSON.stringify({ ready: true, reasons: [], strategies_dir: "/s" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return sseResponse(streamLines);
    }),
  );
}

async function send(text: string) {
  const user = userEvent.setup();
  await user.type(screen.getByRole("textbox"), text);
  // **준비 조회가 끝나기 전에는 보내기가 비활성이다.** 그것을 안 기다리고 누르면 클릭이
  // 아무 일도 안 하고, 테스트는 부하에 따라 붙었다 떨어졌다 한다(병렬 실행에서 실측).
  const button = screen.getByRole("button", { name: /보내기/ }) as HTMLButtonElement;
  await waitFor(() => expect(button.disabled).toBe(false));
  await user.click(button);
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
