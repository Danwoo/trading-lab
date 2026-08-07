// components/features/Common/System/Menu/MenuDetailView.tsx
"use client";

import { Button } from "@/components/shared/ui";
import { TableRow, TableCell, TableGroup } from "@/components/shared/Layout";
import { Icon } from "@/components/shared/ui/primitives/icons";
import { MenuOut } from "@/schemas/common/menu";
import MenuAuthorGrid from "./MenuAuthorGrid";

interface Props {
  data: MenuOut;
  onEdit: () => void;
  onDelete?: () => void;
}

const levelLabel = (level?: number | null) => {
  if (level === 1) return "폴더";
  if (level === 2) return "프로그램";
  return String(level);
};

export default function MenuDetailView({ data, onEdit, onDelete }: Props) {
  return (
    <div className="h-full flex flex-col">
      <div className="flex-shrink-0 mb-2">
        <div className="flex gap-2 justify-end">
          <Button text="수정" onClick={onEdit} />
          {onDelete && !data.is_protected && (
            <Button text="삭제" onClick={onDelete} stylingMode="outlined" type="danger" />
          )}
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-auto">
        <TableGroup title="메뉴 정보">
          <TableRow>
            <TableCell label="메뉴ID">{data.menu_id}</TableCell>
            <TableCell label="메뉴명">{data.menu_nm}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="레벨">{levelLabel(data.menu_level)}</TableCell>
            <TableCell label="정렬순서">{data.sort_ordr}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="상위메뉴">{data.ParentGroup}</TableCell>
            <TableCell label="사용여부">{data.use_at === "Y" ? "사용" : "미사용"}</TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="URL" colSpan={3}>
              {data.url}
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell label="아이콘" colSpan={3}>
              {data.icon ? (
                <span className="flex items-center gap-2">
                  <Icon name={data.icon} size={18} />
                  {data.icon}
                </span>
              ) : (
                "-"
              )}
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

        <TableGroup title="소속 권한">
          <TableRow>
            <TableCell colSpan={4}>
              <MenuAuthorGrid menuId={data.menu_id} />
            </TableCell>
          </TableRow>
        </TableGroup>
      </div>
    </div>
  );
}
