// #408 회귀 그물 — 같은 tick 에 띄운 메시지가 버려지지 않고, 그 Promise 가 매달리지 않는다.
//
// 결함(수정 전): `showMessage` 는 `!currentMessage` 일 때마다 `setTimeout(processNext, 0)` 을
// 걸었다. 한 tick 에 두 번 호출하면 **두 호출 모두** 그 조건을 만족해(아직 `currentMessage` 가
// 안 세워졌다) `processNext` 가 두 번 예약되고, 두 번째 실행이 큐에서 두 번째 메시지를 꺼내
// 첫 메시지를 덮어썼다. 덮인 메시지의 `resolve` 는 아무도 부르지 않아 `await showMessage(...)`
// 한 호출부가 영영 멈췄다.
//
// 뿌리는 `processNext` 가 **재진입에 무방비**였다는 것이다 — 이미 메시지가 떠 있어도
// 무조건 큐에서 하나를 꺼내 덮었다. 그래서 예약이 몇 번 걸리든(같은 tick 중복 예약,
// resolveMessage 가 건 뒤늦은 타이머) 상관없이 안전하도록 `processNext` 를 멱등으로 만든다.
//
// 이 파일이 증명하는 것: 큐의 순서·전건 전달·resolve 전건 호출(= 매달린 Promise 0건).
// 증명하지 못하는 것: 화면 렌더/애니메이션 (그 축은 MessagePopup.test.tsx·실브라우저 몫).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MESSAGE_CLOSE_ANIMATION_MS, showMessage, useMessageStore } from "@/stores/shared/messageStore";

beforeEach(() => {
  vi.useFakeTimers();
  useMessageStore.setState({ messages: [], currentMessage: null });
});

afterEach(() => {
  vi.useRealTimers();
  useMessageStore.setState({ messages: [], currentMessage: null });
});

/** 지금 떠 있는 메시지를 확인 처리하고, 닫힘 애니메이션 여백까지 흘려 다음 메시지를 연다. */
async function confirmCurrent() {
  useMessageStore.getState().resolveMessage(true);
  await vi.advanceTimersByTimeAsync(MESSAGE_CLOSE_ANIMATION_MS);
}

describe("messageStore — 같은 tick 의 메시지 (#408)", () => {
  it("같은 tick 에 두 건을 띄우면 첫 건이 먼저 뜨고 둘째는 큐에 남는다", async () => {
    void showMessage("첫 번째", "a");
    void showMessage("두 번째", "b");

    await vi.advanceTimersByTimeAsync(0);

    expect(useMessageStore.getState().currentMessage?.title).toBe("첫 번째");
    expect(useMessageStore.getState().messages.map((m) => m.title)).toEqual(["두 번째"]);

    await confirmCurrent();
    expect(useMessageStore.getState().currentMessage?.title).toBe("두 번째");
  });

  it("같은 tick 에 세 건을 띄워도 순서대로 전부 뜨고 resolve 가 전건 호출된다", async () => {
    const resolved: string[] = [];
    void showMessage("A", "a").then(() => resolved.push("A"));
    void showMessage("B", "b").then(() => resolved.push("B"));
    void showMessage("C", "c").then(() => resolved.push("C"));

    await vi.advanceTimersByTimeAsync(0);
    expect(useMessageStore.getState().currentMessage?.title).toBe("A");

    await confirmCurrent();
    expect(useMessageStore.getState().currentMessage?.title).toBe("B");

    await confirmCurrent();
    expect(useMessageStore.getState().currentMessage?.title).toBe("C");

    await confirmCurrent();
    expect(useMessageStore.getState().currentMessage).toBeNull();

    // 매달린 Promise 0건 — 세 건 모두 풀렸다.
    expect(resolved).toEqual(["A", "B", "C"]);
  });

  it("await 한 호출부가 매달리지 않는다 (같은 tick 두 건, 병렬 대기)", async () => {
    let settled = 0;
    const both = Promise.all([
      showMessage("검증 실패 1", "a").then((v) => {
        settled += 1;
        return v;
      }),
      showMessage("검증 실패 2", "b").then((v) => {
        settled += 1;
        return v;
      }),
    ]);

    await vi.advanceTimersByTimeAsync(0);
    expect(settled).toBe(0);

    await confirmCurrent();
    expect(settled).toBe(1);

    await confirmCurrent();
    await expect(both).resolves.toEqual([true, true]);
  });

  it("resolveMessage 가 건 뒤늦은 타이머가 새로 뜬 메시지를 덮지 않는다", async () => {
    // 큐가 빈 상태에서 닫으면 `resolveMessage` 가 건 processNext 예약(150ms)이 허공에 남는다.
    // 그 창(window) 안에서 새 메시지를 띄우면 0ms 예약이 먼저 그것을 열고, 뒤이어 그 잔여
    // 타이머가 돌면서 큐의 다음 건으로 화면을 덮어썼다 — 덮인 쪽 resolve 는 미아가 됐다.
    void showMessage("먼저", "a");
    await vi.advanceTimersByTimeAsync(0);
    useMessageStore.getState().resolveMessage(true); // 큐가 비어 있는 채로 닫힘 + 150ms 예약

    let secondResolved = false;
    void showMessage("나중 1", "b").then(() => {
      secondResolved = true;
    });
    await vi.advanceTimersByTimeAsync(0);
    expect(useMessageStore.getState().currentMessage?.title).toBe("나중 1");

    void showMessage("나중 2", "c");
    // 잔여 타이머(150ms)가 도는 시점을 통과시킨다.
    await vi.advanceTimersByTimeAsync(MESSAGE_CLOSE_ANIMATION_MS);

    expect(useMessageStore.getState().currentMessage?.title).toBe("나중 1");
    expect(secondResolved).toBe(false);
    expect(useMessageStore.getState().messages.map((m) => m.title)).toEqual(["나중 2"]);
  });
});
