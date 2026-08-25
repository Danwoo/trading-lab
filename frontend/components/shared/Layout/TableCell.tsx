// components/shared/Layout/TableCell.tsx
import { ReactElement, ReactNode, cloneElement, isValidElement, useId } from "react";
import { useTableGroupMode } from "./TableGroup";
import { formatDate } from "@/utils/common/formatters/date";

export type DataType = "string" | "number" | "date" | "boolean" | "datetime";

/**
 * 라벨과 입력칸을 잇는다 — `<label htmlFor>` 이 가리킬 `id` 를 자식 입력에 내려 준다.
 *
 * 라벨이 **옆 칸의 글자**로만 있으면 눌러도 포커스가 안 가고 스크린 리더는 「편집 텍스트」라고만
 * 읽는다 (#353: 관리자 폼 37칸 중 31칸이 그랬다). 공용 입력 프리미티브는 진작부터 `id` 를 받아
 * 실제 `<input>` 에 붙이고 있었고, 그 자리를 채우는 쪽이 없었을 뿐이다.
 *
 * 이미 `id` 를 들고 온 자식은 건드리지 않고 그 값을 그대로 가리킨다 — 호출부가 정한 것이 우선이다.
 * 자식이 요소가 아니면(보기 전용 셀의 문자열) 이을 자리가 없으므로 `null` 을 돌려주고, 라벨은
 * 종전처럼 글자로만 그린다.
 */
function withFieldId(node: ReactNode, fallbackId: string): { node: ReactNode; targetId: string | null } {
  if (!isValidElement(node)) return { node, targetId: null };
  const existing = (node.props as { id?: string }).id;
  if (existing !== undefined) return { node, targetId: existing };
  return { node: cloneElement(node as ReactElement<{ id?: string }>, { id: fallbackId }), targetId: fallbackId };
}

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
  const fallbackFieldId = useId();
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

  const cellField = withFieldId(displayValue, fallbackFieldId);
  const flexField = withFieldId(children, fallbackFieldId);
  const content = (
    <div className="break-all" style={contentStyle}>
      {formatValue(cellField.node, dataType, format)}
    </div>
  );
  const hasContent = displayValue !== null && displayValue !== undefined && displayValue !== "";

  const labelBody = (
    <>
      {label}
      {required && <span className="text-red-500 ml-1">*</span>}
    </>
  );
  const labelFor = (targetId: string | null) =>
    targetId === null ? labelBody : <label htmlFor={targetId}>{labelBody}</label>;

  if (mode === "flex") {
    if (label !== undefined) {
      return (
        <>
          <div className={labelClassName}>{labelFor(flexField.targetId)}</div>
          <div className={`${contentClassName} ${className} flex-1 min-h-0`}>{flexField.node}</div>
        </>
      );
    }
    return <div className={`${contentClassName} ${className} flex-1 min-h-0`}>{children}</div>;
  }

  if (label !== undefined) {
    return (
      <>
        <td className={labelClassName} rowSpan={rowSpan}>
          {labelFor(cellField.targetId)}
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
