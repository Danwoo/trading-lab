"use client";

// components/shared/Feedback/ToastNotification.tsx
//
// #381 — devextreme-react/toast 를 걷어낸 자체 구현. 큐 로직(showToast 등)은
// toastQueue.ts(순수 모듈, 부수효과 없음)에 있고, 이 파일은 그 큐를 구독해 그리는 렌더만
// 맡는다. `showToast` 를 재수출해 이 배럴(`@/components/shared/Feedback`)을 거치는 기존
// 호출부의 import 경로를 그대로 둔다. `hooks/shared/useServerTable.ts` 는 렌더 컴포넌트를
// 끌고 오지 않도록 `toastQueue.ts` 를 직접 import 한다 — toastQueue.ts:5-7 참고.

import { useEffect, useSyncExternalStore } from "react";
import { ICON_HIT_AREA } from "@/components/shared/ui/primitives/hitArea";
import {
  dismissCurrent,
  getCurrentToast,
  getServerToastSnapshot,
  showToast,
  subscribeToast,
  type ToastType,
} from "./toastQueue";

export { showToast };

// Alert.tsx(같은 Feedback 폴더)와 같은 팔레트·아이콘 — 이 레포가 이미 쓰는 성공/경고/오류/정보
// 시각 언어를 그대로 따른다(새 팔레트를 들이지 않는다). 색만으로 구분하지 않도록 아이콘 +
// 문구를 항상 함께 쓴다.
const TYPE_STYLES: Record<ToastType, { bg: string; border: string; text: string; icon: string }> = {
  info: { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-900", icon: "💡" },
  warning: { bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-900", icon: "⚠️" },
  error: { bg: "bg-red-50", border: "border-red-200", text: "text-red-900", icon: "❌" },
  success: { bg: "bg-green-50", border: "border-green-200", text: "text-green-900", icon: "✅" },
};

/**
 * 전역 토스트 알림. RootLayout 이 라우트마다 한 번 마운트한다(`components/shared/Feedback/index.ts`
 * 경유). `showToast`(toastQueue.ts)가 채운 큐를 구독해 한 번에 하나씩 표시한다(원본 동작 유지).
 *
 * 접근성: 경고·오류는 `role="alert"`(즉시·강하게 알림), 성공·정보는 `role="status"`(완곡하게
 * 알림)로 화면판독기에 전달한다. 닫기 버튼은 실제 `<button>` 이라 Tab 으로 도달하고 Enter/Space
 * 로 닫힌다. 등장 애니메이션은 `prefers-reduced-motion: reduce` 에서 꺼진다(globals.css).
 */
export function ToastNotification() {
  const toast = useSyncExternalStore(subscribeToast, getCurrentToast, getServerToastSnapshot);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(dismissCurrent, toast.duration);
    return () => clearTimeout(timer);
  }, [toast]);

  if (!toast) return null;

  const style = TYPE_STYLES[toast.type];
  const isUrgent = toast.type === "error" || toast.type === "warning";

  return (
    <div
      role={isUrgent ? "alert" : "status"}
      className={`toast-notification pointer-events-auto fixed right-2.5 top-2.5 z-[2000] flex w-[300px] items-start gap-2 rounded-md border px-4 py-3 shadow-lg ${style.bg} ${style.border}`}
    >
      <span aria-hidden="true" className="mt-0.5 flex-shrink-0 text-base leading-none">
        {style.icon}
      </span>
      <p className={`min-w-0 flex-1 break-words text-sm ${style.text}`}>{toast.message}</p>
      <button
        type="button"
        onClick={dismissCurrent}
        aria-label="알림 닫기"
        className={`${ICON_HIT_AREA} flex-shrink-0 rounded text-base leading-none ${style.text} opacity-60 transition-opacity hover:opacity-100 focus:opacity-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1`}
      >
        <span aria-hidden="true">×</span>
      </button>
    </div>
  );
}
