import { describe, expect, it } from "vitest";
import { createRequestQueue } from "@/lib/terminal/requestQueue";

/** 큐잉된 마이크로태스크 체인(`.then().catch().finally()`)이 전부 소진될 때까지 기다린다. */
function tick(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

describe("requestQueue", () => {
  it("① 동시 실행이 상한을 넘지 않는다 (작업 10개, 상한 6)", async () => {
    const queue = createRequestQueue(6);
    const releases: Array<() => void> = [];
    let current = 0;
    let peak = 0;

    const results = Array.from({ length: 10 }, (_, i) =>
      queue.enqueue(
        "g",
        () =>
          new Promise<number>((resolve) => {
            current += 1;
            peak = Math.max(peak, current);
            releases.push(() => {
              current -= 1;
              resolve(i);
            });
          }),
      ),
    );

    // enqueue 10회는 전부 동기 호출이므로, 여기 도달한 시점에 이미 상한만큼만 시작돼 있어야 한다.
    expect(queue.inflightCount()).toBe(6);
    expect(peak).toBe(6);
    expect(releases.length).toBe(6);

    while (releases.length > 0) {
      const release = releases.shift();
      release?.();
      await tick();
    }
    await tick();

    await Promise.all(results);
    expect(peak).toBe(6);
    expect(queue.inflightCount()).toBe(0);
  });

  it("② abortGroup 이 대기 중 작업을 실행 없이 거절한다", async () => {
    const queue = createRequestQueue(1);
    let secondTaskStarted = false;

    // 상한 1로 채워 두 번째 작업을 대기열에 묶어 둔다. 절대 정착하지 않는 프라미스라 타이머는 없다.
    void queue.enqueue("g", () => new Promise(() => {}));
    const second = queue.enqueue("g", () => {
      secondTaskStarted = true;
      return Promise.resolve("실행되면 안 됨");
    });

    queue.abortGroup("g");

    await expect(second).rejects.toThrow();
    expect(secondTaskStarted).toBe(false);
  });

  it("③ abortGroup 이 실행 중 작업의 signal.aborted 를 실제로 관찰하게 한다", () => {
    const queue = createRequestQueue(6);
    let capturedSignal: AbortSignal | undefined;

    void queue.enqueue("g", (signal) => {
      capturedSignal = signal;
      return new Promise(() => {});
    });

    expect(capturedSignal?.aborted).toBe(false);
    queue.abortGroup("g");
    expect(capturedSignal?.aborted).toBe(true);
  });

  it("④ 한 작업의 실패가 큐를 멈추지 않는다", async () => {
    const queue = createRequestQueue(1);

    const failing = queue.enqueue("g", () => Promise.reject(new Error("boom")));
    const succeeding = queue.enqueue("g", () => Promise.resolve("ok"));

    await expect(failing).rejects.toThrow("boom");
    await expect(succeeding).resolves.toBe("ok");
    expect(queue.inflightCount()).toBe(0);
  });
});
