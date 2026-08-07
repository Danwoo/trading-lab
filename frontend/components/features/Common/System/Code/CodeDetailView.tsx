"use client";

import { Button } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import CodeListGrid from "./CodeDetailGrid";
import { CodeGroupOut } from "@/schemas/common/code";

interface Props {
  data: CodeGroupOut;
  onEdit: () => void;
  onDelete?: () => void;
}

export default function CodeGroupDetailView({ data, onEdit, onDelete }: Props) {
  return (
    <div className="h-full flex flex-col">
      <div className="flex-shrink-0 mb-2">
        <div className="flex gap-2 justify-end">
          <Button text="수정" onClick={onEdit} />
          {onDelete && <Button text="삭제" onClick={onDelete} stylingMode="outlined" type="danger" />}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        <TableGroup title="그룹코드 정보">
          <TableRow>
            <TableCell label="그룹코드">{data.group_code}</TableCell>
            <TableCell label="그룹코드명">{data.group_code_nm}</TableCell>
          </TableRow>

          <TableRow>
            <TableCell label="그룹코드설명" colSpan={3}>
              <div className="whitespace-pre-wrap leading-relaxed" style={{ minHeight: "60px", verticalAlign: "top" }}>
                {data.group_code_dc}
              </div>
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="사용여부">{data.use_at}</TableCell>
            <TableCell label="" />
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

        <TableGroup title="코드 목록">
          <TableRow>
            <TableCell colSpan={4}>
              <CodeListGrid groupCode={data.group_code} editable={false} height="500px" />
            </TableCell>
          </TableRow>
        </TableGroup>
      </div>
    </div>
  );
}
