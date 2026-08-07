"use client";

import { create } from "zustand";
import { selectCodeGroupList } from "@/services/common/codeService";
import { Code } from "@/schemas/common/code";
import { getApiErrorMessage } from "@/utils/common/errors";
import { showToast } from "@/components/shared/Feedback";

interface CodeStore {
  codes: Record<string, Code[]>;
  getGroupCodes: () => Promise<void>;
  getCode: (groupCode: string) => Code[];
}

export const useCodeStore = create<CodeStore>((set, get) => ({
  codes: {},

  getGroupCodes: async () => {
    try {
      const res = await selectCodeGroupList({});
      const groups = (res?.items ?? []).filter((g) => g.use_at === "Y");

      const codes = groups.reduce(
        (acc, group) => {
          acc[group.group_code] = (group.codes ?? [])
            .filter((c) => c.use_at === "Y")
            .sort((a, b) => (a.sort_ordr || 0) - (b.sort_ordr || 0));
          return acc;
        },
        {} as Record<string, Code[]>,
      );

      set({ codes });
    } catch (error: any) {
      const errorMessage = getApiErrorMessage(error);
      showToast(errorMessage, "error");
    }
  },

  getCode: (groupCode: string) => get().codes[groupCode] || [],
}));
