export interface PanelInstance {
  instanceId: string;
  type: string;
  collapsed: boolean;
  settings: Record<string, unknown>;
}

export interface GridCell {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface TerminalLayout {
  schemaVersion: number;
  panels: PanelInstance[];
  grid: GridCell[];
}
