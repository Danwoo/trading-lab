// @vitest-environment jsdom
//
// #317 — **구간을 거꾸로 넣으면 화면의 칸 이름으로 답하고, 요청은 나가지 않는다.**
//
// 실측(이슈 본문): 시작 `2026-08-20` · 끝 `2023-08-21` 로 「격자 실행」을 누르면 서버가
// `400 {"detail":"date_from 이 date_to 보다 늦습니다."}` 를 냈고 그 문장이 격자 자리에 그대로
// 그려졌다. `date_from`·`date_to` 는 화면 어디에도 없는 이름이라, 두 칸(「구간 시작」·「구간 끝」)
// 중 어느 것이 잘못됐는지 읽는 사람이 알아낼 수 없다. 게다가 두 값 다 화면이 이미 갖고 있다.
//
// `buildInput()` 이 `null` 이면 `GridRunForm` 의 `onSubmit` 이 `onRun` 을 안 부른다 —
// 그것이 「요청이 나가지 않는다」의 구현이다. 그래서 여기서는 그 계약을 단언한다.

import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";

import { useGridRunForm } from "@/hooks/bench/useGridRunForm";
import { selectBot } from "@/services/bot/botService";

vi.mock("@/services/bot/botService", () => ({ selectBot: vi.fn() }));

const A_BOT = {
  bot_id: 1,
  strategies: [
    {
      bot_strategy_id: 1,
      strategy_key: "pullback",
      params: { window: 20 },
      param_sources: {},
      weight: null,
      sort_order: 1,
      form: {
        key: "pullback",
        fields: [{ name: "window", label: "창", control: "number", default: 20, min: 5, max: 40 }],
      },
      missing_reason: null,
    },
  ],
};

afterEach(() => {
  cleanup();
  vi.mocked(selectBot).mockReset();
});

async function givenBotPicked() {
  vi.mocked(selectBot).mockResolvedValue(A_BOT as never);
  const { result } = renderHook(() => useGridRunForm());
  act(() => result.current.changeBot(1));
  await waitFor(() => expect(result.current.strategy).not.toBeNull());
  act(() => result.current.changeField("symbol", "005930"));
  return result;
}

describe("#317 격자 폼이 뒤집힌 구간을 서버로 보내지 않는다", () => {
  it("거꾸로 넣으면 폼의 칸 이름으로 사유가 서고 입력이 만들어지지 않는다", async () => {
    const result = await givenBotPicked();

    act(() => result.current.changeField("period_from", "2026-08-20"));
    act(() => result.current.changeField("period_to", "2023-08-21"));

    let input: unknown = "not-called";
    act(() => {
      input = result.current.buildInput();
    });

    expect(input).toBeNull();
    expect(result.current.formError).toContain("구간 시작");
    expect(result.current.formError).toContain("구간 끝");
    expect(result.current.formError).not.toContain("date_from");
  });

  it("바로 놓인 구간은 그대로 통과한다 — 검사가 과해서 정상 입력을 막지 않는다", async () => {
    const result = await givenBotPicked();

    act(() => result.current.changeField("period_from", "2023-08-21"));
    act(() => result.current.changeField("period_to", "2026-08-20"));

    let input: { period_from: string; period_to: string } | null = null;
    act(() => {
      input = result.current.buildInput() as never;
    });

    expect(input).not.toBeNull();
    expect(result.current.formError).toBeNull();
  });

  it("같은 날짜 하루짜리 구간도 통과한다 — 경계는 막는 쪽이 아니다", async () => {
    const result = await givenBotPicked();

    act(() => result.current.changeField("period_from", "2026-08-20"));
    act(() => result.current.changeField("period_to", "2026-08-20"));

    let input: unknown = null;
    act(() => {
      input = result.current.buildInput();
    });

    expect(input).not.toBeNull();
  });
});
