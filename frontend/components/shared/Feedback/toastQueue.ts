// components/shared/Feedback/toastQueue.ts
//
// #381 — `showToast`(순수 큐 함수)를 렌더(ToastNotification.tsx)에서 떼어냈다.
// gridQuery.ts(hooks/shared/gridQuery.ts)와 같은 이유로 이 파일만 따로 둔다: React·devextreme
// 등 부수효과 있는 모듈을 import 하지 않는 순수 상태 모듈이라, `hooks/shared/useServerTable.ts`
// 처럼 실패 경로에서 `showToast` 만 필요한 코드가 렌더 컴포넌트(및 그 devextreme 의존)까지
// 끌고 오지 않는다.
//
// 표시(렌더)는 한 번에 하나 — 원본(구 ToastNotification.tsx)의 큐 처리 방식을 그대로 유지한다.
// 여러 개를 동시에 쌓아 보여주는 것은 이 이슈의 범위 밖(요청되지 않은 동작 변경)이다.

export type ToastType = "success" | "error" | "info" | "warning";

export interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
  duration: number;
}

type Listener = () => void;

const queue: ToastItem[] = [];
let current: ToastItem | null = null;
let nextId = 0;
const listeners = new Set<Listener>();

function emit() {
  for (const listener of listeners) listener();
}

function processNext() {
  if (current || queue.length === 0) return;
  current = queue.shift()!;
  emit();
}

/** 토스트를 큐에 넣는다. 현재 표시 중인 토스트가 없으면 즉시 처리를 시작한다. */
export function showToast(message: string | undefined, type: ToastType = "info", duration = 2000) {
  if (!message) {
    return;
  }
  queue.push({ id: nextId++, message, type, duration });
  processNext();
}

/**
 * 현재 토스트를 닫고 큐의 다음 토스트를 처리한다. 원본과 동일하게 300ms 간격을 둔다 — 닫힘
 * 애니메이션 없이 곧바로 다음 토스트가 튀어나오면 두 메시지가 겹쳐 보인다.
 */
export function dismissCurrent() {
  if (!current) return;
  current = null;
  emit();
  setTimeout(processNext, 300);
}

/** ToastNotification 컴포넌트가 `useSyncExternalStore` 로 구독한다. */
export function subscribeToast(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getCurrentToast(): ToastItem | null {
  return current;
}

/** 서버 렌더 스냅샷 — 토스트는 항상 클라이언트 전용 상태라 서버에선 아무것도 없다. */
export function getServerToastSnapshot(): ToastItem | null {
  return null;
}
