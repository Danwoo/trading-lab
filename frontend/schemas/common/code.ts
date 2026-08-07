// schemas/common/code.ts
import { z } from "zod";
import { CommonEntity } from "@/schemas/common/types";
import { enums, Field, Optional, StrRange, PositiveInt, object } from "@/lib/zod/helpers";

const NO_WHITESPACE = /^\S+$/;

// ==================== 코드 그룹 ====================

export const CodeGroupSchema = object({
  group_code: Field({ min_length: 1, max_length: 5, pattern: NO_WHITESPACE }).str(),
  group_code_nm: StrRange(1, 200),
  group_code_dc: Optional(Field({ max_length: 200 }).str()),
  use_at: enums(["Y", "N"]),
});

// CRUD 스키마
export const CodeGroupCreateInSchema = CodeGroupSchema;
export const CodeGroupUpdateInSchema = CodeGroupSchema.omit({ group_code: true });

// 타입 정의
export type CodeGroup = z.infer<typeof CodeGroupSchema>;
export type CodeGroupOut = CodeGroup & CommonEntity & { codes?: CodeOut[] };
export interface CodeGroupsOut {
  items: CodeGroupOut[];
  total_count: number;
}

// ==================== 코드 ====================

export const CodeSchema = object({
  group_code: Field({ min_length: 1, max_length: 5, pattern: NO_WHITESPACE }).str(),
  code: Field({ min_length: 1, max_length: 20, pattern: NO_WHITESPACE }).str(),
  code_nm: StrRange(1, 200),
  code_nm_eng: Optional(Field({ max_length: 200 }).str()),
  code_dc: Optional(Field({ max_length: 200 }).str()),
  sort_ordr: PositiveInt(),
  use_at: enums(["Y", "N"]),
});

// CRUD 스키마
export const CodeCreateInSchema = CodeSchema.omit({ group_code: true });
export const CodeUpdateInSchema = CodeSchema.omit({ group_code: true, code: true });

// 타입 정의
export type Code = z.infer<typeof CodeSchema>;
export type CodeOut = Code &
  CommonEntity & {
    group_code_nm?: string;
    group_code_dc?: string;
  };
export interface CodesOut {
  items: CodeOut[];
  total_count: number;
}
