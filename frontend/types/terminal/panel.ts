import type * as React from "react";
import type { PanelCapability } from "./capability";

export interface PanelProps {
  instanceId: string;
  settings: Record<string, unknown>;
  onSettingsChange: (next: Record<string, unknown>) => void;
}

export interface PanelDefinition {
  type: string;
  title: string;
  capability: PanelCapability;
  needsSymbol: boolean;
  defaultSize: { w: number; h: number };
  minSize: { w: number; h: number };
  load: () => Promise<{ default: React.ComponentType<PanelProps> }>;
}
