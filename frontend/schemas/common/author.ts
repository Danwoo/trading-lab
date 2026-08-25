import { z } from "zod";
import { str, Field, object } from "@/lib/zod/helpers";
import { CommonEntity } from "@/schemas/common/types";

const NO_WHITESPACE = /^\S+$/;

export const AuthorSchema = object({
  author_id: Field({ min_length: 1, max_length: 20, pattern: NO_WHITESPACE }).str(),
  author_nm: str().max(200),
});

export const AuthorCreateInSchema = AuthorSchema;
export const AuthorUpdateInSchema = AuthorSchema.omit({ author_id: true });

export type Author = z.infer<typeof AuthorSchema> & { is_sys_admin?: boolean; is_protected?: boolean };
export type AuthorOut = Author & CommonEntity;

export interface AuthorsOut {
  items: AuthorOut[];
  total_count: number;
}

export interface AuthorOptionOut {
  author_id: string;
  author_nm: string;
}

export interface AuthorOptionsOut {
  items: AuthorOptionOut[];
  total_count: number;
}

export interface AuthorUsersOut {
  authorUsers: { author_id: string; user_id: string; user_nm: string; use_at: string; appr_at: string }[];
  allUsers: { user_id: string; user_nm: string; use_at: string; appr_at: string }[];
  /** 이 권한만 갖고 있어(다른 권한 0건) 삭제 시 권한 0건으로 떨어지는 사용자 수 (#356). */
  sole_author_user_count?: number;
}

export interface AuthorMenusOut {
  authorMenus: { menu_id: string; menu?: { menu_nm: string; use_at: string | null } }[];
  allMenus: { menu_id: string; menu_nm: string; menu_level: number; use_at: string | null }[];
}
