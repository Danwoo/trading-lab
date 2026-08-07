"use client";
import { useState } from "react";

interface Props {
  fieldName: string;
  value: number | undefined;
  onValueChanged: (fieldName: string, value: number) => void;
  maxStars?: number;
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
  showLabel?: boolean;
}

const IMPORTANCE_LABELS: Record<number, string> = {
  0: "참고",
  1: "일반",
  2: "중요",
  3: "필수",
};

export function StarRating({
  fieldName,
  value,
  onValueChanged,
  maxStars = 3,
  size = "md",
  disabled = false,
  showLabel = true,
}: Props) {
  const [hoverValue, setHoverValue] = useState<number | null>(null);

  const sizeClasses = {
    sm: "text-lg",
    md: "text-xl",
    lg: "text-2xl",
  };

  const currentValue = value ?? 0;

  const handleClick = (starValue: number) => {
    if (disabled) return;
    // 같은 값을 클릭하면 0으로 초기화
    const newValue = currentValue === starValue ? 0 : starValue;
    onValueChanged(fieldName, newValue);
  };

  const displayValue = hoverValue !== null ? hoverValue : currentValue;
  const label = IMPORTANCE_LABELS[displayValue] || "";

  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center">
        {Array.from({ length: maxStars }, (_, i) => i + 1).map((starValue) => (
          <button
            key={starValue}
            type="button"
            onClick={() => handleClick(starValue)}
            onMouseEnter={() => !disabled && setHoverValue(starValue)}
            onMouseLeave={() => setHoverValue(null)}
            disabled={disabled}
            className={`${sizeClasses[size]} transition-colors duration-150 ${
              disabled ? "cursor-default" : "cursor-pointer hover:scale-110"
            }`}
            title={IMPORTANCE_LABELS[starValue]}
          >
            {starValue <= displayValue ? (
              <span className="text-yellow-400">★</span>
            ) : (
              <span className="text-gray-300">☆</span>
            )}
          </button>
        ))}
      </div>
      {showLabel && <span className="text-sm text-gray-600 min-w-[40px]">{label}</span>}
    </div>
  );
}
