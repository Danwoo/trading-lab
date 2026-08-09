"use client";

import { formatDate } from "@/utils/common/formatters/date";
import type { IngestRunOut } from "@/schemas/terminal/ingest";
import { describeRunRows, describeRunStatus, type RunTone } from "./ingestPresentation";

/**
 * 색만으로 상태를 구분하지 않는다(WCAG 2.1 AA) — 라벨 텍스트가 항상 함께 있고, 색은 그 라벨을
 * 거드는 역할만 한다. 「한도 소진」이 실패와 다른 색인 것도 같은 이유로 텍스트가 먼저다.
 */
const TONE_CLASS: Record<RunTone, string> = {
  pending: "text-ink-muted",
  running: "text-ink-primary",
  done: "text-ink-primary",
  resumable: "text-signal-warn",
  failed: "text-market-down",
};

function RunRow({ run }: { run: IngestRunOut }) {
  const status = describeRunStatus(run.status, run.cursor);
  const finished = run.finished_dt ?? run.started_dt ?? run.reg_dt;

  return (
    <li className="border-b border-slate-line py-2 last:border-b-0">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-ink-primary">
          {run.job_kind} · {run.scope ?? "—"}
        </span>
        <span className={TONE_CLASS[status.tone]}>{status.label}</span>
      </div>
      <div className="flex items-baseline justify-between gap-2 text-ink-muted">
        <span>
          {run.source}
          {run.period_from || run.period_to ? ` · ${run.period_from ?? ""}~${run.period_to ?? ""}` : ""}
        </span>
        <span>{describeRunRows(run)}</span>
      </div>
      {status.note && <p className={`mt-1 ${TONE_CLASS[status.tone]}`}>{status.note}</p>}
      {run.failed_reason && <p className="mt-1 text-market-down">{run.failed_reason}</p>}
      {finished && <p className="mt-1 text-ink-muted">{formatDate(finished, "datetime")}</p>}
    </li>
  );
}

export function IngestRunList({ runs }: { runs: IngestRunOut[] }) {
  if (runs.length === 0) {
    return (
      <p role="status" className="py-4 text-center text-ink-muted">
        아직 적재를 실행한 적이 없습니다.
      </p>
    );
  }

  return (
    <ul className="flex flex-col">
      {runs.map((run) => (
        <RunRow key={run.run_id} run={run} />
      ))}
    </ul>
  );
}
