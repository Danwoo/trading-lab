import Link from "next/link";

/**
 * 없는 주소로 왔을 때 (#274 계열 — 빈 자리는 무엇이 올 자리인지 말한다).
 *
 * 이 자리가 없으면 Next.js 기본 화면이 나온다 — 영문 한 줄에 돌아갈 길이 없다.
 */
export default function NotFound() {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-3 bg-bg-base p-6 text-center text-ink">
      <p className="text-sm text-ink-muted">주소를 찾지 못했습니다</p>
      <h1 className="break-keep text-lg font-medium text-ink">이 주소에 해당하는 화면이 없습니다.</h1>
      <p className="max-w-md break-keep text-sm text-ink-muted">
        주소를 잘못 입력했거나, 있던 화면이 옮겨졌을 수 있습니다. 실험대에서 다시 시작하시면 됩니다.
      </p>
      <Link
        href="/bench"
        className="mt-2 border border-line px-3 py-1.5 text-sm text-ink hover:bg-bg-raised focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
      >
        실험대로 가기
      </Link>
    </main>
  );
}
