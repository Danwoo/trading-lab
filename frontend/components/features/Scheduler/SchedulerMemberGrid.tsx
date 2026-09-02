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
  // 같은 필드를 형제 화면(`SchedulerDetailForm`)이 부르는 이름과 맞춘다 — 옛 제품의 낱말이었다.
  { dataField: "git_id", caption: "계좌주 ID", width: 160 },
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
      keyField="git_id"
      showPaging={false}
      clientSidePaging={true}
      editable={editable}
      height={height}
    />
  );
};

export default React.memo(SchedulerMemberGrid);
