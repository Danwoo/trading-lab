"use client";

import { useState } from "react";

import { probeDataKey, saveDataKey, type DataKeyStatus } from "@/services/dataKey/dataKeyService";
import { getApiErrorMessage } from "@/utils/common/errors/apierrors";
import { cn } from "@/components/shared/ui/primitives/cn";

/** 화면이 값을 되읽지 않는다 — 입력칸은 넣는 자리일 뿐, 저장된 값은 어디서도 보이지 않는다. */
type Outcome = { kind: "idle" } | { kind: "busy" } | { kind: "said"; ok: boolean; text: string };

/**
 * `canWrite` 는 **권한 판정이 아니라 그 결과를 그리는 것**이다 — 판정은 백엔드가 한다
 * (`PUT /data-key`·`POST /data-key/probe` 는 `require_role(ROLE_ADMIN)`, #344). 여기서 입력칸을
 * 내리는 이유는 감추기 위해서가 아니라 **누를 때마다 403 이 되는 버튼을 내밀지 않기 위해서**다.
 */
export function DataKeyRow({ row, canWrite, onSaved }: { row: DataKeyStatus; canWrite: boolean; onSaved: () => void }) {
  const [value, setValue] = useState("");
  const [outcome, setOutcome] = useState<Outcome>({ kind: "idle" });

  const busy = outcome.kind === "busy";
  const typed = value.trim().length > 0;
  const canSubmit = typed && !busy;
  // **「설정됨」과 「유효함」은 다르다** (#445 B-16·F30). 저장된 키는 값을 다시 칠 수 없어
  // 종전에는 확인 버튼이 영영 잠겨 있었다 — 통하는지 알 길이 없었다. 빈 값으로 확인을 부르면
  // 서버가 저장된 것을 쓴다. 값을 쳤으면 그 값이 이긴다(저장 전 확인은 종전 그대로).
  const canProbe = (typed || row.filled) && !busy;
  // 저장된 것을 쓸 때만 그렇게 말한다 — 저장된 키가 없는 행까지 그 문구를 쓰면 거짓이다.
  const probesStored = !typed && row.filled;

  /** 확인·저장이 같은 실패 처리를 쓴다 — 사유를 삼키지 않는다. */
  const run = async (what: "probe" | "save") => {
    setOutcome({ kind: "busy" });
    try {
      if (what === "probe") {
        const probe = await probeDataKey(row.source, value, row.setting);
        if (probe === null) throw new Error("확인 결과를 받지 못했습니다");
        setOutcome({ kind: "said", ok: probe.ok, text: probe.detail });
        return;
      }
      const saved = await saveDataKey(row.source, value, row.setting);
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

      {canWrite && (
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
            disabled={!canProbe}
            onClick={() => void run("probe")}
            title={probesStored ? "저장된 키로 확인합니다" : "친 값으로 확인합니다"}
            className="min-h-touch-min rounded-control border border-line px-2 text-2xs text-ink disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
          >
            {probesStored ? "저장된 키 확인" : "연결 확인"}
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
      )}

      {outcome.kind === "busy" && <p className="text-2xs text-ink-muted">확인하고 있습니다…</p>}
      {outcome.kind === "said" && (
        <p role="status" className={cn("min-w-0 break-keep text-2xs", outcome.ok ? "text-ink" : "text-danger")}>
          {outcome.text}
        </p>
      )}
    </li>
  );
}
