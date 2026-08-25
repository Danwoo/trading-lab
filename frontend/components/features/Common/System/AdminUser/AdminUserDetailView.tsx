// components/features/Common/System/AdminUser/AdminUserDetailView.tsx
"use client";

import { Button } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { AdminUserOut } from "@/schemas/common/adminUser";
import AdminUserAuthorGrid from "./AdminUserAuthorGrid";
import AdminUserSessionGrid from "./AdminUserSessionGrid";
import { useSessionContext } from "@/hooks/shared/useSessionContext";

interface Props {
  data: AdminUserOut;
  onEdit: () => void;
  onDelete?: () => void;
}

export default function AdminUserDetailView({ data, onEdit, onDelete }: Props) {
  const { isSysAdmin } = useSessionContext();
  return (
    <div className="h-full flex flex-col">
      <div className="flex-shrink-0 mb-2">
        <div className="flex gap-2 justify-end">
          <Button text="수정" onClick={onEdit} />
          {onDelete && <Button text="삭제" onClick={onDelete} stylingMode="outlined" type="danger" />}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        <TableGroup title="사용자 정보">
          {isSysAdmin && (
            <TableRow>
              <TableCell label="사용자 ID" colSpan={3}>
                {data.id}
              </TableCell>
            </TableRow>
          )}
          <TableRow>
            <TableCell label="이메일">{data.email}</TableCell>
            <TableCell label="이름">{data.name}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="부서">{data.dept}</TableCell>
            <TableCell label="워크스페이스">{data.workspace_nm}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="승인여부">
              {data.appr_at === "Y" ? "승인" : data.appr_at === "R" ? "거부" : "대기"}
            </TableCell>
            <TableCell label="사용여부">{data.use_at === "Y" ? "활성" : "비활성"}</TableCell>
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

        <TableGroup title="소속 권한">
          <TableRow>
            <TableCell colSpan={4}>
              <AdminUserAuthorGrid email={data.email} apprAt={data.appr_at} editable={false} />
            </TableCell>
          </TableRow>
        </TableGroup>

        <TableGroup title="활성 세션">
          <TableRow>
            <TableCell colSpan={4}>
              <AdminUserSessionGrid email={data.email} editable={false} />
            </TableCell>
          </TableRow>
        </TableGroup>
      </div>
    </div>
  );
}
