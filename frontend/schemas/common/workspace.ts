// schemas/common/workspace.ts
import { z } from "zod";
import { CommonEntity } from "@/schemas/common/types";
import { domain, enums, Field, int, StrRange, object } from "@/lib/zod/helpers";

// ==================== 워크스페이스 ====================

const NO_WHITESPACE = /^\S+$/;

export const WorkspaceSchema = object({
  id: int(),
  workspace_code: Field({ min_length: 1, max_length: 30, pattern: NO_WHITESPACE }).str(),
  workspace_nm: StrRange(1, 200),
  use_at: enums(["Y", "N"]),
});

export const WorkspaceCreateInSchema = WorkspaceSchema.omit({ id: true });
export const WorkspaceUpdateInSchema = WorkspaceSchema.omit({ id: true, workspace_code: true });

export type Workspace = z.infer<typeof WorkspaceSchema>;
export type WorkspaceOut = Workspace & CommonEntity;
export interface WorkspacesOut {
  items: WorkspaceOut[];
  total_count: number;
}

export interface WorkspaceOptionOut {
  id: number;
  workspace_code: string;
  workspace_nm: string;
}
export interface WorkspaceOptionsOut {
  items: WorkspaceOptionOut[];
  total_count: number;
}

// ==================== 워크스페이스 도메인 ====================

export const WorkspaceDomainSchema = object({
  workspace_id: int(),
  domain: domain(100),
});

export const WorkspaceDomainCreateInSchema = WorkspaceDomainSchema.omit({ workspace_id: true });

export type WorkspaceDomain = z.infer<typeof WorkspaceDomainSchema>;
export type WorkspaceDomainOut = WorkspaceDomain & CommonEntity & { workspace_nm?: string };
export interface WorkspaceDomainsOut {
  items: WorkspaceDomainOut[];
  total_count: number;
}

// ==================== 워크스페이스 메뉴 ====================

export interface WorkspaceMenuItem {
  menu_id: string;
  menu_nm: string;
  menu_level: number;
  use_at: string | null;
}

export interface WorkspaceMenusOut {
  workspaceMenus: { menu_id: string; reg_dt: string | null; menu?: { menu_nm: string; use_at: string | null } }[];
  allMenus: WorkspaceMenuItem[];
}

// ==================== 워크스페이스 사용자 (read-only) ====================

export interface WorkspaceUserOut {
  rn: number;
  email: string;
  name: string | null;
  dept: string | null;
  use_at: string;
  appr_at: string;
  reg_dt: string;
  author_nm: string;
}

export interface WorkspaceUsersOut {
  items: WorkspaceUserOut[];
  total_count: number;
}
