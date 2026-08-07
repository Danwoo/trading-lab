// components/features/Common/System/Author/AuthorContainer.tsx
"use client";

import type { LegacyGridColumn } from "@/types/grid";
import { SplitPane } from "@/components/shared/Layout/SplitPane";
import { MasterPanel, DetailPanel } from "@/components/shared/DataPanel";
import { MasterGrid } from "@/components/shared/DataGrid";
import AuthorDetailView from "./AuthorDetailView";
import AuthorDetailForm from "./AuthorDetailForm";
import {
  selectAuthorList,
  selectAuthor,
  createAuthor,
  updateAuthor,
  deleteAuthor,
} from "@/services/common/authorService";
import { useMasterGridData } from "@/hooks/shared/useMasterGridData";
import { useExcelExport } from "@/hooks/shared/useExcelExport";
import { useMasterGridActions } from "@/hooks/shared/useMasterGridActions";

export default function AuthorContainer() {
  const GRID_COLUMNS: LegacyGridColumn[] = [
    { dataField: "rn", caption: "#", width: 50, dataType: "number", allowSorting: false, allowFiltering: false },
    { dataField: "author_id", caption: "권한ID", width: 200 },
    { dataField: "author_nm", caption: "권한명", minWidth: 150 },
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
    fetchGrid: selectAuthorList,
    fetchData: selectAuthor,
  });

  const { handleExcelDownload } = useExcelExport({
    dataSource,
    columns: GRID_COLUMNS,
    fileName: "authors",
  });

  // 권한관리는 시스템관리자 전용 메뉴 — 등록/수정/삭제 모두 허용.
  const buttons = useMasterGridActions({
    onCreate: handleCreate,
    onRefresh: handleRefresh,
    onExcelDownload: handleExcelDownload,
    customActions: [],
  });

  const apiService = {
    select: selectAuthor,
    create: createAuthor,
    update: updateAuthor,
    delete: deleteAuthor,
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 min-h-0 border-t">
        <SplitPane orientation="horizontal" initialSizes={[60, 40]}>
          {[
            <MasterPanel key="master" title="권한 목록" buttons={buttons}>
              <MasterGrid
                dataSource={dataSource}
                columns={GRID_COLUMNS}
                onSelectionChanged={handleSelect}
                selectedData={selectedData}
              />
            </MasterPanel>,
            <DetailPanel
              key="detail"
              title="권한 정보"
              data={selectedData}
              initialMode={selectedData ? "view" : "create"}
              isSelectLoading={isSelectLoading}
              ViewComponent={AuthorDetailView}
              FormComponent={AuthorDetailForm}
              formProps={{}}
              onComplete={handleCompleteWithRefresh}
              apiService={apiService}
            />,
          ]}
        </SplitPane>
      </div>
    </div>
  );
}
