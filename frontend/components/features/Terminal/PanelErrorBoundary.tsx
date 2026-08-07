"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  panelTitle: string;
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * 패널 하나가 던져도 화면 전체가 죽지 않는다 (설계 §3.5). 클래스 컴포넌트인 이유는
 * React 가 아직 `componentDidCatch`/`getDerivedStateFromError` 를 훅으로 주지 않기 때문이다.
 */
export class PanelErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[Terminal] 패널 "${this.props.panelTitle}" 렌더 실패`, error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div role="alert" className="flex h-full flex-col items-center justify-center gap-1 px-4 text-center">
          <p className="text-sm text-ink-primary">{this.props.panelTitle} 패널을 표시할 수 없습니다.</p>
          <p className="text-xs text-ink-muted">{this.state.error.message}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
