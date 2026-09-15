// components/features/Scheduler/SchedulerMemberGrid.tsx
"use client";

import React from "react";
import { DetailGridPanel } from "@/components/shared/DataPanel";
import { selectSchedulerMembers } from "@/services/scheduler/schedulerService";

interface Props {
  schedulerId: string;
  height?: string;
  editable?: boolean;
}

const MEMBER_COLUMNS = [
  // 정본은 백엔드 `SchedulerMemberOut` 이다 — 응답에 `git_id` 라는 필드는 없다. 이름이 어긋나면
  // 열이 조용히 빈칸으로 그려질 뿐 아무도 안 알려준다.
  { dataField: "account_id", caption: "계좌주 ID", width: 160 },
  { dataField: "name", caption: "이름", width: 140 },
  { dataField: "email", caption: "이메일", minWidth: 180 },
];

// 보기/수정 공유 — 참여 멤버 읽기전용 그리드. (멤버 추가·제거는 Form 의 DualSelectGrid 가 담당)
const SchedulerMemberGrid: React.FC<Props> = ({ schedulerId, height = "250px", editable = false }) => {
  return (
    <DetailGridPanel
      key={schedulerId + "_members"}
      fetchGrid={async () => selectSchedulerMembers(schedulerId)}
      columns={MEMBER_COLUMNS}
      keyField="account_id"
      showPaging={false}
      clientSidePaging={true}
      editable={editable}
      height={height}
    />
  );
};

export default React.memo(SchedulerMemberGrid);
