// components/features/Common/System/Workspace/WorkspaceDetailView.tsx
"use client";

import { Button } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { WorkspaceOut } from "@/schemas/common/workspace";
import WorkspaceDomainGrid from "./WorkspaceDomainGrid";
import WorkspaceMenuGrid from "./WorkspaceMenuGrid";
import WorkspaceUserGrid from "./WorkspaceUserGrid";
import { useSessionContext } from "@/hooks/shared/useSessionContext";
import { isOEM } from "@/utils/common/edition";

interface Props {
  data: WorkspaceOut;
  onEdit: () => void;
}

export default function WorkspaceDetailView({ data, onEdit }: Props) {
  const { isSysAdmin } = useSessionContext();

  return (
    <div className="h-full flex flex-col overflow-auto">
      <div className="flex-shrink-0 mb-2">
        <div className="flex gap-2 justify-end">
          <Button text="수정" onClick={onEdit} />
        </div>
      </div>

      <TableGroup title="워크스페이스 정보">
        <TableRow>
          <TableCell label="워크스페이스ID">{data.id}</TableCell>
          <TableCell label="워크스페이스코드">{data.workspace_code}</TableCell>
        </TableRow>
        <TableRow>
          <TableCell label="워크스페이스명">{data.workspace_nm}</TableCell>
          <TableCell label="사용여부">{data.use_at === "Y" ? "사용" : "미사용"}</TableCell>
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

      {/* OEM: 도메인 매핑 미사용 — 숨김 */}
      {!isOEM() && (
        <TableGroup title="이메일 도메인">
          <TableRow>
            <TableCell colSpan={4}>
              <WorkspaceDomainGrid workspaceId={data.id} editable={false} height="500px" />
            </TableCell>
          </TableRow>
        </TableGroup>
      )}

      <TableGroup title="메뉴">
        <TableRow>
          <TableCell colSpan={4}>
            <WorkspaceMenuGrid workspaceId={data.id} height="500px" />
          </TableCell>
        </TableRow>
      </TableGroup>

      {isSysAdmin && (
        <TableGroup title="사용자">
          <TableRow>
            <TableCell colSpan={4}>
              <WorkspaceUserGrid workspaceId={data.id} height="500px" />
            </TableCell>
          </TableRow>
        </TableGroup>
      )}
    </div>
  );
}
