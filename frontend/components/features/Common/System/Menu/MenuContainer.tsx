// components/features/Common/System/Menu/MenuContainer.tsx
"use client";

import { useState, useEffect } from "react";
import type { LegacyGridColumn } from "@/types/grid";
import { SplitPane } from "@/components/shared/Layout/SplitPane";
import { MasterPanel, DetailPanel } from "@/components/shared/DataPanel";
import type { DeleteConfirmInfo } from "@/components/shared/DataPanel/DetailPanel";
import { MasterGrid } from "@/components/shared/DataGrid";
import MenuDetailView from "./MenuDetailView";
import MenuDetailForm from "./MenuDetailForm";
import {
  selectMenuList,
  selectMenu,
  createMenu,
  updateMenu,
  deleteMenu,
  selectMenuParentOptions,
  selectMenuAuthors,
} from "@/services/common/menuService";
import type { MenuOut } from "@/schemas/common/menu";
import { useMasterGridData } from "@/hooks/shared/useMasterGridData";
import { useExcelExport } from "@/hooks/shared/useExcelExport";
import { useMasterGridActions } from "@/hooks/shared/useMasterGridActions";
import { useSessionContext } from "@/hooks/shared/useSessionContext";

export default function MenuContainer() {
  const [parentOptions, setParentOptions] = useState<{ value: string; label: string; use_at: string }[]>([]);
  const { isSysAdmin } = useSessionContext();

  useEffect(() => {
    selectMenuParentOptions().then(setParentOptions);
  }, []);

  const GRID_COLUMNS: LegacyGridColumn[] = [
    { dataField: "rn", caption: "#", width: 50, dataType: "number", allowSorting: false, allowFiltering: false },
    { dataField: "ParentGroup", caption: "상위메뉴", width: 120, allowFiltering: false, allowSorting: false },
    { dataField: "menu_id", caption: "메뉴ID", width: 150 },
    { dataField: "menu_nm", caption: "메뉴명", minWidth: 150 },
    { dataField: "menu_level", caption: "레벨", width: 90, dataType: "number" },
    { dataField: "sort_ordr", caption: "순서", width: 90, dataType: "number" },
    { dataField: "url", caption: "URL", minWidth: 150 },
    { dataField: "author_nm", caption: "권한", minWidth: 150, allowFiltering: false, allowSorting: false },
    {
      dataField: "use_at",
      caption: "사용여부",
      width: 90,
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
    fetchGrid: selectMenuList,
    fetchData: selectMenu,
  });

  const { handleExcelDownload } = useExcelExport({
    dataSource,
    columns: GRID_COLUMNS,
    fileName: "menus",
  });

  const buttons = useMasterGridActions({
    onCreate: handleCreate,
    onRefresh: handleRefresh,
    onExcelDownload: handleExcelDownload,
    customActions: [],
  });

  const apiService = {
    select: selectMenu,
    create: createMenu,
    update: updateMenu,
    delete: deleteMenu,
  };

  // 이 메뉴에 걸린 권한 매핑 건수 — 삭제가 `authorMenu.deleteMany` 로 지우는 것과 같은 조회다.
  const buildDeleteConfirm = async (data: MenuOut): Promise<DeleteConfirmInfo> => {
    const authorsResult = await selectMenuAuthors(data.menu_id);
    const count = authorsResult?.total_count ?? 0;
    return {
      target: `${data.menu_nm} (${data.menu_id})`,
      cascadeLines: count > 0 ? [`권한 매핑 ${count}건이 함께 삭제됩니다.`] : undefined,
    };
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 min-h-0 border-t">
        <SplitPane orientation="horizontal" initialSizes={[60, 40]}>
          {[
            <MasterPanel key="master" title="메뉴 목록" buttons={buttons}>
              <MasterGrid
                dataSource={dataSource}
                columns={GRID_COLUMNS}
                onSelectionChanged={handleSelect}
                selectedData={selectedData}
              />
            </MasterPanel>,
            <DetailPanel
              key="detail"
              title="메뉴 정보"
              data={selectedData}
              initialMode={selectedData ? "view" : "create"}
              isSelectLoading={isSelectLoading}
              ViewComponent={MenuDetailView}
              FormComponent={MenuDetailForm}
              formProps={{ parentOptions, isSysAdmin }}
              defaultFormData={{ use_at: "Y", sort_ordr: 1 }}
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
