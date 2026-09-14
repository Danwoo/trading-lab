"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { selectBacktestRunsByBot } from "@/services/backtest/backtestService";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";
import type { BotRunOut } from "@/schemas/backtest/backtest";

/** 조합 한 줄 — 격자 칸과 같은 어휘(`ma_period=120 · pullback_pct=15`). */
function paramsLine(params: Record<string, unknown>): string {
  return Object.entries(params)
    .map(([key, value]) => `${key}=${String(value)}`)
    .join(" · ");
}

/**
 * 같은 조합(전략·파라미터·종목·구간)을 먼저 돌린 실행 번호. 같은 봇을 격자로 되돌리면 run 은
 * 불변이라 **매번 새 행**이 생기고(실측: 한 조합이 25행), 목록만 봐서는 그게 반복인지 모른다.
 * 목록은 최신순이라 **더 오래된 쪽**이 원본이다. 보이는 페이지 안에서만 가린다 — 안 보이는
 * 옛 실행과의 중복은 여기서 알 수 없다.
 */
export function firstRunOfSameCombo(runs: BotRunOut[]): Map<number, number> {
  const firstByCombo = new Map<string, number>();
  const sameAs = new Map<number, number>();
  for (const run of [...runs].sort((a, b) => a.run_id - b.run_id)) {
    const combo = JSON.stringify([run.strategy_key, run.params, run.universe_def, run.period_from, run.period_to]);
    const first = firstByCombo.get(combo);
    if (first === undefined) firstByCombo.set(combo, run.run_id);
    else sameAs.set(run.run_id, first);
  }
  return sameAs;
}

/** 검증 이력이 있으면 그 목록을, 없으면 검증하러 가는 길을 낸다. */
export function BotRunHistory({ botId }: { botId: number }) {
  const [runs, setRuns] = useState<BotRunOut[] | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    selectBacktestRunsByBot(botId)
      .then((result) => {
        if (cancelled) return;
        setRuns(result?.items ?? []);
        setTotalCount(result?.total_count ?? 0);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setError(getApiErrorMessage(cause));
      });
    return () => {
      cancelled = true;
    };
  }, [botId]);

  const sameAs = firstRunOfSameCombo(runs ?? []);

  return (
    <section className="border border-line px-3 py-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm text-ink">이 봇의 검증</h2>
        <Link href={`/bench?bot=${botId}`} className="text-2xs text-ink-muted underline underline-offset-2">
          이 봇으로 검증하러 가기
        </Link>
      </div>

      {error !== null ? (
        <p className="mt-1 text-2xs text-ink-muted">이력을 불러오지 못했습니다 — {error}</p>
      ) : runs === null ? (
        <p className="mt-1 text-2xs text-ink-muted">불러오는 중입니다…</p>
      ) : runs.length === 0 ? (
        // 「0건」과 「못 읽었다」를 가른 뒤라, 여기서는 다음 걸음만 말한다.
        <p className="mt-1 text-2xs text-ink-muted">아직 검증한 적이 없습니다. 격자를 한 번 돌리면 여기에 남습니다.</p>
      ) : (
        <>
          {totalCount > runs.length && (
            // 목록은 한 페이지다 — 총수를 안 말하면 「이 봇은 20번 검증했다」로 읽힌다.
            <p className="mt-1 text-2xs text-ink-muted">
              모두 {totalCount}번 검증했습니다 · 최근 {runs.length}건만 보입니다
            </p>
          )}
          <ul className="mt-1 flex flex-col gap-0.5">
            {runs.map((run) => {
              const first = sameAs.get(run.run_id);
              return (
                <li key={run.run_id} className="font-mono text-2xs text-ink-muted">
                  <Link href={`/bench?run=${run.run_id}`} className="underline underline-offset-2">
                    #{run.run_id}
                  </Link>{" "}
                  {run.status} · {run.period_from}~{run.period_to} · 시도 {run.attempt_no}
                  <span className="block break-all pl-3 text-ink-muted">
                    {paramsLine(run.params)}
                    {first !== undefined && ` · 같은 조합을 #${first} 에서 이미 돌렸습니다`}
                  </span>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </section>
  );
}
