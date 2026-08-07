"use client";

import { useRef, useCallback, useEffect, useState, useMemo } from "react";
import ReactECharts from "echarts-for-react";
import { TimeSeriesDataPoint, ChartSeriesConfig, ChartOptions } from "./types";

const DEFAULT_UPL_COLOR = "#ef4444"; // 빨강
const DEFAULT_LPL_COLOR = "#3b82f6"; // 파랑

// upl/lpl 은 독립적으로 옵셔널 — 준 값만 선을 그린다. 0 도 유효(!= null 로 판정).
// name(라벨)이 label formatter "{b}: {c}"로 함께 표시돼 색만으로 상태를 나타내지 않는다.
function buildMarkLine(limits?: ChartSeriesConfig["limits"]) {
  if (!limits) return undefined;
  const lines: { name: string; yAxis: number; lineStyle: { color: string }; label: { color: string } }[] = [];
  if (limits.upl != null) {
    const color = limits.uplColor ?? DEFAULT_UPL_COLOR;
    lines.push({ name: limits.uplLabel ?? "U", yAxis: limits.upl, lineStyle: { color }, label: { color } });
  }
  if (limits.lpl != null) {
    const color = limits.lplColor ?? DEFAULT_LPL_COLOR;
    lines.push({ name: limits.lplLabel ?? "L", yAxis: limits.lpl, lineStyle: { color }, label: { color } });
  }
  if (lines.length === 0) return undefined;
  return {
    symbol: "none",
    label: { formatter: "{b}: {c}", position: "end" },
    lineStyle: { type: "dashed", width: 1 },
    data: lines,
  };
}

interface TimeSeriesChartProps<T extends TimeSeriesDataPoint> {
  data: T[];
  seriesConfigs: ChartSeriesConfig[];
  options?: ChartOptions;
  title?: string;
  isActive?: boolean;
  onActiveChange?: (active: boolean) => void;
  initialSelectedByKey?: Record<string, boolean>;
}

export default function TimeSeriesChart<T extends TimeSeriesDataPoint>({
  data,
  seriesConfigs,
  options = {},
  title = "시계열 데이터 차트",
  isActive,
  onActiveChange,
  initialSelectedByKey,
}: TimeSeriesChartProps<T>) {
  const {
    height,
    initialVisibleHours = 1,
    animationEnabled = false,
    showSymbol = false,
    tooltipHeaderFormatter,
    xAxisLabelRotate = 0,
    xAxisLabelFormatter = "{HH}:{mm}",
    xAxisMaxInterval,
    xAxisMin,
    xAxisMax,
    xAxisType = "time",
    renderer = "svg",
  } = options;

  const chartInstanceRef = useRef<any>(null); // ECharts 인스턴스
  const containerRef = useRef<HTMLDivElement>(null); // 컨테이너 크기 측정용
  // initDims: ResizeObserver로 최초 1회만 측정 — opts에 명시적 크기를 전달해야 NaN 방지
  const [initDims, setInitDims] = useState<{ w: number; h: number } | null>(null);
  const [selectedSeries, setSelectedSeries] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(
      seriesConfigs.map((c) => [c.name, initialSelectedByKey ? (initialSelectedByKey[c.key] ?? false) : true]),
    ),
  );

  useEffect(() => {
    setSelectedSeries((prev) =>
      Object.fromEntries(
        seriesConfigs.map((c) => {
          const defaultSelected = initialSelectedByKey ? (initialSelectedByKey[c.key] ?? false) : true;
          return [c.name, prev[c.name] ?? defaultSelected];
        }),
      ),
    );
  }, [seriesConfigs, initialSelectedByKey]);

  // legend 선택 기준 가시 시리즈. 전체 숨김 시 grid/axis 최소 1개 유지
  const layoutConfigs = useMemo(() => {
    const visible = seriesConfigs.filter((c) => selectedSeries[c.name] !== false);
    return visible.length > 0 ? visible : seriesConfigs.slice(0, 1);
  }, [seriesConfigs, selectedSeries]);

  const sortedData = useMemo(
    () =>
      data.map((d) => ({ ...d, timeValue: new Date(d.timestamp).getTime() })).sort((a, b) => a.timeValue - b.timeValue),
    [data],
  );

  const chartOption = useMemo(() => {
    const now = Date.now();
    const showFullRange = initialVisibleHours === 0;
    const startTime = now - initialVisibleHours * 60 * 60 * 1000;

    const axisIndexMap = new Map(layoutConfigs.map((c, i) => [c.name, i]));

    const gap = 4;
    const chartAreaHeight = 76.5;
    const gridHeight =
      layoutConfigs.length > 0 ? (chartAreaHeight - (layoutConfigs.length - 1) * gap) / layoutConfigs.length : 80;

    const buildSeries = (c: ChartSeriesConfig, pts: [number, unknown][] = []) => {
      const axisIndex = axisIndexMap.get(c.name);
      const visible = axisIndex !== undefined;
      return {
        name: c.name,
        type: "line" as const,
        xAxisIndex: visible ? axisIndex : 0,
        yAxisIndex: visible ? axisIndex : 0,
        showSymbol,
        symbolSize: showSymbol ? 6 : undefined,
        color: c.color,
        connectNulls: true,
        markLine: visible ? buildMarkLine(c.limits) : undefined,
        data: visible ? pts : [],
        lineStyle: visible ? undefined : { opacity: 0 },
        itemStyle: visible ? undefined : { opacity: 0 },
        tooltip: visible ? undefined : { show: false },
        silent: !visible,
      };
    };

    return {
      animation: animationEnabled,
      legend: {
        data: seriesConfigs.map((c) => c.name),
        selected: selectedSeries,
        top: 8,
        left: 10,
        right: 10,
        type: "scroll",
        textStyle: { color: "#4b5563" },
      },
      axisPointer: { link: { xAxisIndex: "all" }, label: { backgroundColor: "#777" } },
      grid: layoutConfigs.map((_, i) => {
        const isLast = i === layoutConfigs.length - 1;
        return {
          left: 50,
          right: 50,
          top: `${12 + i * (gridHeight + gap)}%`,
          ...(isLast ? { bottom: 80 } : { height: `${gridHeight}%` }),
        };
      }),
      tooltip: {
        trigger: "axis",
        confine: true,
        axisPointer: { type: "line", animation: false },
        formatter: (params: any) => {
          if (!params?.length) return "";
          const axisValue = params[0].axisValue;
          const header = tooltipHeaderFormatter
            ? tooltipHeaderFormatter(axisValue)
            : new Date(axisValue).toLocaleString("ko-KR", {
                month: "2-digit",
                day: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              });
          let result = `<b>${header}</b><br/>`;
          params.forEach((p: any) => {
            const val = Array.isArray(p.value) ? p.value[1] : p.value;
            if (val != null && !isNaN(val)) {
              const dec = seriesConfigs.find((c) => c.name === p.seriesName)?.decimals ?? 2;
              const displayVal =
                typeof val === "number"
                  ? val.toLocaleString("ko-KR", { minimumFractionDigits: dec, maximumFractionDigits: dec })
                  : val;
              result += `${p.marker}${p.seriesName}: ${displayVal}<br/>`;
            }
          });
          return result;
        },
      },
      xAxis: layoutConfigs.map((_, i) => ({
        type: xAxisType as "time" | "value",
        gridIndex: i,
        axisLabel: {
          show: i === layoutConfigs.length - 1,
          formatter: i === layoutConfigs.length - 1 ? xAxisLabelFormatter : undefined,
          rotate: xAxisLabelRotate,
          margin: 12,
        },
        axisTick: { show: i === layoutConfigs.length - 1 },
        ...(xAxisType === "value"
          ? {
              ...(xAxisMaxInterval !== undefined ? { interval: xAxisMaxInterval } : {}),
              ...(xAxisMin !== undefined ? { min: xAxisMin } : {}),
              ...(xAxisMax !== undefined ? { max: xAxisMax } : {}),
            }
          : {
              minInterval: xAxisMaxInterval ?? 1000,
              ...(xAxisMaxInterval !== undefined ? { maxInterval: xAxisMaxInterval } : {}),
              ...(xAxisMin !== undefined ? { min: xAxisMin } : {}),
              ...(xAxisMax !== undefined ? { max: xAxisMax } : {}),
            }),
      })),
      yAxis: layoutConfigs.map((c, i) => {
        const dec = c.axisLabelDecimals ?? c.decimals ?? 0;
        return {
          type: "value" as const,
          gridIndex: i,
          scale: true,
          splitLine: { show: true },
          minInterval: Math.pow(10, -dec),
          axisLabel: {
            formatter: (v: number) =>
              typeof v === "number"
                ? v.toLocaleString("ko-KR", { minimumFractionDigits: dec, maximumFractionDigits: dec })
                : `${v}`,
          },
        };
      }),
      dataZoom: [
        {
          type: "inside",
          xAxisIndex: layoutConfigs.map((_, i) => i),
          ...(showFullRange ? { start: 0, end: 100 } : { startValue: startTime, endValue: now }),
        },
        {
          type: "slider",
          xAxisIndex: layoutConfigs.map((_, i) => i),
          bottom: 10,
          height: 25,
          showDetail: true,
          labelFormatter: (v: number) => {
            const d = new Date(v);
            return `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}\n${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
          },
          ...(showFullRange ? { start: 0, end: 100 } : {}),
        },
      ],
      series: seriesConfigs.map((c) =>
        buildSeries(
          c,
          sortedData.map((d) => [d.timeValue, d[c.key]] as [number, unknown]),
        ),
      ),
    };
  }, [
    seriesConfigs,
    selectedSeries,
    layoutConfigs,
    showSymbol,
    initialVisibleHours,
    animationEnabled,
    tooltipHeaderFormatter,
    xAxisType,
    xAxisLabelFormatter,
    xAxisLabelRotate,
    xAxisMaxInterval,
    xAxisMin,
    xAxisMax,
    sortedData,
  ]);

  // 차트 마운트 후 첫 rAF에서 resize — flex 레이아웃 높이가 확정된 뒤 적용
  const onChartReady = useCallback((instance: any) => {
    chartInstanceRef.current = instance;
    requestAnimationFrame(() => {
      if (instance.isDisposed()) return;
      instance.resize();
    });
  }, []);

  // initDims: 첫 측정 이후 고정 (prev ?? ...) — 이후 resize()만 호출
  // opts가 바뀌면 echarts-for-react가 인스턴스를 재생성하므로 크기 변경은 resize()로만 반영
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height: h } = entry.contentRect;
        if (width > 0 && h > 0) {
          setInitDims((prev) => prev ?? { w: Math.floor(width), h: Math.floor(h) });
          if (chartInstanceRef.current) chartInstanceRef.current.resize();
        }
      }
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  const echartsOpts = useMemo(
    () => ({ renderer, ...(initDims ? { width: initDims.w, height: initDims.h } : {}) }),
    [renderer, initDims],
  );

  const onEvents = useMemo(
    () => ({
      dataZoom: () => {
        if (isActive && onActiveChange) onActiveChange(false);
      },
      legendselectchanged: (event: { selected: Record<string, boolean> }) => {
        if (event?.selected) setSelectedSeries(event.selected);
      },
    }),
    [isActive, onActiveChange],
  );

  return (
    <div
      className={`bg-white rounded-lg shadow-md mb-1 ml-1 mr-1 flex flex-col ${height ? "" : "flex-1 min-h-0"}`}
      style={height ? { height, padding: 24 } : { padding: 24 }}
    >
      <h3 className="text-lg font-semibold mb-3">{title}</h3>
      <div ref={containerRef} style={{ flex: 1, minHeight: 0 }}>
        {data.length === 0 ? (
          // 데이터 0건: 제목만 남은 빈 패널("고장"으로 읽힘) 대신 명시적 빈 상태
          <div role="status" className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <div className="text-4xl mb-4">📊</div>
              <div className="text-lg mb-2">데이터가 없습니다</div>
              <div className="text-sm">표시할 시계열 데이터가 없습니다.</div>
            </div>
          </div>
        ) : (
          initDims && (
            <ReactECharts
              key={seriesConfigs.map((c) => c.key).join("-")}
              option={chartOption}
              style={{ height: "100%", width: "100%" }}
              notMerge={false}
              lazyUpdate={true}
              onChartReady={onChartReady}
              onEvents={onEvents}
              opts={echartsOpts}
            />
          )
        )}
      </div>
    </div>
  );
}
