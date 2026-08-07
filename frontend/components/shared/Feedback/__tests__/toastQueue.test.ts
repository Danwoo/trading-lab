import { afterEach, describe, expect, it, vi } from "vitest";

// toastQueue.ts(hooks/shared/gridQuery.ts 와 같은 이유로 분리된 순수 모듈)의 계약을 잠근다 —
// 독립 리뷰(PR #385)가 확인한 것: 1건씩 표시 · dismiss 후 300ms 간격 · 빈/undefined 메시지
// 무시 · showToast(message, type, duration) 시그니처. gridQuery.ts:3-8 이 선례로 든 이유(테스트
// 가능성)를 여기서도 그대로 따른다.
//
// toastQueue.ts 는 모듈 스코프 싱글턴 상태(queue·current·nextId·listeners)를 쓴다. 테스트마다
// `vi.resetModules()` 로 모듈 레지스트리를 비우고 동적 import 로 새 인스턴스를 얻어야
// 이전 테스트의 상태(특히 nextId)가 새지 않는다.
async function freshQueue() {
  vi.resetModules();
  return import("@/components/shared/Feedback/toastQueue");
}

describe("toastQueue", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("① 빈 문자열·undefined 메시지는 큐에 들어가지 않는다", async () => {
    const { showToast, getCurrentToast } = await freshQueue();
    showToast(undefined);
    showToast("");
    expect(getCurrentToast()).toBeNull();
  });

  it("② 한 번에 하나만 표시한다 — 여러 건을 연달아 넣어도 current 는 첫 번째뿐", async () => {
    const { showToast, getCurrentToast } = await freshQueue();
    showToast("첫 번째");
    showToast("두 번째");
    showToast("세 번째");

    expect(getCurrentToast()?.message).toBe("첫 번째");
  });

  it("③ dismissCurrent 는 즉시 비우고, 300ms 뒤에야 큐의 다음 토스트를 올린다", async () => {
    vi.useFakeTimers();
    const { showToast, dismissCurrent, getCurrentToast } = await freshQueue();
    showToast("첫 번째");
    showToast("두 번째");

    dismissCurrent();
    expect(getCurrentToast()).toBeNull(); // dismiss 는 즉시 반영

    vi.advanceTimersByTime(299);
    expect(getCurrentToast()).toBeNull(); // 300ms 전엔 다음 토스트가 올라오지 않는다

    vi.advanceTimersByTime(1);
    expect(getCurrentToast()?.message).toBe("두 번째");
  });

  it("④ 표시 중인 토스트가 없을 때 dismissCurrent 를 불러도 안전하다(no-op)", async () => {
    const { dismissCurrent, getCurrentToast } = await freshQueue();
    expect(() => dismissCurrent()).not.toThrow();
    expect(getCurrentToast()).toBeNull();
  });

  it("⑤ id 는 단조 증가한다", async () => {
    const { showToast, dismissCurrent, getCurrentToast } = await freshQueue();
    showToast("a");
    expect(getCurrentToast()?.id).toBe(0);

    dismissCurrent();
    showToast("b"); // current 가 비어 있으므로 즉시 표시 — 새 id 를 바로 확인할 수 있다
    expect(getCurrentToast()?.id).toBe(1);
  });

  it("⑥ 시그니처 기본값 — type 기본 info, duration 기본 2000ms", async () => {
    const { showToast, getCurrentToast } = await freshQueue();
    showToast("메시지");
    expect(getCurrentToast()).toMatchObject({ message: "메시지", type: "info", duration: 2000 });
  });

  it("⑦ type·duration 을 명시하면 그대로 반영된다", async () => {
    const { showToast, getCurrentToast } = await freshQueue();
    showToast("에러", "error", 5000);
    expect(getCurrentToast()).toMatchObject({ type: "error", duration: 5000 });
  });

  it("⑧ subscribeToast — 상태 변화 시 알리고, 해지 후엔 더 이상 부르지 않는다", async () => {
    const { showToast, dismissCurrent, subscribeToast } = await freshQueue();
    const listener = vi.fn();
    const unsubscribe = subscribeToast(listener);

    showToast("a");
    expect(listener).toHaveBeenCalledTimes(1);

    unsubscribe();
    dismissCurrent();
    expect(listener).toHaveBeenCalledTimes(1); // 해지 후 dismiss 는 알리지 않는다
  });

  it("⑨ getServerToastSnapshot 은 항상 null 이다 — 토스트는 클라이언트 전용 상태", async () => {
    const { getServerToastSnapshot } = await freshQueue();
    expect(getServerToastSnapshot()).toBeNull();
  });
});
