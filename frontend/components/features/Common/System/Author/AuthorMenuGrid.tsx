// components/features/Common/System/Author/AuthorMenuGrid.tsx
"use client";

import React from "react";
import type { LegacyGridColumn } from "@/types/grid";
import { DetailGridPanel } from "@/components/shared/DataPanel";
import { selectAuthorMenus } from "@/services/common/authorService";

interface Props {
  authorId: string;
  isSysAdmin?: boolean;
  height?: string;
}

const GRID_COLUMNS: LegacyGridColumn[] = [
  { dataField: "menu_id", caption: "메뉴ID" },
  { dataField: "menu_nm", caption: "메뉴명" },
];

const AuthorMenuGrid: React.FC<Props> = ({ authorId, isSysAdmin = false, height = "300px" }) => {
  if (isSysAdmin) {
    return (
      <div className="flex items-center justify-center text-gray-500" style={{ height }}>
        시스템관리자 권한은 모든 메뉴에 접근할 수 있습니다.
      </div>
    );
  }

  return (
    <DetailGridPanel
      key={authorId + "_menu"}
      fetchGrid={async () => {
        const result = await selectAuthorMenus(authorId);
        if (!result) return null;
        const items = result.authorMenus.map((m) => ({
          menu_id: m.menu_id,
          menu_nm: m.menu?.menu_nm ?? m.menu_id,
          use_at: m.menu?.use_at ?? null,
        }));
        return { items, total_count: items.length };
      }}
      columns={GRID_COLUMNS}
      keyField="menu_id"
      showPaging={false}
      clientSidePaging={true}
      editable={false}
      inactiveExpr="use_at"
      height={height}
    />
  );
};

export default React.memo(AuthorMenuGrid);
