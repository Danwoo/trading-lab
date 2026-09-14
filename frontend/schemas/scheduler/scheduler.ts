// schemas/scheduler/scheduler.ts
import { z } from "zod";
import { CommonEntity } from "@/schemas/common/types";
import { StrRange, Field, Optional, enums, IntRange, object } from "@/lib/zod/helpers";

export const SchedulerSchema = object({
  scheduler_id: StrRange(1, 20),
  scheduler_nm: Field({ max_length: 200 }).str(),
  day_of_week: enums(["mon", "tue", "wed", "thu", "fri", "sat", "sun", "*"]),
  hour: IntRange(0, 23),
  minute: IntRange(0, 59),
  period_weeks: IntRange(1, 4),
  use_at: enums(["Y", "N"]),
  description: Optional(Field({ max_length: 500 }).str()),
});

export const SchedulerCreateInSchema = SchedulerSchema;
export const SchedulerUpdateInSchema = SchedulerSchema.omit({ scheduler_id: true });

export type Scheduler = z.infer<typeof SchedulerSchema>;
export type SchedulerOut = Scheduler & CommonEntity;
export interface SchedulersOut {
  items: SchedulerOut[];
  total_count: number;
}

// 정본은 백엔드 `SchedulerMemberOut` 이다 — `account_id`·`email` 은 응답에 항상 있다.
// 종전에는 `git_id` 라 불러 **화면이 읽는 값이 늘 undefined** 였다 (#439 F21).
export interface SchedulerMember {
  scheduler_id: string;
  account_id: string;
  email: string;
  name?: string;
}
export interface SchedulerMembersOut {
  items: SchedulerMember[];
  total_count: number;
}
