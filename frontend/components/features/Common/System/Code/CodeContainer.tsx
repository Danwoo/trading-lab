"use client";

import type { LegacyGridColumn } from "@/types/grid";
import { SplitPane } from "@/components/shared/Layout/SplitPane";
import { MasterPanel, DetailPanel } from "@/components/shared/DataPanel";
import { MasterGrid } from "@/components/shared/DataGrid";
import CodeDetailView from "./CodeDetailView";
import CodeDetailForm from "./CodeDetailForm";
import {
  selectCodeGroupList,
  selectCodeGroup,
  createCodeGroup,
  updateCodeGroup,
  deleteCodeGroup,
} from "@/services/common/codeService";
import { useMasterGridData } from "@/hooks/shared/useMasterGridData";
import { useExcelExport } from "@/hooks/shared/useExcelExport";
import { useMasterGridActions } from "@/hooks/shared/useMasterGridActions";

export default function CodeContainer() {
  const GRID_COLUMNS: LegacyGridColumn[] = [
    { dataField: "rn", caption: "#", width: 50, dataType: "number", allowSorting: false, allowFiltering: false },
    { dataField: "group_code", caption: "그룹코드", width: 100 },
    { dataField: "group_code_nm", caption: "그룹코드명", width: 200 },
    { dataField: "group_code_dc", caption: "그룹코드설명", minWidth: 150 },
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
    fetchGrid: selectCodeGroupList,
    fetchData: selectCodeGroup,
  });

  const { handleExcelDownload } = useExcelExport({
    dataSource,
    columns: GRID_COLUMNS,
    fileName: "code_groups",
  });

  const buttons = useMasterGridActions({
    onCreate: handleCreate,
    onRefresh: handleRefresh,
    onExcelDownload: handleExcelDownload,
    customActions: [],
  });

  const apiService = {
    select: selectCodeGroup,
    create: createCodeGroup,
    update: updateCodeGroup,
    delete: deleteCodeGroup,
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 min-h-0 border-t">
        <SplitPane orientation="horizontal" initialSizes={[60, 40]}>
          {[
            <MasterPanel key="master" title="코드 목록" buttons={buttons}>
              <MasterGrid
                dataSource={dataSource}
                columns={GRID_COLUMNS}
                onSelectionChanged={handleSelect}
                selectedData={selectedData}
              />
            </MasterPanel>,
            <DetailPanel
              key="detail"
              title="코드 정보"
              data={selectedData}
              initialMode={selectedData ? "view" : "create"}
              isSelectLoading={isSelectLoading}
              ViewComponent={CodeDetailView}
              FormComponent={CodeDetailForm}
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
