"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { TabPanel, TabContent } from "@/components/shared/ui";
import { TimeRangePanel, DataCards, TimeSeriesChart, DataLog } from "@/components/shared/Dashboard";
import type { CardConfig, ChartSeriesConfig } from "@/components/shared/Dashboard";
import { selectNavHistory } from "@/services/nav/navService";
import type { NavPoint } from "@/schemas/nav/nav";

const POLL_INTERVAL = 5000;
const DEFAULT_MINUTES = 30;

const TAB_ITEMS = [
  { id: "chart", text: "차 트" },
  { id: "log", text: "로 그" },
];

const CARD_CONFIGS: CardConfig[] = [
  { key: "nav", label: "NAV", unit: "pt", colorClass: "text-blue-600", decimals: 2 },
  { key: "benchmark", label: "벤치마크", unit: "pt", colorClass: "text-green-600", decimals: 2 },
  { key: "daily_return", label: "일간 수익률", unit: "%", colorClass: "text-orange-500", decimals: 2 },
  { key: "drawdown", label: "최대낙폭", unit: "%", colorClass: "text-red-600", decimals: 2 },
];

const CHART_SERIES: ChartSeriesConfig[] = [
  { key: "nav", name: "NAV", color: "#3b82f6", unit: "pt", yAxisName: "pt", decimals: 2 },
  { key: "benchmark", name: "벤치마크", color: "#10b981", unit: "pt", yAxisName: "pt", decimals: 2 },
  { key: "daily_return", name: "일간 수익률", color: "#f97316", unit: "%", yAxisName: "%", decimals: 2 },
  { key: "drawdown", name: "최대낙폭", color: "#ef4444", unit: "%", yAxisName: "%", decimals: 2 },
];

export default function NavDashboardContainer() {
  const [minutes, setMinutes] = useState(DEFAULT_MINUTES);
  const [isPolling, setIsPolling] = useState(true);
  const [data, setData] = useState<NavPoint[]>([]);
  const minutesRef = useRef(minutes);
  minutesRef.current = minutes;

  const fetchHistory = useCallback(async (mins: number) => {
    const result = await selectNavHistory(mins);
    if (result) setData(result.items);
  }, []);

  useEffect(() => {
    fetchHistory(minutes);
  }, [fetchHistory, minutes]);

  useEffect(() => {
    if (!isPolling) return;
    const id = setInterval(() => fetchHistory(minutesRef.current), POLL_INTERVAL);
    return () => clearInterval(id);
  }, [isPolling, fetchHistory]);

  const applyMinutes = useCallback(() => fetchHistory(minutesRef.current), [fetchHistory]);
  const toggleActive = useCallback(() => setIsPolling((p) => !p), []);

  const latest = data.length ? data[data.length - 1] : null;

  return (
    <div className="h-full max-h-screen flex flex-col p-4">
      <TimeRangePanel
        minutes={minutes}
        setMinutes={setMinutes}
        applyMinutes={applyMinutes}
        isActive={isPolling}
        toggleActive={toggleActive}
      />

      <DataCards data={latest} cardConfigs={CARD_CONFIGS} connected={isPolling} showConnectionStatus />

      <TabPanel items={TAB_ITEMS} defaultTab="chart">
        <TabContent tabId="chart" className="flex flex-col h-full overflow-hidden">
          <TimeSeriesChart
            data={data}
            seriesConfigs={CHART_SERIES}
            title="NAV 차트"
            isActive={isPolling}
            onActiveChange={setIsPolling}
            options={{ initialVisibleHours: minutes / 60, xAxisLabelRotate: 45 }}
          />
        </TabContent>
        <TabContent tabId="log" className="flex flex-col h-full overflow-auto">
          <DataLog data={data} cardConfigs={CARD_CONFIGS} title="NAV 로그" />
        </TabContent>
      </TabPanel>
    </div>
  );
}
