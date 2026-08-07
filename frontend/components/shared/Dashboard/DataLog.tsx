"use client";

import React, { useMemo } from "react";
import { Virtuoso } from "react-virtuoso";
import { TimeSeriesDataPoint, CardConfig, LogOptions } from "./types";

interface DataLogProps<T extends TimeSeriesDataPoint> {
  data: T[];
  cardConfigs: CardConfig[];
  options?: LogOptions;
  title?: string;
}

const formatLogTime = (isoString: string) => {
  if (!isoString) return "--";
  const noT = isoString.replace("T", " ");
  const dotIndex = noT.indexOf(".");
  if (dotIndex !== -1) {
    return noT.substring(0, dotIndex + 4);
  }
  return noT;
};

export default function DataLog<T extends TimeSeriesDataPoint>({
  data,
  cardConfigs,
  options = {},
  title = "데이터 로그",
}: DataLogProps<T>) {
  const { height, reverseOrder = true } = options;

  const processedData = useMemo(() => {
    if (!data || data.length === 0) return [];

    const sorted = [...data].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

    // 동일 타임스탬프 데이터 병합
    const merged: T[] = [];
    if (sorted.length > 0) {
      let current = { ...sorted[0] };

      for (let i = 1; i < sorted.length; i++) {
        const next = sorted[i];
        if (current.timestamp === next.timestamp) {
          current = { ...current, ...Object.fromEntries(Object.entries(next).filter(([_, v]) => v != null)) } as T;
        } else {
          merged.push(current);
          current = { ...next };
        }
      }
      merged.push(current);
    }

    return reverseOrder ? merged.reverse() : merged;
  }, [data, reverseOrder]);

  const formatValue = (val: any, config: CardConfig) => {
    if (val != null) {
      if (typeof val === "boolean") {
        return val ? "True" : "False";
      }
      if (typeof val === "number") {
        const decimals = config.decimals ?? 2;
        return `${val.toFixed(decimals)}${config.unit}`;
      }
    }
    return "--";
  };

  const getValueStyle = (colorClass: string, value: any) => {
    if (value == null) return "text-gray-300";
    return `${colorClass} font-medium`;
  };

  return (
    <div
      className={`bg-white rounded-lg shadow-md mb-1 ml-1 mr-1 flex flex-col ${height ? "" : "h-full"}`}
      style={{
        ...(height ? { height } : {}),
        padding: 24,
        boxSizing: "border-box",
        overflow: "hidden",
      }}
    >
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <h3 className="text-lg font-semibold">{title}</h3>
        <span className="text-sm text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">Total {processedData.length}</span>
      </div>

      <div style={{ flex: 1, minHeight: 0, width: "100%" }}>
        {processedData.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <p className="text-gray-400">데이터를 기다리는 중...</p>
          </div>
        ) : (
          <Virtuoso
            style={{ height: "100%", width: "100%" }}
            data={processedData}
            className="pr-2"
            itemContent={(index, item) => {
              return (
                <div className="pb-2 pr-2">
                  <div className="flex flex-col p-3 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors w-full box-border">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-gray-500 font-mono tracking-tight bg-gray-100 px-2 py-0.5 rounded">
                        {(item.time_range_label as string | undefined) ?? formatLogTime(item.timestamp)}
                      </span>
                    </div>

                    <div className="flex flex-wrap gap-x-3 gap-y-1 w-full">
                      {cardConfigs.map((config) => {
                        const value = item[config.key];
                        return (
                          <span
                            key={config.key}
                            className={`text-sm whitespace-nowrap ${getValueStyle(config.colorClass, value)}`}
                          >
                            {config.label}: {formatValue(value, config)}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                </div>
              );
            }}
          />
        )}
      </div>
    </div>
  );
}
