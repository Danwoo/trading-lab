// components/shared/Layout/TableCell.tsx
import { ReactNode, isValidElement } from "react";
import { useTableGroupMode } from "./TableGroup";
import { formatDate } from "@/utils/common/formatters/date";

export type DataType = "string" | "number" | "date" | "boolean" | "datetime";

interface Props {
  label?: string;
  required?: boolean;
  children?: ReactNode;
  colSpan?: number;
  rowSpan?: number;
  items?: any[];
  valueExpr?: string;
  displayExpr?: string | ((item: any) => string);
  height?: string | number;
  maxHeight?: string | number;
  overflowY?: "visible" | "hidden" | "scroll" | "auto";
  whiteSpace?: "normal" | "pre-wrap" | "pre" | "nowrap";
  className?: string;
  labelClassName?: string;
  contentClassName?: string;
  dataType?: DataType;
  format?: string;
}

export function TableCell({
  label,
  required = false,
  children,
  colSpan = 1,
  rowSpan = 1,
  items,
  valueExpr = "code",
  displayExpr = "code_nm",
  height,
  maxHeight,
  overflowY = "visible",
  whiteSpace = "normal",
  className = "",
  labelClassName = "p-2 bg-gray-100 border border-gray-300 font-medium",
  contentClassName = "p-2 border border-gray-300",
  dataType = "string",
  format,
}: Props) {
  const getDisplayValue = () => {
    if (!items || typeof children !== "string") return children;

    const matchedItem = items.find((item) => {
      const itemValue = item[valueExpr] || item.code || item.value;
      return itemValue === children || String(itemValue) === children;
    });

    if (!matchedItem) return children;

    if (typeof displayExpr === "function") {
      return displayExpr(matchedItem);
    }

    return matchedItem[displayExpr] || matchedItem.code_nm || matchedItem.text || children;
  };

  const mode = useTableGroupMode();
  const displayValue = getDisplayValue();
  const contentStyle = {
    whiteSpace,
    ...(height !== undefined ? { height } : {}),
    ...(maxHeight !== undefined ? { maxHeight } : {}),
    ...(height !== undefined || maxHeight !== undefined ? { overflowY } : {}),
  };

  const formatValue = (value: any, type: DataType, pattern?: string) => {
    if (value === null || value === undefined || value === "") {
      return "\u00A0";
    }

    if (isValidElement(value)) {
      return value;
    }

    if (typeof value === "object" && value !== null) {
      return value;
    }

    switch (type) {
      case "number": {
        const numValue = Number(value);
        if (isNaN(numValue)) return String(value);

        if (pattern) {
          if (pattern === "#0.####") return numValue.toFixed(4);
          if (pattern === "#,##0") return numValue.toLocaleString();
          if (pattern === "#0.##") return numValue.toFixed(2);
          if (pattern === "#0") return Math.round(numValue).toString();
        }
        return String(numValue);
      }

      case "boolean":
        return value ? "true" : "false";

      // date·datetime 은 공용 포맷터 formatDate() 하나로 모은다(#263 표시 타임존 정책 — 기본값
      // 사용자/런타임 타임존). 예전엔 여기서 직접 `toISOString()` 을 썼는데 그건 항상 UTC
      // 고정이라 사용자 타임존과 어긋난다 — 그리드(DevExtreme dataType:"datetime")와 상세
      // 화면(TableCell)이 같은 값을 다른 타임존으로 보여주면 같은 행이 화면마다 달라진다
      // (#303). `pattern`/`format` prop 은 number 타입 전용으로 남고 date·datetime 은 무시한다
      // — 이 두 타입에 커스텀 패턴을 넘기는 호출부가 없다(전수 확인, 2026-08).
      case "date":
        return formatDate(value, "date") ?? String(value);

      case "datetime":
        return formatDate(value, "datetime") ?? String(value);

      case "string":
      default:
        return String(value);
    }
  };

  const content = (
    <div className="break-all" style={contentStyle}>
      {formatValue(displayValue, dataType, format)}
    </div>
  );
  const hasContent = displayValue !== null && displayValue !== undefined && displayValue !== "";

  if (mode === "flex") {
    if (label !== undefined) {
      return (
        <>
          <div className={labelClassName}>
            {label}
            {required && <span className="text-red-500 ml-1">*</span>}
          </div>
          <div className={`${contentClassName} ${className} flex-1 min-h-0`}>{children}</div>
        </>
      );
    }
    return <div className={`${contentClassName} ${className} flex-1 min-h-0`}>{children}</div>;
  }

  if (label !== undefined) {
    return (
      <>
        <td className={labelClassName} rowSpan={rowSpan}>
          {label}
          {required && <span className="text-red-500 ml-1">*</span>}
        </td>
        <td className={`${contentClassName} ${className}`} colSpan={colSpan} rowSpan={rowSpan}>
          {content}
        </td>
      </>
    );
  }

  return (
    <td
      className={`${contentClassName} ${className}`}
      colSpan={!hasContent ? Math.max(colSpan, 2) : colSpan}
      rowSpan={rowSpan}
    >
      {content}
    </td>
  );
}
