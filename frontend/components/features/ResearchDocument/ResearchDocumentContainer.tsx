"use client";

import type { LegacyGridColumn } from "@/types/grid";
import { SplitPane } from "@/components/shared/Layout/SplitPane";
import { MasterPanel, DetailPanel } from "@/components/shared/DataPanel";
import type { DeleteConfirmInfo } from "@/components/shared/DataPanel/DetailPanel";
import { MasterGrid } from "@/components/shared/DataGrid";
import ResearchDocumentDetailView from "./ResearchDocumentDetailView";
import ResearchDocumentDetailForm from "./ResearchDocumentDetailForm";
import {
  selectResearchDocumentList,
  selectResearchDocument,
  createResearchDocument,
  deleteResearchDocument,
} from "@/services/researchDocument/researchDocumentService";
import { getResearchDocumentStatusLabel, type ResearchDocumentOut } from "@/schemas/researchDocument/researchDocument";
import { useMasterGridData } from "@/hooks/shared/useMasterGridData";
import { useExcelExport } from "@/hooks/shared/useExcelExport";
import { useMasterGridActions } from "@/hooks/shared/useMasterGridActions";

export default function ResearchDocumentContainer() {
  const GRID_COLUMNS: LegacyGridColumn[] = [
    { dataField: "rn", caption: "#", width: 50, dataType: "number", allowSorting: false, allowFiltering: false },
    { dataField: "doc_title", caption: "문서 제목", minWidth: 200 },
    {
      dataField: "status",
      caption: "색인 상태",
      // 가장 긴 라벨 "모의색인(검색불가)"이 잘리지 않을 만큼 — 잘리면 "검색불가" 경고가 사라진다
      width: 140,
      // 백엔드 enum 을 사람이 읽는 라벨로 (색인완료/모의색인(검색불가)/텍스트없음/실패/대기)
      customizeText: (cellInfo) => getResearchDocumentStatusLabel(cellInfo.value),
    },
    { dataField: "chunk_count", caption: "청크 수", width: 90, dataType: "number" },
    { dataField: "reg_dt", caption: "생성일시", width: 160, dataType: "datetime" },
    { dataField: "reg_id", caption: "생성자", width: 120 },
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
    fetchGrid: selectResearchDocumentList,
    fetchData: selectResearchDocument,
  });

  const { handleExcelDownload } = useExcelExport({
    dataSource,
    columns: GRID_COLUMNS,
    fileName: "research-documents",
  });

  const buttons = useMasterGridActions({
    onCreate: handleCreate,
    onRefresh: handleRefresh,
    onExcelDownload: handleExcelDownload,
    customActions: [],
  });

  // 리서치 문서는 등록·삭제만 지원 (백엔드에 수정 엔드포인트 없음)
  const apiService = {
    select: selectResearchDocument,
    create: createResearchDocument,
    delete: deleteResearchDocument,
  };

  // 삭제는 연쇄가 없다(단건 DELETE, 실측: research_document_repository.delete_research_document) — 대상 이름만 말한다.
  const buildDeleteConfirm = (data: ResearchDocumentOut): DeleteConfirmInfo => ({
    target: data.doc_title,
  });

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 min-h-0 border-t">
        <SplitPane orientation="horizontal" initialSizes={[60, 40]}>
          {[
            <MasterPanel key="master" title="리서치 문서 목록" buttons={buttons}>
              <MasterGrid
                dataSource={dataSource}
                columns={GRID_COLUMNS}
                onSelectionChanged={handleSelect}
                selectedData={selectedData}
              />
            </MasterPanel>,
            <DetailPanel
              key="detail"
              title="리서치 문서 정보"
              data={selectedData}
              initialMode={selectedData ? "view" : "create"}
              isSelectLoading={isSelectLoading}
              ViewComponent={ResearchDocumentDetailView}
              FormComponent={ResearchDocumentDetailForm}
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
