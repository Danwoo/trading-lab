// components/features/Common/System/AdminUser/AdminUserSessionGrid.tsx
"use client";

import React, { useRef, useCallback } from "react";
import { Button } from "@/components/shared/ui";
import { DetailGridPanel, DetailGridPanelRef } from "@/components/shared/DataPanel";
import { selectUserSessions, revokeUserSession } from "@/services/common/adminUserService";
import { showMessage, showToast } from "@/components/shared/Feedback";
import { getApiErrorMessage } from "@/utils/common/errors";

interface Props {
  email: string;
  height?: string;
  editable?: boolean;
}

const AdminUserSessionGrid: React.FC<Props> = ({ email, height = "250px", editable = true }) => {
  const gridRef = useRef<DetailGridPanelRef>(null);

  const handleRevoke = useCallback(
    (session: any) => {
      showMessage("강제 종료 확인", <div>선택한 세션을 강제 종료하시겠습니까?</div>, {
        type: "confirm",
        confirmText: "종료",
        cancelText: "취소",
        callback: {
          onConfirm: async () => {
            try {
              const result = await revokeUserSession(email, session.id);
              showToast(result?.message || "세션이 강제 종료되었습니다.", "success");
              gridRef.current?.refresh();
            } catch (error) {
              showToast(getApiErrorMessage(error), "error");
            }
          },
        },
      });
    },
    [email],
  );

  const GRID_COLUMNS = [
    { dataField: "rn", caption: "#", width: 50, allowSorting: false, allowFiltering: false },
    ...(editable
      ? [
          {
            dataField: "_action",
            caption: "관리",
            width: 70,
            allowSorting: false,
            allowFiltering: false,
            cellRender: (cellData: any) => (
              <Button
                text="종료"
                type="danger"
                stylingMode="outlined"
                width="100%"
                onClick={() => handleRevoke(cellData.data)}
              />
            ),
          },
        ]
      : []),
    { dataField: "createdAt", caption: "접속일시", width: 160, dataType: "datetime" as const },
    { dataField: "expiresAt", caption: "만료일시", width: 160, dataType: "datetime" as const },
    { dataField: "ipAddress", caption: "IP 주소", width: 130 },
    { dataField: "userAgent", caption: "브라우저", minWidth: 150 },
  ];

  return (
    <DetailGridPanel
      ref={gridRef}
      key={email + "_session"}
      fetchGrid={async () => selectUserSessions(email)}
      columns={GRID_COLUMNS}
      keyField="id"
      showPaging={false}
      clientSidePaging={true}
      editable={false}
      height={height}
    />
  );
};

export default React.memo(AdminUserSessionGrid);
