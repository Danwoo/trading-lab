"use client";

import { useEffect, ReactNode } from "react";
import { useCodeStore } from "@/stores/shared/codeStore";

export default function MainLayout({ children }: { children: ReactNode }) {
  const { getGroupCodes } = useCodeStore();

  // 코드 데이터 로드
  useEffect(() => {
    getGroupCodes();
  }, [getGroupCodes]);

  return <>{children}</>;
}
