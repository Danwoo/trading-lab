// components/features/Common/System/Author/AuthorDetailView.tsx
"use client";

import { Button } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { AuthorOut } from "@/schemas/common/author";
import AuthorMenuGrid from "./AuthorMenuGrid";
import AuthorUserGrid from "./AuthorUserGrid";

interface Props {
  data: AuthorOut;
  onEdit: () => void;
  onDelete?: () => void;
}

export default function AuthorDetailView({ data, onEdit, onDelete }: Props) {
  return (
    <div className="h-full flex flex-col">
      <div className="flex-shrink-0 mb-2">
        <div className="flex gap-2 justify-end">
          <Button text="수정" onClick={onEdit} />
          {/* 보호 권한(admin/operator/user)은 삭제 불가 */}
          {onDelete && !data.is_protected && (
            <Button text="삭제" onClick={onDelete} stylingMode="outlined" type="danger" />
          )}
        </div>
      </div>

      <div className="flex-shrink-0">
        <TableGroup title="권한 정보">
          <TableRow>
            <TableCell label="권한ID">{data.author_id}</TableCell>
            <TableCell label="권한명">{data.author_nm}</TableCell>
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

      <div className="flex-1 min-h-0 flex gap-2">
        <TableGroup title="메뉴" mode="flex">
          <TableRow>
            <TableCell>
              <AuthorMenuGrid authorId={data.author_id} isSysAdmin={data.is_sys_admin} height="100%" />
            </TableCell>
          </TableRow>
        </TableGroup>
        <TableGroup title="사용자" mode="flex">
          <TableRow>
            <TableCell>
              <AuthorUserGrid authorId={data.author_id} height="100%" />
            </TableCell>
          </TableRow>
        </TableGroup>
      </div>
    </div>
  );
}
