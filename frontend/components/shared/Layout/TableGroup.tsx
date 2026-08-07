// components/shared/Layout/TableGroup.tsx
"use client";

import { ReactNode, createContext, useContext } from "react";

export type TableGroupMode = "table" | "flex";
export const TableGroupContext = createContext<TableGroupMode>("table");
export const useTableGroupMode = () => useContext(TableGroupContext);

interface Props {
  title?: ReactNode;
  children: ReactNode;
  collapsible?: boolean;
  defaultExpanded?: boolean;
  className?: string;
  titleWrapperClassName?: string;
  titleTextClassName?: string;
  tableClassName?: string;
  colWidths?: string[];
  pairCount?: number;
  contentClassName?: string;
  mode?: TableGroupMode;
}

export function TableGroup({
  title,
  children,
  collapsible = false,
  defaultExpanded = true,
  className,
  titleWrapperClassName = "bg-gray-300 border border-gray-300 border-b-0 p-2",
  titleTextClassName = "font-medium text-gray-700 text-sm",
  tableClassName = "w-full border-collapse table-fixed",
  colWidths,
  pairCount = 2,
  contentClassName,
  mode = "table",
}: Props) {
  const getDefaultColClasses = () => {
    const cols = [];
    for (let i = 0; i < pairCount; i++) {
      cols.push("w-1/6");
      cols.push("w-2/6");
    }
    return cols;
  };

  const colClasses = colWidths || getDefaultColClasses();

  // mode="flex" 는 부모 높이를 채우는 레이아웃이 기본 — className 없이도 동작 (필요 시 override)
  const isFlex = mode === "flex";
  const rootClassName = className ?? (isFlex ? "flex-1 min-h-0 flex flex-col mb-0" : "mb-4");

  return (
    <TableGroupContext.Provider value={mode}>
      <div className={rootClassName}>
        {title && (
          <div className={titleWrapperClassName}>
            <h3 className={titleTextClassName}>{title}</h3>
          </div>
        )}
        {isFlex ? (
          <div className={`flex flex-col flex-1 min-h-0 ${contentClassName ?? ""}`}>{children}</div>
        ) : (
          <div className={contentClassName ?? ""}>
            <table className={tableClassName}>
              <colgroup>
                {colClasses.map((colClass, index) => (
                  <col key={index} className={colClass} />
                ))}
              </colgroup>
              <tbody>{children}</tbody>
            </table>
          </div>
        )}
      </div>
    </TableGroupContext.Provider>
  );
}
