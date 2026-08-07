"use client";

import React, { useState, useEffect } from "react";
import { Button, DateRangeBox } from "@/components/shared/ui";
import { TimeRangePreset } from "./types";

export const DEFAULT_PRESETS: TimeRangePreset[] = [
  { label: "10분", minutes: 10 },
  { label: "30분", minutes: 30 },
  { label: "1시간", minutes: 60 },
  { label: "3시간", minutes: 180 },
  { label: "6시간", minutes: 360 },
  { label: "12시간", minutes: 720 },
  { label: "1일", minutes: 1440 },
  { label: "2일", minutes: 2880 },
];

const MANUAL_PRESET: TimeRangePreset = { label: "직접 입력", minutes: 0 };

interface Props {
  minutes: number;
  setMinutes: (m: number) => void;
  applyMinutes: () => void;
  isActive: boolean;
  toggleActive: () => void;
  showManualInput?: boolean;
  dateRange?: [Date | null, Date | null] | undefined;
  setDateRange?: (range: [Date | null, Date | null]) => void;
  presets?: TimeRangePreset[];
  showToggleButton?: boolean;
  toggleButtonLabels?: {
    active: string;
    inactive: string;
  };
}

export default function TimeRangePanel({
  minutes,
  setMinutes,
  applyMinutes,
  isActive,
  toggleActive,
  showManualInput = false,
  dateRange,
  setDateRange,
  presets = DEFAULT_PRESETS,
  showToggleButton = true,
  toggleButtonLabels = {
    active: "정 지",
    inactive: "재 생",
  },
}: Props) {
  const effectivePresets = showManualInput ? [...presets, MANUAL_PRESET] : presets;
  const isManual = showManualInput && minutes === 0;
  const [localDateRange, setLocalDateRange] = useState<[Date | null, Date | null]>(dateRange ?? [null, null]);

  useEffect(() => {
    setLocalDateRange(dateRange ?? [null, null]);
  }, [dateRange]);

  const onPresetClick = (presetMinutes: number) => {
    setMinutes(presetMinutes);
    if (presetMinutes === 0 && isActive) {
      toggleActive();
    }
  };

  const onApplyDates = () => {
    if (setDateRange) setDateRange(localDateRange);
    applyMinutes();
  };

  return (
    <div className="bg-white p-4 rounded-lg shadow-md mb-6">
      <div className="flex flex-wrap gap-2 items-center justify-between">
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-sm font-medium text-gray-700 mr-2 mt-2">조회 기간</span>

          <div className="flex gap-2 items-center mt-2">
            {effectivePresets.map(({ label, minutes: presetMinutes }) => (
              <Button
                key={label}
                text={label}
                type="default"
                stylingMode={minutes === presetMinutes ? "contained" : "outlined"}
                onClick={() => onPresetClick(presetMinutes)}
                className="rounded"
              />
            ))}
          </div>

          {isManual && (
            <DateRangeBox
              fieldName="dateRange"
              value={localDateRange}
              onValueChanged={(fieldName, newValue) => {
                const newDates: [Date | null, Date | null] = [
                  newValue[0] ? new Date(newValue[0]) : null,
                  newValue[1] ? new Date(newValue[1]) : null,
                ];
                setLocalDateRange(newDates);
              }}
              displayFormat="yyyy-MM-dd"
              type="date"
              placeholder="날짜 범위 선택"
            />
          )}
        </div>

        <div className="flex gap-2 items-center mt-2">
          {isManual ? (
            <Button
              icon="search"
              text="검 색"
              type="default"
              stylingMode="contained"
              onClick={onApplyDates}
              className="rounded font-bold"
              width={100}
              disabled={!localDateRange[0] || !localDateRange[1]}
            />
          ) : (
            showToggleButton && (
              <Button
                icon={isActive ? "clear" : "video"}
                text={isActive ? toggleButtonLabels.active : toggleButtonLabels.inactive}
                type={isActive ? "danger" : "success"}
                stylingMode="contained"
                onClick={() => {
                  toggleActive();
                  if (!isActive) {
                    applyMinutes();
                  }
                }}
                className="rounded font-bold"
              />
            )
          )}
        </div>
      </div>
    </div>
  );
}
