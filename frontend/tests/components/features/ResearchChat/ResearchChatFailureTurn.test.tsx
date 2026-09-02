// @vitest-environment jsdom
//
// #423 F7 — **리서치 서비스가 안 떠 있을 때 실패가 대화에 남는다.** 2초 토스트는 흔적이 아니다.
//
// 종전 동작(Cycle 6 실측): 프록시 500 → 진행 중이던 말풍선이 `ABORT_ASSISTANT_MSG` 로 **제거**되고
// 토스트가 약 2초 떴다 사라진다. 그 뒤 화면은 질문만 남고 답도 설명도 없다 — 잠깐 눈을 떼면
// 「보냈는데 아무 일도 없는」 화면이 된다. 처방도 틀렸다(재시도가 아니라 서비스 기동이다).
//
// **이 그물은 `fetch` 를 세운다** — 서비스 층을 모킹하지 않는다. 프록시가 실제로 내는 봉투
// (사유 코드를 실은 503)를 그대로 흘려, `fetchNDJSON` → `getApiErrorMessage` → 화면까지의
// 경로를 통째로 태운다. 서비스를 모킹하면 그 사이의 뭉개짐을 못 본다 (BotConversation 과 같은 이유).

import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ResearchChatContainer from "@/components/features/ResearchChat/ResearchChatContainer";

// 근거 카드가 파일 서비스 URL 을 물어 `@/env` 검증이 import 시점에 돈다 — 이 그물의 대상이 아니다.
vi.mock("@/env", () => ({ env: { NEXT_PUBLIC_FILE_SERVICE_URL: "http://files.test", NODE_ENV: "development" } }));

// jsdom 은 ResizeObserver 를 구현하지 않는다 — `SplitPane`(react-resizable-panels)이 마운트
// 시점에 `new ResizeObserver(...)` 를 부르며 렌더 자체를 막는다.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeAll(() => {
  vi.stubGlobal("ResizeObserver", ResizeObserverStub);
  Element.prototype.scrollTo = () => {};
  Element.prototype.scrollIntoView = () => {};
  window.requestAnimationFrame = ((cb: FrameRequestCallback) => {
    cb(0);
    return 0;
  }) as typeof window.requestAnimationFrame;
});

/** :8003 이 안 떠 있을 때 프록시가 내는 봉투 — 닫힌 집합의 사유 코드만 건넌다. */
function givenServiceDown() {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify({ code: "research.service_unreachable" }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
}

/**
 * 빈 대화의 예시 질문을 눌러 한 턴을 건다 — 실제로 클릭 가능한 진입점이라(placeholder 가 아니다)
 * 입력창 타이핑을 흉내 내지 않고도 같은 `send` 경로를 탄다.
 */
const EXAMPLE_QUESTION = "이 종목 리스크 요인 정리해줘";

async function askExample() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: EXAMPLE_QUESTION }));
}

describe("#423 리서치 챗 — 서비스 부재가 대화에 흔적으로 남는다", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("질문만 남고 사라지지 않는다 — 실패 턴이 대화에 남고 「띄우라」고 말한다", async () => {
    givenServiceDown();
    render(<ResearchChatContainer />);

    await askExample();

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toMatch(/띄운 뒤 다시 물어보세요/);
    });

    // 질문도 그대로 남아 있어야 한다 — 무엇에 대한 실패인지 알 수 있게.
    expect(screen.getByText(EXAMPLE_QUESTION)).toBeTruthy();
  });
});
