// components/features/Scheduler/SchedulerDetailView.tsx
"use client";

import { Button } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { showToast, showMessage } from "@/components/shared/Feedback";
import { getApiErrorMessage } from "@/utils/common/errors";
import { runScheduler } from "@/services/scheduler/schedulerService";
import { SchedulerOut } from "@/schemas/scheduler/scheduler";
import SchedulerMemberGrid from "./SchedulerMemberGrid";

interface Props {
  data: SchedulerOut;
  onEdit: () => void;
  onDelete?: () => void;
  dayOfWeekItems?: { code: string; code_nm: string }[];
  useAtItems?: { code: string; code_nm: string }[];
  periodItems?: { code: number; code_nm: string }[];
}

export default function SchedulerDetailView({
  data,
  onEdit,
  onDelete,
  dayOfWeekItems = [],
  useAtItems = [],
  periodItems = [],
}: Props) {
  const handleRun = () => {
    showMessage("실행 확인", <div>{data.scheduler_nm} 스케줄러를 지금 실행하시겠습니까?</div>, {
      type: "confirm",
      confirmText: "실행",
      cancelText: "취소",
      callback: {
        onConfirm: async () => {
          try {
            const res = await runScheduler(data.scheduler_id);
            showToast(res?.message ?? "실행이 요청되었습니다.", res?.level ?? "success");
          } catch (error) {
            showToast(getApiErrorMessage(error), "error");
          }
        },
      },
    });
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-shrink-0 mb-2">
        <div className="flex gap-2 justify-end">
          <Button text="지금 실행" onClick={handleRun} type="success" />
          <Button text="수정" onClick={onEdit} />
          {onDelete && <Button text="삭제" onClick={onDelete} stylingMode="outlined" type="danger" />}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        <TableGroup title="기본 정보">
          <TableRow>
            <TableCell label="스케줄러ID">{data.scheduler_id}</TableCell>
            <TableCell label="스케줄러명">{data.scheduler_nm}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="요일" items={dayOfWeekItems}>
              {data.day_of_week}
            </TableCell>
            <TableCell label="주기" items={periodItems}>
              {data.period_weeks}
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="시각">
              {String(data.hour).padStart(2, "0")}:{String(data.minute).padStart(2, "0")}
            </TableCell>
            <TableCell label="사용여부" items={useAtItems}>
              {data.use_at}
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="설명" colSpan={3}>
              {data.description}
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="생성일시">{data.reg_dt}</TableCell>
            <TableCell label="생성자">{data.reg_id}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="수정일시">{data.mod_dt}</TableCell>
            <TableCell label="수정자">{data.mod_id}</TableCell>
          </TableRow>
        </TableGroup>

        <TableGroup title="참여 멤버">
          <TableRow>
            <TableCell colSpan={4}>
              <SchedulerMemberGrid schedulerId={data.scheduler_id} editable={false} />
            </TableCell>
          </TableRow>
        </TableGroup>
      </div>
    </div>
  );
}
