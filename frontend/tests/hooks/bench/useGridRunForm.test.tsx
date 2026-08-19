// @vitest-environment jsdom
//
// #232 — **봇 화면에서 「검증하러 가기」로 온 사람은 그 봇이 이미 골라져 있어야 한다.**
//
// 길만 놓고 도착지가 빈 폼이면 사용자는 방금 보던 봇을 목록에서 다시 찾아야 한다 —
// 「가운데가 끊긴다」는 이슈의 표현이 그대로 남는다.
//
// **검증 경계** — 봇 상세 조회(`selectBot`)를 세운다. 실제 폼 렌더는 보지 않고, URL 에서
// 집은 봇 번호가 조회로 이어지는지까지를 본다.

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, renderHook, waitFor } from "@testing-library/react";

import { useGridRunForm } from "@/hooks/bench/useGridRunForm";

const selectBot = vi.fn();

vi.mock("@/services/bot/botService", () => ({
  selectBot: (...args: unknown[]) => selectBot(...args),
}));

function givenUrl(search: string) {
  window.history.replaceState({}, "", `/bench${search}`);
}

afterEach(() => {
  cleanup();
  selectBot.mockReset();
  givenUrl("");
});

describe("#232 `/bench?bot=<id>` 로 오면 그 봇이 골라진다", () => {
  it("주소의 봇을 집어 조회한다", async () => {
    selectBot.mockResolvedValue({ bot_id: 42, strategies: [] });
    givenUrl("?bot=42");

    const { result } = renderHook(() => useGridRunForm());

    await waitFor(() => expect(selectBot).toHaveBeenCalledWith(42));
    expect(result.current.botId).toBe(42);
  });

  it("봇 없이 오면 아무것도 고르지 않는다", async () => {
    givenUrl("");

    const { result } = renderHook(() => useGridRunForm());

    await waitFor(() => expect(result.current.botId).toBeNull());
    expect(selectBot).not.toHaveBeenCalled();
  });

  it("숫자가 아닌 값은 무시한다 — 주소를 손으로 고쳐도 조회로 나가지 않는다", async () => {
    givenUrl("?bot=drop-table");

    renderHook(() => useGridRunForm());

    await waitFor(() => expect(selectBot).not.toHaveBeenCalled());
  });

  it("사용자가 고른 봇을 주소가 되돌리지 않는다", async () => {
    selectBot.mockResolvedValue({ bot_id: 42, strategies: [] });
    givenUrl("?bot=42");

    const { result, rerender } = renderHook(() => useGridRunForm());
    await waitFor(() => expect(result.current.botId).toBe(42));

    result.current.changeBot(7);
    rerender();

    await waitFor(() => expect(result.current.botId).toBe(7));
  });
});
