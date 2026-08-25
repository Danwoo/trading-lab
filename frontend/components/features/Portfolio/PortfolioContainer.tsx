"use client";

import type { LegacyGridColumn } from "@/types/grid";
import { SplitPane } from "@/components/shared/Layout/SplitPane";
import { MasterPanel, DetailPanel } from "@/components/shared/DataPanel";
import type { DeleteConfirmInfo } from "@/components/shared/DataPanel/DetailPanel";
import { MasterGrid } from "@/components/shared/DataGrid";
import PortfolioDetailView from "./PortfolioDetailView";
import PortfolioDetailForm from "./PortfolioDetailForm";
import {
  selectPortfolioList,
  selectPortfolio,
  createPortfolio,
  updatePortfolio,
  deletePortfolio,
  selectHoldingList,
} from "@/services/portfolio/portfolioService";
import type { PortfolioOut } from "@/schemas/portfolio/portfolio";
import { useCodeStore } from "@/stores/shared/codeStore";
import { useMasterGridData } from "@/hooks/shared/useMasterGridData";
import { useExcelExport } from "@/hooks/shared/useExcelExport";
import { useMasterGridActions } from "@/hooks/shared/useMasterGridActions";
import { useWriteAccess } from "@/hooks/shared/useWriteAccess";

export default function PortfolioContainer() {
  const { getCode } = useCodeStore();
  const codeList = {
    useAt: getCode("1000"), // 사용여부
    // 보유종목 시장 — 관심종목과 같은 코드 그룹을 쓴다. `Holding.market` 은 `Watchlist.market`
    // 과 대칭이라(#328) 값의 정본도 같아야 한다: 두 화면이 다른 목록을 쓰면 같은 종목의 시장이
    // 화면마다 달라지고, 터미널의 시장 판정(resolveRegion)이 한쪽만 알아본다.
    market: getCode("5000"), // 시장
  };

  const GRID_COLUMNS: LegacyGridColumn[] = [
    { dataField: "rn", caption: "#", width: 50, dataType: "number", allowSorting: false, allowFiltering: false },
    { dataField: "portfolio_id", caption: "포트폴리오ID", width: 120 },
    { dataField: "portfolio_nm", caption: "포트폴리오명", width: 200 },
    { dataField: "sort_ordr", caption: "정렬순서", width: 90, dataType: "number" },
    {
      dataField: "use_at",
      caption: "사용여부",
      width: 100,
      lookup: {
        dataSource: codeList.useAt,
        displayExpr: "code_nm",
        valueExpr: "code",
      },
    },
    { dataField: "reg_dt", caption: "생성일시", width: 160, dataType: "datetime" },
    { dataField: "mod_dt", caption: "수정일시", width: 160, dataType: "datetime" },
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
    fetchGrid: selectPortfolioList,
    fetchData: selectPortfolio,
  });

  const { handleExcelDownload } = useExcelExport({
    dataSource,
    columns: GRID_COLUMNS,
    fileName: "portfolios",
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
    select: selectPortfolio,
    create: createPortfolio,
    update: updatePortfolio,
    delete: deletePortfolio,
  };

  // 포트폴리오 삭제는 보유종목까지 지운다(`delete_portfolio` 가 `tn_holding` 을 먼저 지우는
  // 트랜잭션) — 이슈 #356 이 짚은 3종엔 없었지만 같은 클래스라 실측해 싣는다.
  const buildDeleteConfirm = async (data: PortfolioOut): Promise<DeleteConfirmInfo> => {
    const holdings = await selectHoldingList({ portfolio_id: data.portfolio_id }, { throwOnFailure: true });
    const count = holdings?.total_count ?? 0;
    return {
      target: data.portfolio_nm,
      cascadeLines: count > 0 ? [`보유종목 ${count}건이 함께 삭제됩니다.`] : undefined,
    };
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 min-h-0 border-t">
        <SplitPane orientation="horizontal" initialSizes={[50, 50]}>
          {[
            <MasterPanel key="master" title="포트폴리오 목록" buttons={buttons}>
              <MasterGrid
                dataSource={dataSource}
                columns={GRID_COLUMNS}
                onSelectionChanged={handleSelect}
                selectedData={selectedData}
              />
            </MasterPanel>,
            <DetailPanel
              writeGated={
                writeAccess.isDenied ? { halted: ["포트폴리오 등록", "수정", "삭제", "보유종목 편집"] } : undefined
              }
              key="detail"
              title="포트폴리오 정보"
              data={selectedData}
              initialMode={selectedData ? "view" : "create"}
              isSelectLoading={isSelectLoading}
              ViewComponent={PortfolioDetailView}
              FormComponent={PortfolioDetailForm}
              viewProps={{ codeList }}
              formProps={{ codeList }}
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
