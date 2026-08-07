// components/shared/ui/CheckBoxGroup.tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "./Button";
import { CheckBox } from "./CheckBox";

interface CheckBoxItem {
  value: string;
  text: string;
}

interface Props {
  items: CheckBoxItem[] | any[];
  selectedValues: string[] | string | null | undefined;
  onSelectionChanged: (selectedValues: string[]) => void;
  columns?: number;
  disabled?: boolean;
  showSelectAll?: boolean;
  valueField?: string;
  textField?: string;
  fieldName?: string;
  getFieldProps?: (fieldName: string) => { validationStatus?: string; validationError?: any };
}

export function CheckBoxGroup({
  items,
  selectedValues,
  onSelectionChanged,
  columns = 4,
  disabled = false,
  showSelectAll = true,
  valueField = "value",
  textField = "text",
  fieldName,
  getFieldProps,
}: Props) {
  const fieldProps = fieldName && getFieldProps ? getFieldProps(fieldName) : null;
  const isInvalid = fieldProps?.validationStatus === "invalid";
  const errorMessage = isInvalid
    ? Array.isArray(fieldProps?.validationError)
      ? fieldProps?.validationError[0]?.message
      : fieldProps?.validationError?.message
    : undefined;
  const normalizedItems: CheckBoxItem[] = items.map((item) => {
    if (typeof item === "object" && item !== null) {
      return {
        value: item[valueField] || item.value || "",
        text: item[textField] || item.text || item[valueField] || item.value || "",
      };
    }
    return { value: String(item), text: String(item) };
  });

  const getSafeSelectedValues = (values: string[] | string | null | undefined): string[] => {
    if (Array.isArray(values)) return values;
    if (typeof values === "string") return [values];
    return [];
  };

  const [internalSelected, setInternalSelected] = useState<string[]>(() => getSafeSelectedValues(selectedValues));

  useEffect(() => {
    setInternalSelected(getSafeSelectedValues(selectedValues));
  }, [selectedValues]);

  const handleItemChange = useCallback(
    (fieldName: string | number, value: boolean) => {
      const itemValue = fieldName.toString();

      setInternalSelected((prev) => {
        const newSelected = value
          ? [...prev.filter((v) => v !== itemValue), itemValue]
          : prev.filter((v) => v !== itemValue);

        setTimeout(() => {
          onSelectionChanged(newSelected);
        }, 0);

        return newSelected;
      });
    },
    [onSelectionChanged],
  );

  const handleSelectAll = useCallback(() => {
    setInternalSelected((prev) => {
      const isAllSelected = prev.length === normalizedItems.length;
      const newSelected = isAllSelected ? [] : normalizedItems.map((item) => item.value);

      setTimeout(() => {
        onSelectionChanged(newSelected);
      }, 0);

      return newSelected;
    });
  }, [normalizedItems, onSelectionChanged]);

  if (normalizedItems.length === 0) {
    return <div className="text-center py-4 text-gray-500">선택할 항목이 없습니다</div>;
  }

  return (
    <div className="h-full flex flex-col">
      {showSelectAll && (
        <div className="flex items-center gap-2 mb-2 flex-shrink-0">
          <Button
            text={internalSelected.length === normalizedItems.length ? "전체해제" : "전체선택"}
            onClick={handleSelectAll}
            stylingMode="outlined"
            type="normal"
            disabled={disabled}
          />
          <span className="text-sm text-gray-600">
            ({internalSelected.length}/{normalizedItems.length} 선택)
          </span>
        </div>
      )}

      <div className="flex-1 flex flex-col">
        <div
          className={`grid gap-2 overflow-y-auto flex-1 rounded border p-2 ${
            isInvalid ? "border-[#d9534f66]" : "border-transparent"
          }`}
          style={{
            gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
            gridAutoRows: "min-content",
          }}
        >
          {normalizedItems.map((item) => (
            <CheckBox
              key={item.value}
              fieldName={item.value}
              text={item.text}
              value={internalSelected.includes(item.value)}
              onValueChanged={handleItemChange}
              readOnly={disabled}
            />
          ))}
        </div>

        {isInvalid && errorMessage && (
          <div className="mt-1 self-start bg-[#d9534f] text-white text-xs p-2.5 rounded leading-normal">
            {errorMessage}
          </div>
        )}
      </div>
    </div>
  );
}
