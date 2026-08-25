import { z } from "zod";
import { str, int, email, Optional, object, enums } from "@/lib/zod/helpers";
import { CommonEntity } from "@/schemas/common/types";

export const AdminUserSchema = object({
  email: email().max(100),
  name: Optional(str().max(100)),
  dept: Optional(str().max(50)),
  workspace_id: Optional(int()),
  use_at: enums(["Y", "N"]),
  appr_at: enums(["Y", "N", "R"]),
});

export const AdminUserUpdateInSchema = AdminUserSchema.omit({ email: true }).extend({
  password: Optional(str(8).max(72)),
});

export const AdminUserCreateInSchema = AdminUserSchema.extend({
  password: str(8).max(72),
});

export type AdminUser = z.infer<typeof AdminUserSchema>;
export type AdminUserCreate = z.infer<typeof AdminUserCreateInSchema>;
export type AdminUserOut = AdminUser & CommonEntity & { id: string; workspace_nm?: string | null };

export interface AdminUsersOut {
  items: AdminUserOut[];
  total_count: number;
}

export interface UserSessionOut {
  rn: number;
  id: string;
  ipAddress: string;
  userAgent: string;
  createdAt: string | null;
  expiresAt: string | null;
}

export interface UserSessionsOut {
  items: UserSessionOut[];
  total_count: number;
}

/**
 * 사용자 삭제가 함께 지우는 것 — `countUserCascade`(authUtils.ts) 가 `deleteUserCascade` 와
 * 같은 술어로 센 값이다. 삭제 확인 창(#356)이 읽는다.
 */
export interface UserDeleteCascadeOut {
  author_member_count: number;
  workspace_member_count: number;
  session_count: number;
  chat_history_count: number;
  email_log_count: number;
  /** 주간 활동요약 수신자 등록(`tn_scheduler_member.account_id`) — 사용자 축. 소유 워크스페이스 안의 것은 `owned_workspace_counts` 가 센다 */
  scheduler_member_count: number;
  /** 소유한 개인 워크스페이스 — 있으면 통째로 지워진다 */
  owned_personal_workspaces: { id: number; workspace_nm: string }[];
  /** 위 워크스페이스들 안의 `public` 테이블별 행 수 (`WORKSPACE_SCOPED_PUBLIC_TABLES` 순서) */
  owned_workspace_counts: Record<string, number>;
}

// 사용자 선택 피커용 경량 옵션 (워크스페이스 범위)
export interface UserOption {
  user_id: string;
  email: string;
  name: string;
  dept: string;
  workspace_nm: string;
}

export interface UserOptionsOut {
  items: UserOption[];
  total_count: number;
}
