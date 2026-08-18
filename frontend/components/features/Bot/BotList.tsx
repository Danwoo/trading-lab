"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getApiErrorMessage } from "@/utils/common/errors";
import { selectBotList } from "@/services/bot/botService";
import type { BotOut } from "@/schemas/bot/bot";

const ROLE_LABEL: Record<string, string> = {
  READONLY: "보기만 한다",
  PROPOSE: "제안까지 한다",
  EXECUTE: "주문까지 한다",
};

/**
 * 내 봇 목록. **0개일 때가 첫 화면**이라, 빈 자리가 무엇이 올 자리인지 말한다 (§21.4) —
 * 「없음」만 적으면 사용자는 고장인지 자기가 아직 안 만든 것인지 모른다.
 */
export function BotList() {
  const [bots, setBots] = useState<BotOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    selectBotList({})
      .then((result) => {
        if (!cancelled) setBots(result?.items ?? []);
      })
      .catch((cause) => {
        if (!cancelled) setError(getApiErrorMessage(cause));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error !== null) {
    return (
      <p role="status" className="text-sm text-ink">
        봇 목록을 불러오지 못했습니다 — {error}
      </p>
    );
  }

  if (bots === null) return <p className="text-sm text-ink-muted">불러오는 중입니다…</p>;

  if (bots.length === 0) {
    return (
      <div className="flex flex-col items-start gap-2">
        <p className="text-sm text-ink">아직 만든 봇이 없습니다.</p>
        <p className="text-sm leading-relaxed text-ink-muted">
          봇은 &ldquo;어떤 종목을, 어떤 조건에서, 얼마나&rdquo; 를 적어둔 것입니다. 하나 만들면 여기 놓이고, 검증과
          운용이 그 뒤에 붙습니다.
        </p>
        <Link href="/bench/bot/new" className="text-sm text-ink underline underline-offset-4">
          첫 봇 만들기
        </Link>
      </div>
    );
  }

  return (
    <ul className="flex flex-col divide-y divide-line border-y border-line">
      {bots.map((bot) => (
        <li key={bot.bot_id}>
          <Link
            href={`/bench/bot/${bot.bot_id}`}
            className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 px-1 py-2 hover:bg-bg-raised focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
          >
            <span className="text-sm text-ink">{bot.bot_nm}</span>
            <span className="font-mono text-2xs text-ink-muted">
              {ROLE_LABEL[bot.bot_role] ?? bot.bot_role} · {bot.use_at === "Y" ? "켜짐" : "꺼짐"}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
