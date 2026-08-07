// components/features/Common/System/Workspace/WorkspaceContainer.tsx
"use client";

import type { LegacyGridColumn } from "@/types/grid";
import { SplitPane } from "@/components/shared/Layout/SplitPane";
import { MasterPanel, DetailPanel } from "@/components/shared/DataPanel";
import { MasterGrid } from "@/components/shared/DataGrid";
import WorkspaceDetailView from "./WorkspaceDetailView";
import WorkspaceDetailForm from "./WorkspaceDetailForm";
import {
  selectWorkspaceList,
  selectWorkspace,
  createWorkspace,
  updateWorkspace,
} from "@/services/common/workspaceService";
import { useMasterGridData } from "@/hooks/shared/useMasterGridData";
import { useExcelExport } from "@/hooks/shared/useExcelExport";
import { useMasterGridActions } from "@/hooks/shared/useMasterGridActions";
import { isOEM } from "@/utils/common/edition";

export default function WorkspaceContainer() {
  const GRID_COLUMNS: LegacyGridColumn[] = [
    { dataField: "rn", caption: "#", width: 50, dataType: "number", allowSorting: false, allowFiltering: false },
    { dataField: "id", caption: "워크스페이스ID", width: 80, dataType: "number" },
    { dataField: "workspace_code", caption: "워크스페이스코드", width: 150 },
    { dataField: "workspace_nm", caption: "워크스페이스명", minWidth: 200 },
    {
      dataField: "use_at",
      caption: "사용여부",
      width: 100,
      lookup: {
        dataSource: [
          { value: "Y", text: "사용" },
          { value: "N", text: "미사용" },
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
    fetchGrid: selectWorkspaceList,
    keyField: "id",
    fetchData: selectWorkspace,
  });

  const { handleExcelDownload } = useExcelExport({
    dataSource,
    columns: GRID_COLUMNS,
    fileName: "workspaces",
  });

  const buttons = useMasterGridActions({
    // OEM: 활성 공용 워크스페이스는 정확히 1개여야 함(signup 불변식). 추가 생성 차단 위해 등록 버튼 숨김.
    onCreate: isOEM() ? undefined : handleCreate,
    onRefresh: handleRefresh,
    onExcelDownload: handleExcelDownload,
    customActions: [],
  });

  // delete 없음: 워크스페이스는 영구 보존, 폐쇄 시 use_at='N' 으로 soft delete
  const apiService = {
    select: selectWorkspace,
    create: createWorkspace,
    update: updateWorkspace,
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 min-h-0 border-t">
        <SplitPane orientation="horizontal" initialSizes={[60, 40]}>
          {[
            <MasterPanel key="master" title="워크스페이스 목록" buttons={buttons}>
              <MasterGrid
                dataSource={dataSource}
                columns={GRID_COLUMNS}
                onSelectionChanged={handleSelect}
                selectedData={selectedData}
              />
            </MasterPanel>,
            <DetailPanel
              key="detail"
              title="워크스페이스 정보"
              data={selectedData}
              initialMode={selectedData ? "view" : "create"}
              isSelectLoading={isSelectLoading}
              ViewComponent={WorkspaceDetailView}
              FormComponent={WorkspaceDetailForm}
              formProps={{}}
              defaultFormData={{ use_at: "Y" }}
              onComplete={handleCompleteWithRefresh}
              apiService={apiService}
            />,
          ]}
        </SplitPane>
      </div>
    </div>
  );
}
