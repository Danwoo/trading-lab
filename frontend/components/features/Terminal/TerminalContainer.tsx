"use client";

import { useEffect, useMemo } from "react";
import { useSessionContext } from "@/hooks/shared/useSessionContext";
import { useTerminalRegion } from "@/hooks/terminal/useTerminalContext";
import { useLayoutStore } from "@/stores/terminal/layoutStore";
import { pruneUnknownPanels } from "@/lib/terminal/layoutSchema";
import { getPanelDefinition, listPanelDefinitions } from "@/lib/terminal/panelRegistry";
import { DEFAULT_LAYOUT } from "@/lib/terminal/layoutDefaults";
import {
  DEFAULT_MARKET_COLOR_PRESET,
  applyMarketColorPreset,
  readStoredMarketColorPreset,
} from "@/lib/terminal/marketColorPreset";
import { PanelSlot } from "./PanelSlot";
import { SymbolSidebar } from "./SymbolSidebar";

/**
 * 「시세」 화면의 셸 — 문맥·레이아웃 스토어를 여는 유일한 곳(다른 컴포넌트는 `contextActions`/
 * `contextStore` 를 직접 import 하지 않는다). 저장 레이아웃 복원은 렌더 중이 아니라 이 마운트
 * 이펙트에서 `setWorkspace()` 로 한다.
 *
 * **패널을 사람이 옮기고 키우지 않는다**(화면 결정 §20.2, 자유 배치 철거). 놓이는 자리는
 * 화면이 정하고, 저장되는 것은 「무엇이 열려 있는가」뿐이다.
 */
export function TerminalContainer() {
  const { workspaceId: sessionWorkspaceId, isLoaded } = useSessionContext();
  const setWorkspace = useLayoutStore((s) => s.setWorkspace);
  const layout = useLayoutStore((s) => s.layout);
  const recovered = useLayoutStore((s) => s.recovered);
  const toggleCollapsed = useLayoutStore((s) => s.toggleCollapsed);
  const closePanel = useLayoutStore((s) => s.closePanel);
  const resetPanels = useLayoutStore((s) => s.resetPanels);
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

  const defaultInstanceIds = DEFAULT_LAYOUT.panels.map((panel) => panel.instanceId);
  const openInstanceIds = new Set(layout.panels.map((panel) => panel.instanceId));
  const hasClosedDefaultPanel = defaultInstanceIds.some((id) => !openInstanceIds.has(id));

  const resetButton = (
    <button
      type="button"
      onClick={resetPanels}
      className="border border-slate-line px-2 py-1 font-mono text-xs text-ink-primary hover:bg-slate-line focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ink-muted"
    >
      기본 패널 되살리기
    </button>
  );

  return (
    <div className="flex h-full flex-col bg-slate-void text-ink-primary">
      {recovered && (
        <div
          role="alert"
          className="flex flex-shrink-0 items-center justify-between gap-3 border-b border-signal-warn/40 bg-signal-warn/10 px-3 py-2 font-mono text-xs text-signal-warn"
        >
          <span>저장된 패널 구성을 읽지 못해 기본 구성으로 열었습니다.</span>
          <button type="button" onClick={dismissRecovered} className="underline hover:no-underline">
            닫기
          </button>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <SymbolSidebar />

        <div className="flex min-h-0 flex-1 flex-col">
          {hasClosedDefaultPanel && (
            <div className="flex flex-shrink-0 items-center justify-end border-b border-slate-line px-2 py-1.5">
              {resetButton}
            </div>
          )}

          <div className="min-h-0 flex-1 overflow-auto">
            {renderable.length === 0 ? (
              <div
                role="status"
                className="flex h-full flex-col items-center justify-center gap-2 text-sm text-ink-muted"
              >
                <p>열린 패널이 없습니다.</p>
                {resetButton}
              </div>
            ) : (
              <div className="grid min-h-full auto-rows-[minmax(20rem,1fr)] gap-2 p-2 xl:grid-cols-2">
                {renderable.map((instance) => {
                  const definition = getPanelDefinition(instance.type);
                  if (!definition) return null;
                  return (
                    <PanelSlot
                      key={instance.instanceId}
                      instance={instance}
                      definition={definition}
                      region={region}
                      onToggleCollapse={() => toggleCollapsed(instance.instanceId)}
                      onClose={() => closePanel(instance.instanceId)}
                      onSettingsChange={(next) => updateSettings(instance.instanceId, next)}
                    />
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
