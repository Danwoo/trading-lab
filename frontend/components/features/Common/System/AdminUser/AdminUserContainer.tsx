// components/features/Common/System/AdminUser/AdminUserContainer.tsx
"use client";

import type { LegacyGridColumn } from "@/types/grid";
import { SplitPane } from "@/components/shared/Layout/SplitPane";
import { MasterPanel, DetailPanel } from "@/components/shared/DataPanel";
import type { DeleteConfirmInfo } from "@/components/shared/DataPanel/DetailPanel";
import { MasterGrid } from "@/components/shared/DataGrid";
import AdminUserDetailView from "./AdminUserDetailView";
import AdminUserDetailForm from "./AdminUserDetailForm";
import {
  selectAdminUserList,
  selectAdminUser,
  createAdminUser,
  updateAdminUser,
  deleteAdminUser,
  selectUserDeleteCascade,
} from "@/services/common/adminUserService";
import type { AdminUserOut } from "@/schemas/common/adminUser";
import { buildUserCascadeLines } from "./userCascadeLines";
import { useMasterGridData } from "@/hooks/shared/useMasterGridData";
import { useExcelExport } from "@/hooks/shared/useExcelExport";
import { useMasterGridActions } from "@/hooks/shared/useMasterGridActions";
import { useSessionContext } from "@/hooks/shared/useSessionContext";
import { renderAuthorCell } from "./authorCell";

export default function AdminUserContainer() {
  const { isSysAdmin } = useSessionContext();

  // 운영자는 자기 워크스페이스 사용자만 보이므로 워크스페이스 컬럼이 단일값 — 시스템관리자에게만 노출
  const GRID_COLUMNS: LegacyGridColumn[] = [
    { dataField: "rn", caption: "#", width: 50, dataType: "number", allowSorting: false, allowFiltering: false },
    ...(isSysAdmin
      ? [
          {
            dataField: "workspace_nm",
            caption: "워크스페이스",
            width: 150,
            allowFiltering: false,
            allowSorting: false,
          },
          { dataField: "id", caption: "사용자ID", width: 290 },
        ]
      : []),
    { dataField: "email", caption: "이메일", minWidth: 200 },
    { dataField: "name", caption: "이름", width: 150 },
    { dataField: "dept", caption: "부서", width: 150 },
    {
      dataField: "author_nm",
      caption: "권한",
      width: 180,
      allowFiltering: false,
      allowSorting: false,
      // 빈 칸은 상태를 말하지 않는다 (#355) — 권한 0건이면 「권한 없음」을 그린다.
      cellRender: renderAuthorCell,
    },
    {
      dataField: "appr_at",
      caption: "승인",
      width: 80,
      lookup: {
        dataSource: [
          { value: "Y", text: "승인" },
          { value: "N", text: "대기" },
          { value: "R", text: "거부" },
        ],
        displayExpr: "text",
        valueExpr: "value",
      },
    },
    {
      dataField: "use_at",
      caption: "사용",
      width: 80,
      lookup: {
        dataSource: [
          { value: "Y", text: "활성" },
          { value: "N", text: "비활성" },
        ],
        displayExpr: "text",
        valueExpr: "value",
      },
    },
    { dataField: "reg_dt", caption: "생성일시", width: 160, dataType: "datetime" },
    { dataField: "reg_id", caption: "생성자ID", width: 100 },
    { dataField: "mod_dt", caption: "수정일시", width: 160, dataType: "datetime" },
    { dataField: "mod_id", caption: "수정자ID", width: 100 },
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
    fetchGrid: selectAdminUserList,
    keyField: "email",
    fetchData: selectAdminUser,
  });

  const { handleExcelDownload } = useExcelExport({
    dataSource,
    columns: GRID_COLUMNS,
    fileName: "admin_users",
  });

  const buttons = useMasterGridActions({
    onCreate: handleCreate,
    onRefresh: handleRefresh,
    onExcelDownload: handleExcelDownload,
    customActions: [],
  });

  const apiService = {
    select: selectAdminUser,
    create: createAdminUser,
    update: updateAdminUser,
    delete: deleteAdminUser,
  };

  // 사용자 삭제는 앱에서 가장 크게 연쇄한다 — `deleteUserCascade`(authUtils.ts) 가 권한 배정·세션·
  // 대화 이력을 지우고, 소유한 개인 워크스페이스가 있으면 그 안의 자산까지 통째로 지운다.
  // 건수는 같은 술어로 세는 `countUserCascade` 가 삭제 직전 DB 에서 읽는다.
  const buildDeleteConfirm = async (data: AdminUserOut): Promise<DeleteConfirmInfo> => {
    const cascade = await selectUserDeleteCascade(data.email);
    // 연쇄를 못 셌으면 확인 창을 띄우지 않는다 — 가장 큰 연쇄에서 침묵은 「연쇄 없음」으로 읽힌다.
    if (!cascade) throw new Error("삭제 범위를 확인하지 못해 삭제를 진행하지 않습니다.");
    return {
      target: data.name ? `${data.name} (${data.email})` : data.email,
      cascadeLines: buildUserCascadeLines(cascade),
    };
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 min-h-0 border-t">
        <SplitPane orientation="horizontal" initialSizes={[60, 40]}>
          {[
            <MasterPanel key="master" title="사용자 목록" buttons={buttons}>
              <MasterGrid
                dataSource={dataSource}
                columns={GRID_COLUMNS}
                onSelectionChanged={handleSelect}
                selectedData={selectedData}
              />
            </MasterPanel>,
            <DetailPanel
              key="detail"
              title="사용자 정보"
              data={selectedData}
              initialMode={selectedData ? "view" : "create"}
              isSelectLoading={isSelectLoading}
              ViewComponent={AdminUserDetailView}
              FormComponent={AdminUserDetailForm}
              formProps={{}}
              defaultFormData={{ appr_at: "Y", use_at: "Y" }}
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
