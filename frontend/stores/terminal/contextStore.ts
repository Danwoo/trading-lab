"use client";

import { create } from "zustand";
import type { TerminalContext } from "@/types/terminal/context";

/**
 * 스토어 본체 — `useTerminalContext.ts`(읽기)와 `contextActions.ts`(쓰기) 밖에서
 * import 하지 않는다. 패널 폴더에서 이 모듈을 직접 import 하면 §3.2 문맥 경계 위반이다.
 */
export const useContextStore = create<TerminalContext>(() => ({
  symbol: null,
  interval: "1d",
  range: null,
  selectedBotId: null,
}));
