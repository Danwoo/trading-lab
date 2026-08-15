// schemas/terminal/ingest.ts
import { z } from "zod";
import { StrRange, Optional, Field, enums, object } from "@/lib/zod/helpers";

/** 백엔드 `ingest_schema.py` 의 `JobKind` 와 값이 같아야 한다 (backend 가 SoT). */
export const JOB_KINDS = ["instrument_master", "daily_bar", "minute_bar"] as const;

/** 백엔드 `ingest_schema.py` 의 `RunStatus`. `rate_limited` 는 실패가 아니라 이어받을 지점이 있는 상태다(설계 §7.2). */
export const RUN_STATUSES = ["queued", "running", "succeeded", "failed", "rate_limited"] as const;

export type JobKind = (typeof JOB_KINDS)[number];
export type RunStatus = (typeof RUN_STATUSES)[number];

/**
 * 수동 적재 요청. `scope` 형식이 잡 종류마다 다르다 — `instrument_master` 는 시장 하나(`"NASDAQ"`),
 * 캔들 잡은 시장 + 종목 목록(`"NASDAQ:AAPL,MSFT"`). 이 규칙의 정본은 백엔드
 * `IngestRunCreateIn` docstring 이고, 여기서는 형식 검사만 한다 — 무엇이 유효한 시장·종목인지는
 * 백엔드가 판정한다(프론트가 시장 목록을 복제하면 두 벌이 갈린다).
 */
export const IngestRunCreateInSchema = object({
  source: StrRange(1, 30),
  job_kind: enums(JOB_KINDS),
  scope: StrRange(1, 200),
  period_from: Optional(Field({ max_length: 10 }).str()),
  period_to: Optional(Field({ max_length: 10 }).str()),
});

export type IngestRunCreateIn = z.infer<typeof IngestRunCreateInSchema>;

/** 백엔드 `IngestRunOut` 중 화면이 읽는 필드만. 감사 컬럼은 목록에 쓰지 않아 옮기지 않는다. */
export interface IngestRunOut {
  run_id: number;
  source: string;
  job_kind: string;
  scope: string | null;
  period_from: string | null;
  period_to: string | null;
  status: string;
  cursor: string | null;
  written_rows: number | null;
  skipped_rows: number | null;
  failed_reason: string | null;
  started_dt: string | null;
  finished_dt: string | null;
  reg_dt: string | null;
}

export interface IngestRunsOut {
  items: IngestRunOut[];
  total_count: number;
}
