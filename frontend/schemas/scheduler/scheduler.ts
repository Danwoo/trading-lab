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

export interface SchedulerMember {
  scheduler_id: string;
  git_id: string;
  email?: string;
  name?: string;
}
export interface SchedulerMembersOut {
  items: SchedulerMember[];
  total_count: number;
}
