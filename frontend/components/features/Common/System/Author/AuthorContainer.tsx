// components/features/Common/System/Author/AuthorContainer.tsx
"use client";

import type { LegacyGridColumn } from "@/types/grid";
import { SplitPane } from "@/components/shared/Layout/SplitPane";
import { MasterPanel, DetailPanel } from "@/components/shared/DataPanel";
import type { DeleteConfirmInfo } from "@/components/shared/DataPanel/DetailPanel";
import { MasterGrid } from "@/components/shared/DataGrid";
import AuthorDetailView from "./AuthorDetailView";
import AuthorDetailForm from "./AuthorDetailForm";
import {
  selectAuthorList,
  selectAuthor,
  createAuthor,
  updateAuthor,
  deleteAuthor,
  selectAuthorUsers,
  selectAuthorMenus,
} from "@/services/common/authorService";
import type { AuthorOut } from "@/schemas/common/author";
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

  // 삭제가 실제로 지우는 것 — DB FK 를 짐작하지 않고 그 권한의 사용자·메뉴 매핑을 그대로 센다.
  const buildDeleteConfirm = async (data: AuthorOut): Promise<DeleteConfirmInfo> => {
    const [usersResult, menusResult] = await Promise.all([
      selectAuthorUsers(data.author_id),
      selectAuthorMenus(data.author_id),
    ]);
    const userCount = usersResult?.authorUsers.length ?? 0;
    const menuCount = menusResult?.authorMenus.length ?? 0;
    const soleUserCount = usersResult?.sole_author_user_count ?? 0;

    const cascadeLines: string[] = [];
    const parts = [
      userCount > 0 ? `사용자 배정 ${userCount}건` : null,
      menuCount > 0 ? `메뉴 매핑 ${menuCount}건` : null,
    ].filter((part): part is string => part !== null);
    if (parts.length > 0) cascadeLines.push(`${parts.join(", ")}이 함께 삭제됩니다.`);
    if (soleUserCount > 0)
      cascadeLines.push(`이 권한만 가진 사용자 ${soleUserCount}명이 제품에 들어갈 수 없게 됩니다.`);

    return {
      target: `${data.author_nm} (${data.author_id})`,
      cascadeLines: cascadeLines.length ? cascadeLines : undefined,
    };
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
              deleteConfirm={buildDeleteConfirm}
            />,
          ]}
        </SplitPane>
      </div>
    </div>
  );
}
