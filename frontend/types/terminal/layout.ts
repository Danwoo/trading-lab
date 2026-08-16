export interface PanelInstance {
  instanceId: string;
  type: string;
  collapsed: boolean;
  settings: Record<string, unknown>;
}

/**
 * 저장되는 것은 **무엇이 열려 있는가**뿐이다 — 어디에 어떤 크기로 놓였는지는 화면이 정한다
 * (화면 결정 §20.2 「패널은 모달이 아니다 … 옆으로 민다」). 좌표 배열(`grid`)은 스키마 v2 에서
 * 사라졌고 `layoutSchema.ts` 의 마이그레이션이 옛 저장본에서 그것을 떼어낸다.
 */
export interface TerminalLayout {
  schemaVersion: number;
  panels: PanelInstance[];
}
