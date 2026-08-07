// components/shared/ui/EditableTextList.tsx
"use client";

import { Fragment, ReactNode, useEffect, useState } from "react";
import { Button } from "./Button";
import { TextBox } from "./TextBox";

interface RowProps {
  value: string;
  onChange: (value: string) => void;
  isEditing: boolean;
  onEdit: () => void;
  onSave: () => void;
  onDelete: () => void;
  placeholder?: string;
  fieldName?: string;
  editable?: boolean;
  error?: string;
  editDisabled?: boolean;
  deleteDisabled?: boolean;
  inputMode?: "text" | "search" | "tel" | "url" | "email";
  maxLength?: number;
}

function EditableTextRow({
  value,
  onChange,
  isEditing,
  onEdit,
  onSave,
  onDelete,
  placeholder,
  fieldName = "value",
  editable = true,
  error,
  editDisabled,
  deleteDisabled,
  inputMode,
  maxLength,
}: RowProps) {
  return (
    <div>
      <div className="flex gap-2 items-center">
        <div className="flex-1 min-w-0">
          <TextBox
            fieldName={fieldName}
            value={value}
            onValueChanged={(_, v: any) => onChange(v)}
            placeholder={placeholder}
            readOnly={!editable || !isEditing}
            mode={inputMode}
            maxLength={maxLength}
          />
        </div>
        {editable &&
          (isEditing ? (
            <Button icon="save" type="default" onClick={onSave} disabled={!value.trim()} width={36} height={36} />
          ) : (
            <Button
              icon="edit"
              stylingMode="outlined"
              onClick={onEdit}
              disabled={editDisabled}
              width={36}
              height={36}
            />
          ))}
        {editable && (
          <Button
            icon="trash"
            stylingMode="outlined"
            type="danger"
            onClick={onDelete}
            disabled={deleteDisabled}
            width={36}
            height={36}
          />
        )}
      </div>
      {error && <div className="text-xs text-red-500 mt-1">{error}</div>}
    </div>
  );
}

interface Props<T> {
  items: T[];
  setItems: (items: T[]) => void;
  getValue: (item: T) => string;
  setValue: (item: T, value: string) => T;
  createItem: () => T;
  /** 빈값 아닌 항목 저장 시 호출. true 리턴하면 편집모드 종료. async 지원. 미전달 시 즉시 종료. */
  onSave?: (item: T, index: number) => Promise<boolean> | boolean;
  /** 행별 에러 메시지 추출 (있으면 행 하단에 빨간 텍스트로 표시) */
  getError?: (item: T) => string | undefined;
  /** React key 추출. 기본 index */
  getKey?: (item: T, index: number) => string | number;

  fieldName?: string;
  /** 입력 placeholder. 기본 "입력하세요" */
  placeholder?: string;
  /** 추가 버튼 라벨. 기본 "추가" */
  addLabel?: string;
  /** 항목 최대 개수. 미전달 시 무제한 */
  maxItems?: number;
  /** false 면 전체 read-only (행/추가 버튼 모두 비활성) */
  editable?: boolean;

  /** 행 wrapping (예: <TableRow><TableCell>{row}</TableCell></TableRow>) */
  rowWrapper?: (row: ReactNode, key: string | number) => ReactNode;
  /** 추가 버튼 wrapping */
  addWrapper?: (button: ReactNode) => ReactNode;

  editDisabled?: (item: T, index: number) => boolean;
  deleteDisabled?: (item: T, index: number) => boolean;
  addDisabled?: boolean;

  /** HTML input mode hint (모바일 키보드 최적화). 예: "url", "email" */
  inputMode?: "text" | "search" | "tel" | "url" | "email";
  /** 행별 최대 글자수 */
  maxLength?: number;
}

/**
 * 인라인 편집 가능한 텍스트 리스트 (행 + 추가 버튼 + max 제한 통합).
 *
 * 편집 상태는 내부 관리. 항목 데이터는 controlled (items / setItems).
 */
export function EditableTextList<T>({
  items,
  setItems,
  getValue,
  setValue,
  createItem,
  onSave,
  getError,
  getKey,
  fieldName = "value",
  placeholder = "입력하세요",
  addLabel = "추가",
  maxItems,
  editable = true,
  rowWrapper,
  addWrapper,
  editDisabled,
  deleteDisabled,
  addDisabled,
  inputMode,
  maxLength,
}: Props<T>) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  // 외부에서 items 가 짧아진 경우 (예: 자동생성으로 교체) editingIndex 가 out-of-bounds 가 되지 않도록 클램프
  useEffect(() => {
    if (editingIndex !== null && editingIndex >= items.length) setEditingIndex(null);
  }, [items.length, editingIndex]);

  const handleAdd = () => {
    const next = [...items, createItem()];
    setItems(next);
    setEditingIndex(next.length - 1);
  };

  const handleDelete = (index: number) => {
    setItems(items.filter((_, i) => i !== index));
    if (editingIndex === index) setEditingIndex(null);
    else if (editingIndex !== null && editingIndex > index) setEditingIndex(editingIndex - 1);
  };

  const handleSave = async (index: number) => {
    if (onSave) {
      const ok = await onSave(items[index], index);
      if (ok) setEditingIndex(null);
    } else {
      setEditingIndex(null);
    }
  };

  const reachedMax = maxItems !== undefined && items.length >= maxItems;
  const addButton = editable ? (
    <Button
      text={addLabel}
      icon="plus"
      stylingMode="outlined"
      onClick={handleAdd}
      width="100%"
      disabled={addDisabled || editingIndex !== null || reachedMax}
    />
  ) : null;

  const renderRow = (item: T, index: number) => (
    <EditableTextRow
      fieldName={fieldName}
      value={getValue(item)}
      onChange={(v) => setItems(items.map((it, i) => (i === index ? setValue(it, v) : it)))}
      placeholder={placeholder}
      isEditing={editingIndex === index}
      onEdit={() => setEditingIndex(index)}
      onSave={() => handleSave(index)}
      onDelete={() => handleDelete(index)}
      editable={editable}
      error={getError?.(item)}
      editDisabled={editDisabled?.(item, index)}
      deleteDisabled={deleteDisabled?.(item, index)}
      inputMode={inputMode}
      maxLength={maxLength}
    />
  );

  // rowWrapper 제공 시 (예: TableRow 안에 배치) — 외부 wrapping 에 맡김
  if (rowWrapper) {
    return (
      <>
        {items.map((item, index) => {
          const key = getKey?.(item, index) ?? index;
          return rowWrapper(renderRow(item, index), key);
        })}
        {addButton && (addWrapper ? addWrapper(addButton) : addButton)}
      </>
    );
  }

  // flat layout — 컴포넌트가 자체 vertical gap 보장
  return (
    <div className="flex flex-col gap-2">
      {items.map((item, index) => {
        const key = getKey?.(item, index) ?? index;
        return <Fragment key={key}>{renderRow(item, index)}</Fragment>;
      })}
      {addButton}
    </div>
  );
}
