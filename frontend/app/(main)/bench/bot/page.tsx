import Link from "next/link";
import { BotList } from "@/components/features/Bot/BotList";

export default function Page() {
  return (
    <div className="flex h-full flex-col gap-4 p-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-medium text-ink">내 봇</h1>
          <p className="mt-1 text-sm text-ink-muted">만든 봇과 지금 상태입니다.</p>
        </div>
        <Link
          href="/bench/bot/new"
          className="border border-line px-3 py-1.5 text-sm text-ink hover:bg-bg-raised focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
        >
          봇 만들기
        </Link>
      </header>
      <BotList />
    </div>
  );
}
