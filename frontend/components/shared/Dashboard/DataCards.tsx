"use client";

import React, { useState, useEffect } from "react";
import { TimeSeriesDataPoint, CardConfig } from "./types";

interface DataCardsProps<T extends TimeSeriesDataPoint> {
  data: T | null;
  cardConfigs: CardConfig[];
  connected?: boolean;
  showConnectionStatus?: boolean;
  connectionStatusLabel?: string;
}

type DataState = {
  value: number | boolean | null;
  timestamp: string | null;
};

type DataCardProps = {
  label: string;
  value: string | number | boolean | null;
  unit: string;
  colorClass: string;
  bgClass?: string;
  timestamp?: string | null;
  isConnectionStatus?: boolean;
  connected?: boolean;
};

/**
 * 타임스탬프를 HH:mm:ss 형식으로 변환
 * 마이크로초는 백엔드에서 제거됨
 */
const formatDetailedTime = (isoString: string | null | undefined) => {
  if (!isoString) return "-";
  try {
    const date = new Date(isoString);
    const h = date.getHours().toString().padStart(2, "0");
    const m = date.getMinutes().toString().padStart(2, "0");
    const s = date.getSeconds().toString().padStart(2, "0");
    return `${h}:${m}:${s}`;
  } catch {
    return "-";
  }
};

// 카드 레이블
function CardLabel({ label }: { label: string }) {
  return <span className="text-sm font-bold text-gray-400 uppercase tracking-wider line-clamp-2 z-10">{label}</span>;
}

// 타임스탬프 표시
function Timestamp({ timestamp }: { timestamp?: string | null }) {
  return (
    <div className="flex items-center gap-1 text-sm text-gray-500 font-mono">
      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      {formatDetailedTime(timestamp)}
    </div>
  );
}

// Boolean 값 표시 (타임스탬프 포함)
function BooleanValueDisplay({
  value,
  colorClass,
  timestamp,
}: {
  value: boolean;
  colorClass: string;
  timestamp?: string | null;
}) {
  return (
    <div className="flex items-center justify-between gap-2 mt-1 z-10">
      <div className="flex items-center gap-2">
        <span
          className={`w-4 h-4 rounded-full ${value ? "bg-green-500" : "bg-red-500"}`}
          aria-label={value ? "True" : "False"}
        />
        <span className={`text-3xl font-extrabold tracking-tight ${colorClass}`}>{value ? "True" : "False"}</span>
      </div>
      <Timestamp timestamp={timestamp} />
    </div>
  );
}

// 숫자/문자열 값 표시 (타임스탬프 포함)
function NumericValueDisplay({
  value,
  unit,
  colorClass,
  timestamp,
}: {
  value: string | number;
  unit: string;
  colorClass: string;
  timestamp?: string | null;
}) {
  return (
    <div className="flex items-baseline justify-between mt-1 z-10">
      <div className="flex items-baseline">
        <span className={`text-4xl font-extrabold tracking-tight ${colorClass}`}>{value}</span>
        <span className="text-base font-medium text-gray-400 ml-1">{unit}</span>
      </div>
      <Timestamp timestamp={timestamp} />
    </div>
  );
}

function DataCard({
  label,
  value,
  unit,
  colorClass,
  bgClass = "bg-white",
  timestamp,
  isConnectionStatus = false,
  connected,
}: DataCardProps) {
  if (isConnectionStatus) {
    return (
      <div className="bg-blue-50 rounded-lg shadow p-5 flex flex-col items-center justify-center h-28">
        <span className="text-sm font-bold text-blue-500 uppercase tracking-wider mb-2">{label}</span>
        <div className="flex items-center gap-2">
          <span
            className={`w-3 h-3 rounded-full ${connected ? "bg-green-500" : "bg-red-500"} animate-pulse`}
            aria-label={connected ? "온라인" : "오프라인"}
          />
          <span className={`text-xl font-bold ${connected ? "text-gray-800" : "text-gray-500"}`}>
            {connected ? "Online" : "Offline"}
          </span>
        </div>
      </div>
    );
  }

  // Boolean 값인 경우 자동 판단하여 처리
  const isBooleanValue = typeof value === "boolean";

  return (
    <div
      className={`${bgClass} shadow rounded-lg p-5 flex flex-col justify-between h-28 relative overflow-hidden`}
      title={`${label}: ${isBooleanValue ? (value ? "True" : "False") : value}${isBooleanValue ? "" : unit}`}
    >
      <CardLabel label={label} />
      {isBooleanValue ? (
        <BooleanValueDisplay value={value as boolean} colorClass={colorClass} timestamp={timestamp} />
      ) : (
        <NumericValueDisplay
          value={value as string | number}
          unit={unit}
          colorClass={colorClass}
          timestamp={timestamp}
        />
      )}
    </div>
  );
}

const formatValue = (value: number | boolean | null | undefined, decimals: number = 2): string => {
  if (value !== undefined && value !== null) {
    if (typeof value === "number") {
      return value.toFixed(decimals);
    }
    // boolean 값은 문자열로 변환하지 않음 (카드에서 별도 처리)
    return "";
  }
  return "--";
};

export default function DataCards<T extends TimeSeriesDataPoint>({
  data,
  cardConfigs,
  connected = false,
  showConnectionStatus = false,
  connectionStatusLabel = "STATUS",
}: DataCardsProps<T>) {
  const [latestValues, setLatestValues] = useState<Map<string, DataState>>(
    new Map(cardConfigs.map((config) => [config.key, { value: null, timestamp: null }])),
  );

  useEffect(() => {
    if (!data) return;

    const newValues = new Map(latestValues);
    cardConfigs.forEach((config) => {
      const value = data[config.key];
      // number 또는 boolean 값 모두 처리
      if (value != null && (typeof value === "number" || typeof value === "boolean")) {
        newValues.set(config.key, {
          value,
          timestamp: data.timestamp,
        });
      }
    });
    setLatestValues(newValues);
  }, [data, cardConfigs]);

  /**
   * 카드 레이아웃 - 한 줄에 모든 카드 표시
   * - 최소 카드 크기 100px 유지
   * - 항목이 많아져도 한 줄에 모두 표시 (차트 영역 확보)
   */
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4 mb-4">
      {showConnectionStatus && (
        <DataCard
          label={connectionStatusLabel}
          isConnectionStatus
          connected={connected}
          value=""
          unit=""
          colorClass=""
        />
      )}

      {cardConfigs.map((config) => {
        const state = latestValues.get(config.key) || { value: null, timestamp: null };

        const isBooleanValue = typeof state.value === "boolean";

        // Boolean 값이면 그대로 전달, 숫자면 포맷팅
        const displayValue = isBooleanValue
          ? (state.value as boolean)
          : formatValue(state.value as number | null | undefined, config.decimals);

        return (
          <DataCard
            key={config.key}
            label={config.label}
            value={displayValue}
            unit={config.unit}
            colorClass={config.colorClass}
            bgClass={config.bgClass}
            timestamp={state.timestamp}
          />
        );
      })}
    </div>
  );
}
