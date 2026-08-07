"use client";

import { useCallback, useMemo, useState } from "react";
// 직접 경로 import — 각 배럴(`Layout`/`DataPanel`)은 이 화면에 필요 없는 형제 컴포넌트도
// 함께 물고 있어(예: `DataPanel` 배럴 → `SelectGridPanel` → `@/components/shared/ui` 배럴
// → `FileListDisplay`/`FileUploader`), 배럴 경유 시 번들과 모듈 그래프가 불필요하게 커진다.
import { SplitPane } from "@/components/shared/Layout/SplitPane";
import { DataTable } from "@/components/shared/DataTable/DataTable";
import { MasterPanel } from "@/components/shared/DataPanel/MasterPanel";
import { DetailPanel } from "@/components/shared/DataPanel/DetailPanel";
import WatchlistDetailView from "./WatchlistDetailView";
import WatchlistDetailForm from "./WatchlistDetailForm";
import {
  selectWatchlistList,
  selectWatchlist,
  createWatchlist,
  updateWatchlist,
  deleteWatchlist,
} from "@/services/watchlist/watchlistService";
import { useCodeStore } from "@/stores/shared/codeStore";
import { useServerTable } from "@/hooks/shared/useServerTable";
import { useTableExport } from "@/hooks/shared/useTableExport";
import { useMasterGridActions } from "@/hooks/shared/useMasterGridActions";
import { getApiErrorMessage } from "@/utils/common/errors";
import { showToast } from "@/components/shared/Feedback";
import { getCodeName } from "@/utils/common/codeUtils";
import type { GridColumn } from "@/types/grid";
import type { WatchlistOut } from "@/schemas/watchlist/watchlist";

// 이슈 #242 O5 — 그리드 커널(O1)로 이주. 컬럼 집합·순서, 서버 필터·정렬·페이징 결과,
// 엑셀 헤더·행 수, 공통코드 룩업 표시는 이주 전과 같아야 한다(시안 「바뀌면 안 되는 것」).
// 오른쪽 상세 폼(WatchlistDetailForm/View)의 DevExtreme 의존은 #341 로 함께 사라졌다.
export default function WatchlistContainer() {
  const { getCode } = useCodeStore();
  const codeList = {
    market: getCode("5000"), // 관심종목 시장
    sector: getCode("5001"), // 관심종목 섹터
    currency: getCode("5002"), // 관심종목 통화
    priority: getCode("5003"), // 관심종목 우선순위
    useAt: getCode("1000"), // 사용여부
  };

  const GRID_COLUMNS: GridColumn<WatchlistOut>[] = useMemo(
    () => [
      { field: "rn", caption: "#", width: 50, dataType: "number", sortable: false, filterable: false },
      { field: "ticker", caption: "티커", width: 100 },
      { field: "issuer_nm", caption: "종목명", minWidth: 150 },
      { field: "market", caption: "시장", width: 100, render: (row) => getCodeName(row.market, codeList.market) },
      { field: "sector", caption: "섹터", width: 120, render: (row) => getCodeName(row.sector, codeList.sector) },
      {
        field: "currency",
        caption: "통화",
        width: 80,
        render: (row) => getCodeName(row.currency, codeList.currency),
      },
      { field: "target_price", caption: "목표가", width: 120, dataType: "number" },
      { field: "alert_price", caption: "알림가", width: 120, dataType: "number" },
      {
        field: "priority",
        caption: "우선순위",
        width: 90,
        render: (row) => getCodeName(row.priority, codeList.priority),
      },
      {
        field: "use_at",
        caption: "사용여부",
        width: 100,
        render: (row) => getCodeName(row.use_at, codeList.useAt),
      },
      { field: "reg_dt", caption: "생성일시", width: 160, dataType: "datetime" },
      { field: "mod_dt", caption: "수정일시", width: 160, dataType: "datetime" },
    ],
    [codeList.market, codeList.sector, codeList.currency, codeList.priority, codeList.useAt],
  );

  const table = useServerTable<WatchlistOut>({ fetchGrid: selectWatchlistList });

  const [selectedData, setSelectedData] = useState<WatchlistOut | null>(null);
  const [selectedKeys, setSelectedKeys] = useState<Array<string | number>>([]);
  const [isSelectLoading, setIsSelectLoading] = useState(false);

  // selectionMode="single" 은 DataTable 이 체크박스 열을 하나 더 그린다 — 옛 MasterGrid 는
  // 체크박스 없이 행 클릭으로만 선택했다(포커스 행 방식). 컬럼 계약(12개, 시안 「바뀌면 안
  // 되는 것」)을 지키려면 selectionMode="none" + onRowClick 조합으로 같은 동작을 낸다.
  // selectedKeys 는 강조 표시(bg-blue-50)에는 여전히 쓰인다 — DataTableBody 가 selectionMode
  // 와 무관하게 selectedKeySet 으로 행 배경을 계산하기 때문이다.
  const handleRowClick = useCallback((row: WatchlistOut) => {
    setSelectedKeys(row.rn !== undefined ? [row.rn] : []);
    setSelectedData(row);
  }, []);

  const handleCreate = useCallback(() => {
    setSelectedData(null);
    setSelectedKeys([]);
  }, []);

  const handleRefresh = useCallback(async () => {
    table.reload();
    if (!selectedData) return;

    setIsSelectLoading(true);
    try {
      const latest = await selectWatchlist(selectedData);
      setSelectedData(latest);
    } catch (error) {
      showToast(getApiErrorMessage(error), "error");
      setSelectedData(null);
      setSelectedKeys([]);
    } finally {
      setIsSelectLoading(false);
    }
  }, [table, selectedData]);

  const handleCompleteWithRefresh = useCallback(
    (data: WatchlistOut | null, action?: "create" | "update" | "delete") => {
      setSelectedData(data);
      if (action === "delete") setSelectedKeys([]);
      if (action) table.reload();
    },
    [table],
  );

  const { handleExcelDownload } = useTableExport<WatchlistOut>({
    columns: GRID_COLUMNS,
    // 화면에 보이는 페이지가 아니라 현재 필터·정렬 조건에 맞는 전체 행을 받는다(기존
    // useExcelExport/exportDataGrid 와 같은 범위 — 페이징은 무시하고 필터·정렬은 반영).
    fetchAll: async () => {
      const response = await selectWatchlistList({ filter: table.query.filter, sort: table.query.sort });
      return response?.items ?? [];
    },
    fileName: "watchlists",
  });

  const buttons = useMasterGridActions({
    onCreate: handleCreate,
    onRefresh: handleRefresh,
    onExcelDownload: handleExcelDownload,
    customActions: [],
  });

  const apiService = {
    select: selectWatchlist,
    create: createWatchlist,
    update: updateWatchlist,
    delete: deleteWatchlist,
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 min-h-0 border-t">
        <SplitPane orientation="horizontal" initialSizes={[60, 40]} minSizes={[20, 20]}>
          {[
            <MasterPanel key="master" title="관심종목 목록" buttons={buttons}>
              <DataTable table={table} columns={GRID_COLUMNS} selectedKeys={selectedKeys} onRowClick={handleRowClick} />
            </MasterPanel>,
            <DetailPanel
              key="detail"
              title="관심종목 정보"
              data={selectedData}
              initialMode={selectedData ? "view" : "create"}
              isSelectLoading={isSelectLoading}
              ViewComponent={WatchlistDetailView}
              FormComponent={WatchlistDetailForm}
              viewProps={{ codeList }}
              formProps={{ codeList }}
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
