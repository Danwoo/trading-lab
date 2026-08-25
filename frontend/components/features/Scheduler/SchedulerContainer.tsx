// components/features/Scheduler/SchedulerContainer.tsx
"use client";

import { useEffect, useState } from "react";
import type { LegacyGridColumn } from "@/types/grid";
import { SplitPane } from "@/components/shared/Layout/SplitPane";
import { MasterPanel, DetailPanel } from "@/components/shared/DataPanel";
import type { DeleteConfirmInfo } from "@/components/shared/DataPanel/DetailPanel";
import { MasterGrid } from "@/components/shared/DataGrid";
import SchedulerDetailView from "./SchedulerDetailView";
import SchedulerDetailForm from "./SchedulerDetailForm";
import {
  selectSchedulerList,
  selectScheduler,
  createScheduler,
  updateScheduler,
  deleteScheduler,
  selectHolders,
  selectSchedulerMembers,
} from "@/services/scheduler/schedulerService";
import type { SchedulerOut } from "@/schemas/scheduler/scheduler";
import { HolderInfo } from "@/schemas/devActivity/devActivity";
import { useCodeStore } from "@/stores/shared/codeStore";
import { useMasterGridData } from "@/hooks/shared/useMasterGridData";
import { useExcelExport } from "@/hooks/shared/useExcelExport";
import { useMasterGridActions } from "@/hooks/shared/useMasterGridActions";
import { useWriteAccess } from "@/hooks/shared/useWriteAccess";

const DAY_OF_WEEK_ITEMS = [
  { code: "mon", code_nm: "월" },
  { code: "tue", code_nm: "화" },
  { code: "wed", code_nm: "수" },
  { code: "thu", code_nm: "목" },
  { code: "fri", code_nm: "금" },
  { code: "sat", code_nm: "토" },
  { code: "sun", code_nm: "일" },
  { code: "*", code_nm: "매일" },
];

const PERIOD_ITEMS = [
  { code: 1, code_nm: "주간" },
  { code: 2, code_nm: "격주" },
  { code: 4, code_nm: "월간" },
];

export default function SchedulerContainer() {
  const [holders, setHolders] = useState<HolderInfo[]>([]);
  const { getCode } = useCodeStore();
  const useAtItems = getCode("1000"); // 사용여부

  useEffect(() => {
    selectHolders()
      .then(setHolders)
      .catch(() => setHolders([]));
  }, []);

  const GRID_COLUMNS: LegacyGridColumn[] = [
    { dataField: "rn", caption: "#", width: 50, dataType: "number", allowSorting: false, allowFiltering: false },
    { dataField: "scheduler_id", caption: "스케줄러ID", width: 160 },
    { dataField: "scheduler_nm", caption: "스케줄러명", minWidth: 180 },
    {
      dataField: "day_of_week",
      caption: "요일",
      width: 80,
      lookup: { dataSource: DAY_OF_WEEK_ITEMS, displayExpr: "code_nm", valueExpr: "code" },
    },
    { dataField: "hour", caption: "시", width: 60, dataType: "number" },
    { dataField: "minute", caption: "분", width: 60, dataType: "number" },
    {
      dataField: "period_weeks",
      caption: "주기",
      width: 90,
      lookup: { dataSource: PERIOD_ITEMS, displayExpr: "code_nm", valueExpr: "code" },
    },
    {
      dataField: "use_at",
      caption: "사용여부",
      width: 90,
      lookup: { dataSource: useAtItems, displayExpr: "code_nm", valueExpr: "code" },
    },
    { dataField: "reg_dt", caption: "생성일시", width: 160, dataType: "datetime" },
    { dataField: "reg_id", caption: "생성자ID", width: 120 },
    { dataField: "mod_dt", caption: "수정일시", width: 160, dataType: "datetime" },
    { dataField: "mod_id", caption: "수정자ID", width: 120 },
  ];

  const {
    dataSource,
    selectedData,
    isSelectLoading,
    handleSelect,
    handleCreate,
    handleRefresh,
    handleCompleteWithRefresh,
  } = useMasterGridData({
    fetchGrid: selectSchedulerList,
    fetchData: selectScheduler,
  });

  const { handleExcelDownload } = useExcelExport({
    dataSource,
    columns: GRID_COLUMNS,
    fileName: "scheduler",
  });

  // 등록은 `require_role` 이 걸린 쓰기다 — 막힌 계정에는 「등록」이 비활성으로 서고 title 이
  // 사유를 말한다. 상세 패널의 배너가 왜 막혔고 어떻게 여는지를 잇는다 (#341).
  const writeAccess = useWriteAccess();
  const buttons = useMasterGridActions({
    onCreate: handleCreate,
    writeGated: writeAccess.isDenied,
    onRefresh: handleRefresh,
    onExcelDownload: handleExcelDownload,
    customActions: [],
  });

  const apiService = {
    select: selectScheduler,
    create: createScheduler,
    update: updateScheduler,
    delete: deleteScheduler,
  };

  // 스케줄러 삭제는 구성원 배정까지 지운다(`delete_scheduler` 가 `tn_scheduler_member` 를 먼저
  // 지우는 트랜잭션) — 이슈 #356 이 짚은 3종엔 없었지만 같은 클래스라 실측해 싣는다.
  const buildDeleteConfirm = async (data: SchedulerOut): Promise<DeleteConfirmInfo> => {
    const members = await selectSchedulerMembers(data.scheduler_id);
    const count = members?.total_count ?? 0;
    return {
      target: data.scheduler_nm,
      cascadeLines: count > 0 ? [`구성원 배정 ${count}건이 함께 삭제됩니다.`] : undefined,
    };
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 min-h-0 border-t">
        <SplitPane orientation="horizontal" initialSizes={[60, 40]}>
          {[
            <MasterPanel key="master" title="스케줄러 목록" buttons={buttons}>
              <MasterGrid
                dataSource={dataSource}
                columns={GRID_COLUMNS}
                onSelectionChanged={handleSelect}
                selectedData={selectedData}
              />
            </MasterPanel>,
            <DetailPanel
              writeGated={
                writeAccess.isDenied
                  ? { halted: ["스케줄러 등록", "수정", "삭제", "지금 실행", "구성원 편집"] }
                  : undefined
              }
              key="detail"
              title="스케줄러 정보"
              data={selectedData}
              initialMode={selectedData ? "view" : "create"}
              isSelectLoading={isSelectLoading}
              ViewComponent={SchedulerDetailView}
              FormComponent={SchedulerDetailForm}
              viewProps={{ dayOfWeekItems: DAY_OF_WEEK_ITEMS, useAtItems, periodItems: PERIOD_ITEMS }}
              formProps={{
                holders,
                dayOfWeekItems: DAY_OF_WEEK_ITEMS,
                useAtItems,
                periodItems: PERIOD_ITEMS,
              }}
              defaultFormData={{ day_of_week: "mon", hour: 9, minute: 0, period_weeks: 1, use_at: "Y" }}
              onComplete={handleCompleteWithRefresh}
              apiService={apiService}
              deleteConfirm={buildDeleteConfirm}
            />,
          ]}
        </SplitPane>
      </div>
    </div>
  );
}
