"use client";

import { useState } from "react";

import { probeDataKey, saveDataKey, type DataKeyStatus } from "@/services/dataKey/dataKeyService";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";
import { cn } from "@/components/shared/ui/primitives/cn";

/** 화면이 값을 되읽지 않는다 — 입력칸은 넣는 자리일 뿐, 저장된 값은 어디서도 보이지 않는다. */
type Outcome = { kind: "idle" } | { kind: "busy" } | { kind: "said"; ok: boolean; text: string };

export function DataKeyRow({ row, onSaved }: { row: DataKeyStatus; onSaved: () => void }) {
  const [value, setValue] = useState("");
  const [outcome, setOutcome] = useState<Outcome>({ kind: "idle" });

  const busy = outcome.kind === "busy";
  const canSubmit = value.trim().length > 0 && !busy;

  /** 확인·저장이 같은 실패 처리를 쓴다 — 사유를 삼키지 않는다. */
  const run = async (what: "probe" | "save") => {
    setOutcome({ kind: "busy" });
    try {
      if (what === "probe") {
        const probe = await probeDataKey(row.source, value);
        if (probe === null) throw new Error("확인 결과를 받지 못했습니다");
        setOutcome({ kind: "said", ok: probe.ok, text: probe.detail });
        return;
      }
      const saved = await saveDataKey(row.source, value);
      if (saved === null) throw new Error("저장 결과를 받지 못했습니다");
      // 넣은 값을 화면에 남기지 않는다 — 저장이 끝나면 입력칸을 비운다.
      setValue("");
      setOutcome({
        kind: "said",
        ok: true,
        text: saved.restart_required
          ? `${saved.setting} 에 저장했습니다 — 반영에는 재기동이 필요합니다`
          : `${saved.setting} 에 저장했습니다`,
      });
      onSaved();
    } catch (cause: unknown) {
      setOutcome({ kind: "said", ok: false, text: getApiErrorMessage(cause) });
    }
  };

  return (
    <li className="flex min-w-0 flex-col gap-1 border-b border-line py-2 last:border-b-0">
      <div className="flex min-w-0 flex-wrap items-baseline gap-x-2">
        <span className="text-sm text-ink">{row.source}</span>
        <span className="min-w-0 break-all font-mono text-2xs text-ink-muted">{row.setting}</span>
        <span className={row.filled ? "text-2xs text-ink" : "text-2xs text-danger"}>
          {row.filled ? "설정됨" : "없음"}
        </span>
      </div>

      {row.guidance && <p className="min-w-0 break-keep text-2xs text-ink-muted">{row.guidance}</p>}

      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <input
          type={row.secret ? "password" : "text"}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={row.filled ? "새 값으로 바꾸려면 입력" : "값을 넣으세요"}
          aria-label={`${row.source} ${row.setting}`}
          autoComplete="off"
          className="min-h-touch-min min-w-0 flex-1 border border-line bg-bg-base px-2 py-1 font-mono text-2xs text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
        />
        <button
          type="button"
          disabled={!canSubmit}
          onClick={() => void run("probe")}
          className="min-h-touch-min rounded-control border border-line px-2 text-2xs text-ink disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
        >
          연결 확인
        </button>
        <button
          type="button"
          disabled={!canSubmit}
          onClick={() => void run("save")}
          className="min-h-touch-min rounded-control border border-line-strong px-2 text-2xs text-ink-strong disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
        >
          저장
        </button>
      </div>

      {outcome.kind === "busy" && <p className="text-2xs text-ink-muted">확인하고 있습니다…</p>}
      {outcome.kind === "said" && (
        <p role="status" className={cn("min-w-0 break-keep text-2xs", outcome.ok ? "text-ink" : "text-danger")}>
          {outcome.text}
        </p>
      )}
    </li>
  );
}
