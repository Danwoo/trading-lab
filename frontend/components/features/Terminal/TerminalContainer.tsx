"use client";

import { useEffect, useMemo } from "react";
import { useSessionContext } from "@/hooks/shared/useSessionContext";
import { useTerminalRegion } from "@/hooks/terminal/useTerminalContext";
import { useLayoutStore } from "@/stores/terminal/layoutStore";
import { pruneUnknownPanels } from "@/lib/terminal/layoutSchema";
import { getPanelDefinition, listPanelDefinitions } from "@/lib/terminal/panelRegistry";
import { moveCell, resizeCell, type MoveDirection, type ResizeAxis } from "@/lib/terminal/gridMath";
import {
  DEFAULT_MARKET_COLOR_PRESET,
  applyMarketColorPreset,
  readStoredMarketColorPreset,
} from "@/lib/terminal/marketColorPreset";
import { GRID_COLUMNS_COUNT } from "@/constants/terminal";
import type { GridCell } from "@/types/terminal/layout";
import type { PanelDefinition } from "@/types/terminal/panel";
import { PanelGrid } from "./PanelGrid";
import { PanelSlot } from "./PanelSlot";
import { PanelPicker } from "./PanelPicker";
import { SymbolSidebar } from "./SymbolSidebar";

/**
 * 터미널의 셸 — 문맥·레이아웃 스토어를 여는 유일한 곳(다른 컴포넌트는 `contextActions`/
 * `contextStore` 를 직접 import 하지 않는다). RGL 스파이크 규칙 B: 저장 레이아웃 복원은
 * 렌더 중이 아니라 이 마운트 이펙트에서 `setWorkspace()` 로 한다.
 */
export function TerminalContainer() {
  const { workspaceId: sessionWorkspaceId, isLoaded } = useSessionContext();
  const setWorkspace = useLayoutStore((s) => s.setWorkspace);
  const layout = useLayoutStore((s) => s.layout);
  const recovered = useLayoutStore((s) => s.recovered);
  const applyGrid = useLayoutStore((s) => s.applyGrid);
  const toggleCollapsed = useLayoutStore((s) => s.toggleCollapsed);
  const closePanel = useLayoutStore((s) => s.closePanel);
  const openPanel = useLayoutStore((s) => s.openPanel);
  const updateSettings = useLayoutStore((s) => s.updateSettings);
  const dismissRecovered = useLayoutStore((s) => s.dismissRecovered);
  const region = useTerminalRegion();

  useEffect(() => {
    if (!isLoaded) return;
    setWorkspace(sessionWorkspaceId != null ? String(sessionWorkspaceId) : "default");
  }, [isLoaded, sessionWorkspaceId, setWorkspace]);

  useEffect(() => {
    const preset = readStoredMarketColorPreset() ?? DEFAULT_MARKET_COLOR_PRESET;
    applyMarketColorPreset(preset, document.documentElement);
  }, []);

  const knownTypes = useMemo(() => listPanelDefinitions().map((d) => d.type), []);
  const { renderable } = pruneUnknownPanels(layout, knownTypes);
  const renderableIds = new Set(renderable.map((p) => p.instanceId));
  const renderableCells = layout.grid.filter((cell) => renderableIds.has(cell.i));

  const handleCellsChange = (nextRenderableCells: GridCell[]) => {
    const preservedCells = layout.grid.filter((cell) => !renderableIds.has(cell.i));
    applyGrid([...preservedCells, ...nextRenderableCells]);
  };

  const handleMove = (instanceId: string, direction: MoveDirection) => {
    applyGrid(layout.grid.map((c) => (c.i === instanceId ? moveCell(c, direction, GRID_COLUMNS_COUNT) : c)));
  };

  const handleResize = (instanceId: string, axis: ResizeAxis, delta: number, minSize: { w: number; h: number }) => {
    applyGrid(
      layout.grid.map((c) => (c.i === instanceId ? resizeCell(c, axis, delta, GRID_COLUMNS_COUNT, minSize) : c)),
    );
  };

  const handleAddPanel = (definition: PanelDefinition) => {
    const instanceId = `${definition.type}-${crypto.randomUUID()}`;
    const y = layout.grid.reduce((max, cell) => Math.max(max, cell.y + cell.h), 0);
    openPanel(
      { instanceId, type: definition.type, collapsed: false, settings: {} },
      { i: instanceId, x: 0, y, w: definition.defaultSize.w, h: definition.defaultSize.h },
    );
  };

  const minSizeByInstanceId = Object.fromEntries(
    renderable
      .map((panel): [string, { w: number; h: number } | undefined] => [
        panel.instanceId,
        getPanelDefinition(panel.type)?.minSize,
      ])
      .filter((entry): entry is [string, { w: number; h: number }] => entry[1] !== undefined),
  );

  return (
    <div className="flex h-full flex-col bg-slate-void text-ink-primary">
      {recovered && (
        <div
          role="alert"
          className="flex flex-shrink-0 items-center justify-between gap-3 border-b border-signal-warn/40 bg-signal-warn/10 px-3 py-2 font-mono text-xs text-signal-warn"
        >
          <span>저장된 배치를 읽지 못해 기본 배치로 열었습니다.</span>
          <button type="button" onClick={dismissRecovered} className="underline hover:no-underline">
            닫기
          </button>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <SymbolSidebar />

        <div className="flex min-h-0 flex-1 flex-col">
          <div className="flex flex-shrink-0 items-center justify-end border-b border-slate-line px-2 py-1.5">
            <PanelPicker panels={layout.panels} onAdd={handleAddPanel} />
          </div>

          <div className="min-h-0 flex-1">
            {renderable.length === 0 ? (
              <div
                role="status"
                className="flex h-full flex-col items-center justify-center gap-1 text-sm text-ink-muted"
              >
                <p>열린 패널이 없습니다.</p>
                <p className="text-xs">위 "패널 추가"에서 열어보세요.</p>
              </div>
            ) : (
              <PanelGrid
                cells={renderableCells}
                onCellsChange={handleCellsChange}
                minSizeByInstanceId={minSizeByInstanceId}
              >
                {(cell) => {
                  const instance = renderable.find((p) => p.instanceId === cell.i);
                  const definition = instance ? getPanelDefinition(instance.type) : undefined;
                  if (!instance || !definition) return null;
                  return (
                    <PanelSlot
                      instance={instance}
                      definition={definition}
                      region={region}
                      onMove={(direction) => handleMove(instance.instanceId, direction)}
                      onResize={(axis, delta) => handleResize(instance.instanceId, axis, delta, definition.minSize)}
                      onToggleCollapse={() => toggleCollapsed(instance.instanceId)}
                      onClose={() => closePanel(instance.instanceId)}
                      onSettingsChange={(next) => updateSettings(instance.instanceId, next)}
                    />
                  );
                }}
              </PanelGrid>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
