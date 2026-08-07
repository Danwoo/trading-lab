import { z } from "zod";
import { str, Optional, Field, int, object, enums } from "@/lib/zod/helpers";
import { CommonEntity } from "@/schemas/common/types";

const NO_WHITESPACE = /^\S+$/;

export const MenuSchema = object({
  menu_id: Field({ min_length: 1, max_length: 20, pattern: NO_WHITESPACE }).str(),
  menu_nm: str().max(200),
  menu_level: int(),
  sort_ordr: int(),
  upper_menu_id: Optional(str().max(20)),
  url: Optional(str().max(400)),
  use_at: enums(["Y", "N"]),
  icon: Optional(str().max(50)),
});

export const MenuCreateInSchema = MenuSchema;
export const MenuUpdateInSchema = MenuSchema.omit({ menu_id: true });

export type Menu = z.infer<typeof MenuSchema>;
export type MenuOut = Menu & CommonEntity & { ParentGroup?: string; is_protected?: boolean };

export interface MenusOut {
  items: MenuOut[];
  total_count: number;
}

export interface MenuParentOptionOut {
  value: string;
  label: string;
  use_at: string;
}
