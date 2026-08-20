"use client";

import { useEffect } from "react";

/**
 * 화면을 그리다 예외가 났을 때. 이 자리가 없으면 트리 전체가 Next.js 기본 화면으로 넘어간다.
 *
 * **원인 문자열을 화면에 싣지 않는다.** 예외 메시지에는 요청 URL·키가 실려 나온 전례가 있고
 * (#274), 여기는 그것을 걸러 줄 사람이 없다. 대신 무엇이 멈췄고 무엇을 할 수 있는지 말한다.
 */
export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-3 p-6 text-center" role="alert">
      <p className="text-sm text-danger">화면을 그리지 못했습니다</p>
      <h1 className="break-keep text-lg font-medium text-ink">이 화면이 멈췄습니다.</h1>
      <p className="max-w-md break-keep text-sm text-ink-muted">
        저장된 것은 그대로 있습니다 — 멈춘 것은 이 화면뿐입니다. 다시 그려 보거나 실험대로 돌아가시면 됩니다.
      </p>
      {error.digest && <p className="text-2xs text-ink-muted">기록 번호 {error.digest}</p>}
      <div className="mt-2 flex flex-wrap justify-center gap-2">
        <button
          type="button"
          onClick={reset}
          className="border border-line px-3 py-1.5 text-sm text-ink hover:bg-bg-raised focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
        >
          다시 그리기
        </button>
        <a
          href="/bench"
          className="border border-line px-3 py-1.5 text-sm text-ink hover:bg-bg-raised focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
        >
          실험대로 가기
        </a>
      </div>
    </main>
  );
}
