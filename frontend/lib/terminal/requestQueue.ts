import { MAX_INFLIGHT_REQUESTS } from "@/constants/terminal";

export interface RequestQueue {
  enqueue<T>(group: string, task: (signal: AbortSignal) => Promise<T>): Promise<T>;
  abortGroup(group: string): void;
  inflightCount(): number;
}

/** 대기 중 작업이 취소됐을 때 던지는 사유 — 실행된 적 없는 작업임을 구분한다. */
class QueueAbortError extends Error {
  constructor(group: string) {
    super(`요청이 취소되었습니다: ${group}`);
    this.name = "QueueAbortError";
  }
}

interface QueueEntry<T> {
  group: string;
  controller: AbortController;
  task: (signal: AbortSignal) => Promise<T>;
  resolve: (value: T) => void;
  reject: (reason: unknown) => void;
}

/**
 * 문맥 세대(`group`) 단위로 동시 인플라이트 요청 상한을 지킨다. `enqueue` 는 상한을 넘으면
 * 대기열에 두고, 자리가 나는 대로 순서대로 실행한다 (§3.7).
 */
export function createRequestQueue(maxInflight: number): RequestQueue {
  const pending: QueueEntry<unknown>[] = [];
  const running = new Set<QueueEntry<unknown>>();

  function pump(): void {
    while (running.size < maxInflight && pending.length > 0) {
      const entry = pending.shift();
      if (!entry) break;
      running.add(entry);
      entry
        .task(entry.controller.signal)
        .then((value) => entry.resolve(value))
        .catch((error: unknown) => entry.reject(error))
        .finally(() => {
          running.delete(entry);
          pump();
        });
    }
  }

  return {
    enqueue<T>(group: string, task: (signal: AbortSignal) => Promise<T>): Promise<T> {
      return new Promise<T>((resolve, reject) => {
        const entry: QueueEntry<unknown> = {
          group,
          controller: new AbortController(),
          task: task as (signal: AbortSignal) => Promise<unknown>,
          resolve: resolve as (value: unknown) => void,
          reject,
        };
        pending.push(entry);
        pump();
      });
    },

    abortGroup(group: string): void {
      // 대기 중 작업 — 실행하지 않고 즉시 거절한다.
      for (let i = pending.length - 1; i >= 0; i -= 1) {
        if (pending[i].group === group) {
          const [entry] = pending.splice(i, 1);
          entry.controller.abort();
          entry.reject(new QueueAbortError(group));
        }
      }
      // 실행 중 작업 — signal 만 abort 한다. 실제 정지는 task 가 signal 을 관찰해야 한다.
      for (const entry of running) {
        if (entry.group === group) {
          entry.controller.abort();
        }
      }
    },

    inflightCount(): number {
      return running.size;
    },
  };
}

/** 앱 기본 인스턴스 — 테스트는 절대 이걸 쓰지 않고 `createRequestQueue` 로 자기 인스턴스를 만든다. */
export const requestQueue: RequestQueue = createRequestQueue(MAX_INFLIGHT_REQUESTS);
