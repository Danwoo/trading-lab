"use client";

import React from "react";
import { Popup, Button } from "@/components/shared/ui";

export interface Props {
  visible: boolean;
  title: string;
  width?: number | string;
  height?: number | string;
  minWidth?: number | string;
  minHeight?: number | string;
  maxWidth?: number | string;
  maxHeight?: number | string;
  onClose: () => void;
  onSave?: () => void;
  children: React.ReactNode;
  saveDisabled?: boolean;
  cancelText?: string;
  saveText?: string;
  showCloseButton?: boolean;
  dragEnabled?: boolean;
  resizeEnabled?: boolean;
  showSaveButton?: boolean;
  showCancelButton?: boolean;
  customButtons?: React.ReactNode;
  contentClassName?: string;
  shading?: boolean;
  hideOnOutsideClick?: boolean;
  buttonsPosition?: "top" | "bottom";
}

export function FormModal({
  visible,
  title,
  width = "auto",
  height = "auto",
  minWidth,
  minHeight,
  maxWidth,
  maxHeight,
  onClose,
  onSave,
  children,
  saveDisabled = false,
  cancelText = "취소",
  saveText = "저장",
  showCloseButton = true,
  dragEnabled = false,
  resizeEnabled = false,
  showSaveButton = true,
  showCancelButton = true,
  customButtons,
  contentClassName,
  shading = true,
  hideOnOutsideClick = false,
  buttonsPosition = "top",
}: Props) {
  const hasButtons = showSaveButton || showCancelButton || !!customButtons;

  const renderButtons = (position: "top" | "bottom") =>
    hasButtons && (
      <div className={`flex-shrink-0 ${position === "top" ? "mb-4" : "mt-4"}`}>
        <div className="flex gap-2 justify-end">
          {customButtons}
          {showSaveButton && onSave && <Button text={saveText} onClick={onSave} disabled={saveDisabled} />}
          {showCancelButton && <Button text={cancelText} onClick={onClose} stylingMode="outlined" />}
        </div>
      </div>
    );

  return (
    <Popup
      visible={visible}
      title={title}
      width={width}
      height={height}
      minWidth={minWidth}
      minHeight={minHeight}
      maxWidth={maxWidth}
      maxHeight={maxHeight}
      onHiding={onClose}
      showCloseButton={showCloseButton}
      dragEnabled={dragEnabled}
      resizeEnabled={resizeEnabled}
      shading={shading}
      hideOnOutsideClick={hideOnOutsideClick}
    >
      <div className="h-full flex flex-col">
        {buttonsPosition === "top" && renderButtons("top")}
        <div
          tabIndex={0}
          className={`flex-1 overflow-auto outline-none [&>*:last-child]:mb-0 ${contentClassName || ""}`}
        >
          {children}
        </div>
        {buttonsPosition === "bottom" && renderButtons("bottom")}
      </div>
    </Popup>
  );
}
