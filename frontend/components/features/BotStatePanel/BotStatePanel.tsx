"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePanelProvenance } from "@/components/features/Terminal/panelProvenanceBridge";
import { selectBotList } from "@/services/bot/botService";
import { getApiErrorMessage } from "@/utils/common/errors";
import type { BotOut } from "@/schemas/bot/bot";
import type { PanelProps } from "@/types/terminal/panel";

const ROLE_LABEL: Record<string, string> = {
  READONLY: "보기만 한다",
  PROPOSE: "제안까지 한다",
  EXECUTE: "주문까지 한다",
};

/**
 * 봇 상태 패널 — 저장한 봇과 지금 상태.
 *
 * 이 패널의 데이터는 **우리 DB 에서 온 실물**이다(외부 소스가 필요 없다). 그래서 출처는
 * `loaded` 다. 다만 「지금 무엇을 하고 있나」(장중 신호 판정)는 봇 실행 엔진의 산출물이라
 * 이번 마일스톤의 no-go 다 — 그 칸은 만들지 않고, 대신 저장된 **역할**을 보여준다.
 */
export default function BotStatePanel({ instanceId }: PanelProps) {
  const reportProvenance = usePanelProvenance(instanceId);
  const [bots, setBots] = useState<BotOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    selectBotList({})
      .then((result) => {
        if (cancelled) return;
        setBots(result?.items ?? []);
        reportProvenance({ kind: "loaded", source: "봇 저장본", asOf: null });
      })
      .catch((cause) => {
        if (cancelled) return;
        const message = getApiErrorMessage(cause);
        setError(message);
        reportProvenance({ kind: "unavailable", reason: `봇 목록을 불러오지 못했습니다 — ${message}` });
      });
    return () => {
      cancelled = true;
    };
  }, [reportProvenance]);

  if (error !== null) return null; // 사유는 프레임이 그린다
  if (bots === null) return <p className="p-3 text-xs text-ink-muted">불러오는 중입니다…</p>;

  if (bots.length === 0) {
    return (
      <div className="flex h-full flex-col justify-center gap-2 px-4 text-sm">
        <p className="text-ink-primary">아직 만든 봇이 없습니다.</p>
        <Link href="/bench/bot/new" className="text-ink-primary underline underline-offset-4">
          봇 만들기
        </Link>
      </div>
    );
  }

  return (
    <ul className="divide-y divide-slate-line font-mono text-xs">
      {bots.map((bot) => (
        <li key={bot.bot_id}>
          <Link
            href={`/bench/bot/${bot.bot_id}`}
            className="flex items-baseline justify-between gap-2 px-3 py-2 hover:bg-slate-void focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
          >
            <span className="min-w-0 truncate text-ink-primary">{bot.bot_nm}</span>
            <span className="flex-shrink-0 text-ink-muted">
              {ROLE_LABEL[bot.bot_role] ?? bot.bot_role} · {bot.use_at === "Y" ? "켜짐" : "꺼짐"}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
