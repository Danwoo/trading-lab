// components/shared/DataGrid/DualSelectGrid.tsx
"use client";

import { useCallback, useMemo, useState } from "react";
// 배럴이 아니라 직접 경로 — `@/components/shared/ui` 는 FileListDisplay 를 거쳐
// services/common/fileService → env.ts 까지 끌고 온다(#341 ② 배럴 fan-out).
import { Button } from "@/components/shared/ui/Button";
import { DataTable } from "@/components/shared/DataTable";
import { useStaticGridSource } from "@/hooks/shared/legacyGridSource";
import { toGridColumns } from "./legacyColumns";
import type { LegacyGridColumn } from "@/types/grid";

// 좌/우 목록은 전체를 한 화면에 보여준다(이관 전 `paging={{ enabled: false }}`) — 페이저가
// 없으므로 페이지 크기는 "사실상 무제한"이면 된다.
const UNPAGED_SIZE = 100000;

interface Props {
  title: string;
  leftTitle: string;
  rightTitle: string;
  leftData: any[];
  rightData: any[];
  leftColumns: LegacyGridColumn[];
  rightColumns: LegacyGridColumn[];
  leftKeyExpr: string;
  rightKeyExpr: string;
  loading?: boolean;
  height?: string;
  fillHeight?: boolean;
  className?: string;
  /** 이 필드가 "Y" 가 아닌 행을 흐리게 그린다(사용 안 함 표시). */
  inactiveExpr?: string;
  onAdd: () => void | Promise<void>;
  onRemove: () => void | Promise<void>;
  onLeftSelectionChanged: (selectedKeys: string[]) => void;
  onRightSelectionChanged: (selectedKeys: string[]) => void;
}

/**
 * 좌/우 두 목록 사이에서 항목을 옮기는 그리드 — #341 로 `DataTable` 커널로 이관됐다.
 *
 * 이관 전에는 DevExtreme 그리드 인스턴스를 ref 로 잡아 `deselectAll()` 을 명령형으로 불렀다.
 * 여기서는 선택 키를 이 컴포넌트가 state 로 갖고 옮긴 뒤 비운다 — 화면에 보이는 것과 상태가
 * 항상 같은 출처에서 나온다.
 */
export function DualSelectGrid({
  title,
  leftTitle,
  rightTitle,
  leftData,
  rightData,
  leftColumns,
  rightColumns,
  leftKeyExpr,
  rightKeyExpr,
  loading = false,
  height = "16rem",
  fillHeight = false,
  className = "mt-4",
  inactiveExpr,
  onAdd,
  onRemove,
  onLeftSelectionChanged,
  onRightSelectionChanged,
}: Props) {
  const [leftKeys, setLeftKeys] = useState<Array<string | number>>([]);
  const [rightKeys, setRightKeys] = useState<Array<string | number>>([]);

  const leftTable = useStaticGridSource(leftData, UNPAGED_SIZE);
  const rightTable = useStaticGridSource(rightData, UNPAGED_SIZE);

  const leftGridColumns = useMemo(() => toGridColumns<any>(leftColumns), [leftColumns]);
  const rightGridColumns = useMemo(() => toGridColumns<any>(rightColumns), [rightColumns]);

  const rowClassName = useCallback(
    (row: any) => (inactiveExpr && row[inactiveExpr] !== "Y" ? "text-gray-400" : undefined),
    [inactiveExpr],
  );

  const handleAdd = async () => {
    await onAdd();
    setLeftKeys([]);
    onLeftSelectionChanged([]);
  };

  const handleRemove = async () => {
    await onRemove();
    setRightKeys([]);
    onRightSelectionChanged([]);
  };

  const renderSide = (
    label: string,
    table: typeof leftTable,
    columns: typeof leftGridColumns,
    keyExpr: string,
    keys: Array<string | number>,
    setKeys: (next: Array<string | number>) => void,
    notify: (next: string[]) => void,
  ) => (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex-shrink-0 border border-b-0 border-gray-300 bg-gray-300 p-2 text-sm font-medium text-gray-700">
        {label}
      </div>
      <div className="min-h-0 flex-1">
        <DataTable<any>
          table={table}
          columns={columns}
          keyField={keyExpr}
          height="100%"
          showPager={false}
          selectionMode="multiple"
          selectedKeys={keys}
          onSelectionChange={(nextKeys) => {
            setKeys(nextKeys);
            notify(nextKeys.map(String));
          }}
          rowClassName={inactiveExpr ? rowClassName : undefined}
        />
      </div>
    </div>
  );

  return (
    <div className={fillHeight ? "flex h-full flex-col" : className}>
      <h3
        className={`border border-b-0 border-gray-300 bg-gray-300 p-2 text-sm font-medium text-gray-700${fillHeight ? " flex-shrink-0" : ""}`}
      >
        {title}
      </h3>
      <div
        className={`flex gap-2 border border-gray-300 p-2${fillHeight ? " min-h-0 flex-1" : ""}`}
        style={fillHeight ? undefined : { height }}
      >
        {loading ? (
          <div className="flex flex-1 items-center justify-center text-gray-500">로딩 중...</div>
        ) : (
          renderSide(leftTitle, leftTable, leftGridColumns, leftKeyExpr, leftKeys, setLeftKeys, onLeftSelectionChanged)
        )}

        <div className="flex flex-col items-center justify-center gap-2">
          <Button
            icon="arrowright"
            hint="오른쪽으로 옮기기"
            stylingMode="contained"
            type="success"
            onClick={handleAdd}
          />
          <Button
            icon="arrowleft"
            hint="왼쪽으로 되돌리기"
            stylingMode="contained"
            type="danger"
            onClick={handleRemove}
          />
        </div>

        {renderSide(
          rightTitle,
          rightTable,
          rightGridColumns,
          rightKeyExpr,
          rightKeys,
          setRightKeys,
          onRightSelectionChanged,
        )}
      </div>
    </div>
  );
}
