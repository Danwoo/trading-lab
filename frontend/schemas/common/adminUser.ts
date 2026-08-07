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
