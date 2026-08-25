// components/features/Common/System/AdminUser/authorCell.tsx
import type { ReactNode } from "react";
import { NO_AUTHOR_LABEL } from "@/constants/accountAuthor";

/**
 * 사용자 목록의 「권한」 칸 — 빈 칸은 상태를 말하지 않는다 (#355).
 *
 * 권한 0건은 승인된 계정이면 「그대로 두면 안 되는 것」이라 `--caution` 으로, 승인 전이면 정상이라
 * 흐리게 낸다. 컨테이너의 컬럼 정의 밖으로 꺼낸 이유는 이 판정을 렌더 테스트가 직접 잡게 하기
 * 위해서다(컨테이너 전체는 세션·그리드 데이터까지 물고 있다).
 */
export function renderAuthorCell({ data, value }: { data: { appr_at?: string }; value: unknown }): ReactNode {
  if (typeof value === "string" && value.trim()) return value;
  return <span className={data.appr_at === "Y" ? "text-caution" : "text-ink-muted"}>{NO_AUTHOR_LABEL}</span>;
}
