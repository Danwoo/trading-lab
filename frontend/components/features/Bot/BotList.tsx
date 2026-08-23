"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getApiErrorMessage } from "@/utils/common/errors";
import { selectBotList } from "@/services/bot/botService";
import { deleteBotWithConfirm } from "./deleteBotWithConfirm";
import type { BotOut } from "@/schemas/bot/bot";
import { BOT_ROLE_LABEL } from "@/schemas/bot/bot";
import { WRITE_DENIED_SHORT } from "@/constants/writeAccess";
import { useWriteAccess } from "@/hooks/shared/useWriteAccess";

/**
 * 내 봇 목록. **0개일 때가 첫 화면**이라, 빈 자리가 무엇이 올 자리인지 말한다 (§21.4) —
 * 「없음」만 적으면 사용자는 고장인지 자기가 아직 안 만든 것인지 모른다.
 *
 * 지우기가 여기에 있는 이유: 시험 삼아 만든 봇이 쌓이는 자리가 곧 이 목록이라, 지우려고
 * 상세로 들어갔다 나오는 왕복이 그대로 마찰이 된다 (#315).
 */
export function BotList() {
  const [bots, setBots] = useState<BotOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const writeAccess = useWriteAccess();

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

  // 지운 뒤 목록을 다시 부르지 않고 그 행만 뺀다 — 방금 지운 것을 서버에 되물어 확인할 이유가
  // 없고, 재조회가 실패하면 삭제는 성공했는데 화면이 오류로 뒤집힌다.
  const handleDelete = async (bot: BotOut) => {
    setDeletingId(bot.bot_id);
    try {
      const deleted = await deleteBotWithConfirm(bot);
      if (deleted) setBots((prev) => (prev === null ? prev : prev.filter((it) => it.bot_id !== bot.bot_id)));
    } finally {
      setDeletingId(null);
    }
  };

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
        {/* 못 만드는 계정을 만들기 화면으로 보내지 않는다 — 거기서 「저장」을 눌러야 403 을 만난다 (#341). */}
        {writeAccess.isDenied ? (
          <p className="text-sm text-ink-muted">{WRITE_DENIED_SHORT}</p>
        ) : (
          <Link href="/bench/bot/new" className="text-sm text-ink underline underline-offset-4">
            첫 봇 만들기
          </Link>
        )}
      </div>
    );
  }

  return (
    <ul className="flex flex-col divide-y divide-line border-y border-line">
      {bots.map((bot) => (
        <li key={bot.bot_id} className="flex min-w-0 items-center gap-1">
          {/* 지우기는 링크 **밖**에 선다 — 링크 안에 버튼을 넣으면 어느 쪽이 눌린 것인지가 모호해진다. */}
          <Link
            href={`/bench/bot/${bot.bot_id}`}
            className="flex min-w-0 flex-1 flex-wrap items-baseline justify-between gap-x-3 gap-y-1 px-1 py-2 hover:bg-bg-raised focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
          >
            <span className="text-sm text-ink">{bot.bot_nm}</span>
            <span className="font-mono text-2xs text-ink-muted">
              {BOT_ROLE_LABEL[bot.bot_role]} · {bot.use_at === "Y" ? "켜짐" : "꺼짐"}
            </span>
          </Link>
          <button
            type="button"
            // 행마다 같은 「삭제」가 서므로 이름에 봇을 넣는다 — 소리로 듣는 사람에게는 그것만이 구분이다.
            aria-label={`${bot.bot_nm} 삭제`}
            disabled={deletingId === bot.bot_id || !writeAccess.canWrite}
            title={writeAccess.deniedHint}
            onClick={() => void handleDelete(bot)}
            className="shrink-0 px-2 py-2 text-2xs text-ink-muted underline underline-offset-2 hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted disabled:text-ink-muted"
          >
            삭제
          </button>
        </li>
      ))}
    </ul>
  );
}
