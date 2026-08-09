import type { IngestRunOut } from "@/schemas/terminal/ingest";

export type RunTone = "pending" | "running" | "done" | "resumable" | "failed";

export interface RunStatusView {
  label: string;
  tone: RunTone;
  /** 그 상태에서 사람이 알아야 할 한 줄. 없으면 `null` — 지어내지 않는다. */
  note: string | null;
}

/**
 * 적재 상태를 사람 말로 옮긴다. **`rate_limited` 를 실패와 같은 칸에 두지 않는 것이 이 함수의
 * 존재 이유다** — 설계 §7.2 에서 한도 소진은 "지금까지 받은 것을 커밋하고 `cursor` 를 남긴
 * 상태"라 다음 실행이 이어받는다. 실패로 보이면 사람이 처음부터 다시 돌리게 되고, 그게 바로
 * 남은 한도를 태우는 행동이다.
 */
export function describeRunStatus(status: string, cursor: string | null): RunStatusView {
  switch (status) {
    case "queued":
      return { label: "대기 중", tone: "pending", note: null };
    case "running":
      return { label: "실행 중", tone: "running", note: null };
    case "succeeded":
      return { label: "완료", tone: "done", note: null };
    case "rate_limited":
      return {
        label: "한도 소진",
        tone: "resumable",
        note: cursor
          ? `여기까지 받았습니다: ${cursor} — 다시 넣으면 이어서 받습니다`
          : "받은 곳까지는 저장됐습니다 — 다시 넣으면 이어서 받습니다",
      };
    case "failed":
      return { label: "실패", tone: "failed", note: null };
    default:
      // 백엔드가 새 상태를 늘렸는데 화면이 모를 때. 삼키지 않고 원문을 그대로 보여준다.
      return { label: status, tone: "pending", note: "이 화면이 모르는 상태입니다" };
  }
}

/**
 * "무엇을 얼마나 받았나" 한 줄. **`null` 과 `0` 을 가른다** — 아직 안 돌아 값이 없는 것과 돌았는데
 * 0건인 것은 다르고, 그 둘을 뭉개면 "적재가 됐는데 왜 비어 있나"를 추적할 수 없다.
 */
export function describeRunRows(run: Pick<IngestRunOut, "written_rows" | "skipped_rows">): string {
  const parts: string[] = [];
  if (run.written_rows !== null) parts.push(`받음 ${run.written_rows.toLocaleString("ko-KR")}`);
  if (run.skipped_rows !== null) parts.push(`건너뜀 ${run.skipped_rows.toLocaleString("ko-KR")}`);
  return parts.length > 0 ? parts.join(" · ") : "—";
}

/** 잡 종류별 `scope` 입력 형식 안내. 정본은 백엔드 `IngestRunCreateIn` docstring 이다. */
export function scopePlaceholder(jobKind: string): string {
  return jobKind === "instrument_master" ? "시장 하나 — 예: KOSPI" : "시장 + 종목 — 예: KOSPI:005930,000660";
}

/** 기간을 쓰는 잡인지. 종목마스터는 시점 스냅샷이라 기간이 없다. */
export function usesPeriod(jobKind: string): boolean {
  return jobKind !== "instrument_master";
}
