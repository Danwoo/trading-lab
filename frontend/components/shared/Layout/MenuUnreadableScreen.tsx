"use client";

import { useState } from "react";
import { useNavStore } from "@/stores/shared/navStore";

/**
 * 메뉴를 못 읽어 화면을 못 여는 자리 (#333).
 *
 * **사라지지 않는다.** 종전에는 2초짜리 토스트 하나를 띄우고 로그인 화면으로 되돌렸다 —
 * 놓치면 사유를 되찾을 수단이 없고, 도착한 로그인 화면은 세션이 멀쩡한데도 로그아웃된 것처럼
 * 읽혔다. 막다른 화면의 말투·구조는 `app/error.tsx`·`app/not-found.tsx` 와 같은 줄에 둔다.
 *
 * 「관리자에게 문의」를 쓰지 않는다 — 이 제품은 로컬 배포판이라 그 관리자가 화면을 보는 사람
 * 자신이다. 그 사람이 실제로 할 수 있는 것(기동 여부 확인 → 다시 시도)만 적는다.
 */
export function MenuUnreadableScreen() {
  const [retrying, setRetrying] = useState(false);

  const retry = async () => {
    setRetrying(true);
    try {
      // `fetchNav` 는 `loaded` 면 건너뛴다 — 비우지 않으면 다시 읽지 않는다.
      useNavStore.getState().reset();
      await useNavStore.getState().fetchNav();
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div role="alert" className="flex min-h-full flex-col items-center justify-center gap-3 p-6 text-center text-ink">
      <p className="text-sm text-danger">메뉴를 읽지 못했습니다</p>
      <h1 className="break-keep text-lg font-medium text-ink">이 화면을 열 수 없습니다.</h1>
      <p className="max-w-md break-keep text-sm text-ink-muted">
        로그인은 그대로 유지되고 있습니다 — 읽지 못한 것은 메뉴 목록뿐입니다. 어느 화면이 열려도 되는지 알 수 없어 열지
        않았습니다.
      </p>
      <p className="max-w-md break-keep text-sm text-ink-muted">
        이 제품은 사용자의 컴퓨터에서 돕니다. 데이터베이스와 백엔드가 떠 있는지 확인한 뒤 다시 시도해 주세요.
      </p>
      <button
        type="button"
        onClick={retry}
        disabled={retrying}
        className="mt-2 border border-line px-3 py-1.5 text-sm text-ink hover:bg-bg-raised focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted disabled:opacity-60"
      >
        {retrying ? "다시 읽는 중…" : "다시 시도"}
      </button>
    </div>
  );
}
