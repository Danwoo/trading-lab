// components/shared/Feedback/Alert.tsx
import React from "react";

type AlertType = "info" | "warning" | "error" | "success";

interface Props {
  type?: AlertType;
  icon?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

const STYLE_BY_TYPE: Record<AlertType, { bg: string; border: string; text: string; defaultIcon: string }> = {
  info: { bg: "bg-blue-50", border: "border-blue-200", text: "text-blue-900", defaultIcon: "💡" },
  warning: { bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-900", defaultIcon: "⚠️" },
  error: { bg: "bg-red-50", border: "border-red-200", text: "text-red-900", defaultIcon: "❌" },
  success: { bg: "bg-green-50", border: "border-green-200", text: "text-green-900", defaultIcon: "✅" },
};

/**
 * Alert 컴포넌트
 *
 * 폼/패널 안에 inline 으로 표시되는 정적 안내 배너.
 * 사용자 액션이 필요하지 않은 정보/경고/에러 표시에 사용.
 * (사용자 confirm 이 필요하면 MessagePopup, 단발성 알림은 ToastNotification 사용)
 *
 * @example
 * <Alert type="warning">이 Step 뒤에 오는 컬럼/행 삭제는 반영되지 않습니다.</Alert>
 * <Alert type="info" icon="🔍">검색 결과는 최대 100개까지 표시됩니다.</Alert>
 */
export function Alert({ type = "info", icon, children, className = "" }: Props) {
  const style = STYLE_BY_TYPE[type];
  return (
    <div
      className={`px-3 py-2 ${style.bg} border ${style.border} rounded text-sm ${style.text} flex gap-2 ${className}`}
      role="alert"
    >
      <span className="flex-shrink-0">{icon ?? style.defaultIcon}</span>
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  );
}
