// components/shared/Layout/SplitPane.tsx
"use client";

import { Fragment, type ReactNode } from "react";
import { Group, Panel, Separator } from "react-resizable-panels";

export interface SplitPaneProps {
  orientation?: "horizontal" | "vertical";
  initialSizes?: number[];
  minSizes?: number[];
  children: ReactNode[];
}

// react-resizable-panels 는 숫자 defaultSize/minSize 를 픽셀로 해석한다 — 이 컴포넌트의
// initialSizes/minSizes 는 퍼센트 계약이라 단위 없는 문자열로 바꿔 넘긴다(라이브러리 규칙:
// "Strings without explicit units are interpreted as percentage").
function toPercentString(value: number | undefined): string | undefined {
  return value === undefined ? undefined : String(value);
}

export function SplitPane({ orientation = "horizontal", initialSizes, minSizes, children }: SplitPaneProps) {
  return (
    <Group orientation={orientation} style={{ height: "100%", width: "100%" }}>
      {children.map((child, index) => (
        <Fragment key={index}>
          {index > 0 && (
            <Separator
              className={
                orientation === "horizontal"
                  ? "w-1 shrink-0 cursor-col-resize bg-gray-200 hover:bg-blue-300 focus-visible:bg-blue-400 focus-visible:outline-none"
                  : "h-1 shrink-0 cursor-row-resize bg-gray-200 hover:bg-blue-300 focus-visible:bg-blue-400 focus-visible:outline-none"
              }
            />
          )}
          <Panel
            defaultSize={toPercentString(initialSizes?.[index])}
            minSize={toPercentString(minSizes?.[index])}
            className="min-h-0 min-w-0 overflow-auto"
          >
            {child}
          </Panel>
        </Fragment>
      ))}
    </Group>
  );
}
