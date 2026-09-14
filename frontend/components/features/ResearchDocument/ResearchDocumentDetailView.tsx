"use client";

import { Button, FileListDisplay } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { ResearchDocumentOut, getResearchDocumentStatusLabel } from "@/schemas/researchDocument/researchDocument";

interface Props {
  data: ResearchDocumentOut;
  onDelete?: () => void;
}

// 색인 상태별 배지 색 — 색만으로 구분하지 않도록 라벨 텍스트를 항상 함께 표시
const STATUS_BADGE_CLASS: Record<string, string> = {
  indexed: "bg-green-100 text-green-800",
  // mock-indexed·empty 는 둘 다 "검색되지 않는 문서"라 같은 주의색 — 구분은 라벨 텍스트가 한다
  "mock-indexed": "bg-amber-100 text-amber-800",
  empty: "bg-amber-100 text-amber-800",
  failed: "bg-red-100 text-red-800",
  uploaded: "bg-gray-100 text-gray-700",
};

function StatusBadge({ status }: { status?: string }) {
  const cls = (status && STATUS_BADGE_CLASS[status]) || "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-sm font-medium ${cls}`}>
      {getResearchDocumentStatusLabel(status)}
    </span>
  );
}

// 리서치 문서는 등록·삭제만 지원 — 수정 버튼 없음(백엔드 수정 엔드포인트 부재)
export default function ResearchDocumentDetailView({ data, onDelete }: Props) {
  return (
    <div className="h-full flex flex-col">
      <div className="flex-shrink-0 mb-2">
        <div className="flex gap-2 justify-end">
          {onDelete && <Button text="삭제" onClick={onDelete} stylingMode="outlined" type="danger" />}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        <TableGroup title="기본 정보">
          <TableRow>
            <TableCell label="문서 제목" colSpan={3}>
              {data.doc_title}
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="색인 상태">
              <StatusBadge status={data.status} />
            </TableCell>
            <TableCell label="청크 수">{data.chunk_count ?? "-"}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="문서 파일" colSpan={3}>
              <FileListDisplay atchFileId={data.atch_file_id} fileSn={data.file_sn} />
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="생성일시" dataType="datetime">
              {data.reg_dt}
            </TableCell>
            <TableCell label="생성자">{data.reg_id}</TableCell>
          </TableRow>
        </TableGroup>
      </div>
    </div>
  );
}
