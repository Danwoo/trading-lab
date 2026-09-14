"use client";

import { Button, FileListDisplay } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { formatNumber } from "@/utils/common/formatters";
import { WatchlistOut } from "@/schemas/watchlist/watchlist";

interface Props {
  data: WatchlistOut;
  onEdit?: () => void;
  onDelete?: () => void;
  /** 역할이 쓰기를 막았을 때의 사유 — 주면 수정·삭제가 비활성으로 서고 title 이 이것을 말한다 (#341). */
  writeDeniedHint?: string;
  codeList?: any;
}

export default function WatchlistDetailView({ data, onEdit, onDelete, writeDeniedHint, codeList }: Props) {
  return (
    <div className="h-full flex flex-col">
      <div className="flex-shrink-0 mb-2">
        <div className="flex gap-2 justify-end">
          {/* 막힌 계정에는 비활성으로 선다 — 판정은 `DataPanel/DetailPanel` 의 `writeGated` 가 한다 (#341). */}
          {onEdit && <Button text="수정" onClick={onEdit} disabled={Boolean(writeDeniedHint)} hint={writeDeniedHint} />}
          {onDelete && (
            <Button
              text="삭제"
              onClick={onDelete}
              stylingMode="outlined"
              type="danger"
              disabled={Boolean(writeDeniedHint)}
              hint={writeDeniedHint}
            />
          )}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        <TableGroup title="기본 정보">
          <TableRow>
            <TableCell label="티커">{data.ticker}</TableCell>
            <TableCell label="종목명">{data.issuer_nm}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="시장" items={codeList?.market}>
              {data.market}
            </TableCell>
            <TableCell label="섹터" items={codeList?.sector}>
              {data.sector}
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="통화" items={codeList?.currency}>
              {data.currency}
            </TableCell>
            <TableCell label="우선순위" items={codeList?.priority}>
              {data.priority}
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="목표가">{formatNumber(data.target_price)}</TableCell>
            <TableCell label="알림가">{formatNumber(data.alert_price)}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="사용여부" items={codeList?.useAt}>
              {data.use_at}
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="비고" colSpan={3}>
              <div className="whitespace-pre-wrap leading-relaxed" style={{ minHeight: "80px", verticalAlign: "top" }}>
                {data.memo}
              </div>
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="리서치 문서" colSpan={3}>
              <FileListDisplay atchFileId={data.atch_file_id} />
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="생성일시" dataType="datetime">
              {data.reg_dt}
            </TableCell>
            <TableCell label="생성자">{data.reg_id}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="수정일시" dataType="datetime">
              {data.mod_dt}
            </TableCell>
            <TableCell label="수정자">{data.mod_id}</TableCell>
          </TableRow>
        </TableGroup>
      </div>
    </div>
  );
}
