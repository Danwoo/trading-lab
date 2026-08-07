/**
 * 공통 Dashboard 컴포넌트를 위한 타입 정의
 */

// 시계열 데이터의 기본 구조
export interface TimeSeriesDataPoint {
  timestamp: string;
  [key: string]: string | number | boolean | null | undefined;
}

// 차트 시리즈 설정
export interface ChartSeriesConfig {
  key: string; // 데이터 키
  name: string; // 표시 이름
  color: string; // 색상
  unit: string; // 단위
  yAxisName: string; // Y축 이름
  decimals?: number; // 소수점 자릿수
  axisLabelDecimals?: number; // Y축 라벨 소수점 자릿수
  // 관리선(markLine). upl/lpl 은 각각 독립적 — 한쪽만 주면 그 선만 그린다
  // (예: drawdown 은 하한 경보선만 필요). 0 도 유효한 값으로 그린다.
  limits?: {
    upl?: number; // 상단선 값 (Upper Process Limit). 생략 시 상단선 미표시
    lpl?: number; // 하단선 값 (Lower Process Limit). 생략 시 하단선 미표시
    uplColor?: string; // 상단선 의미색 (기본 빨강). 지표에 맞게 지정
    lplColor?: string; // 하단선 의미색 (기본 파랑). 지표에 맞게 지정
    uplLabel?: string; // 상단선 라벨 (기본 "U"). 색만이 아닌 텍스트로 의미 병기
    lplLabel?: string; // 하단선 라벨 (기본 "L")
  };
}

// 카드 설정
export interface CardConfig {
  key: string; // 데이터 키
  label: string; // 표시 라벨
  unit: string; // 단위
  colorClass: string; // Tailwind CSS 색상 클래스
  decimals?: number; // 소수점 자릿수
  bgClass?: string; // 배경 색상 클래스
}

// 시간 범위 프리셋
export interface TimeRangePreset {
  label: string;
  minutes: number; // 0이면 직접 입력 모드
}

// 차트 옵션
export interface ChartOptions {
  height?: number | string;
  initialVisibleHours?: number;
  animationEnabled?: boolean;
  showSymbol?: boolean;
  tooltipHeaderFormatter?: (axisValue: number) => string;
  xAxisLabelRotate?: number;
  xAxisLabelFormatter?: string | ((value: number) => string);
  xAxisMaxInterval?: number;
  xAxisMin?: number;
  xAxisMax?: number;
  xAxisType?: "time" | "value";
  renderer?: "canvas" | "svg";
}

// 로그 옵션
export interface LogOptions {
  height?: number | string;
  reverseOrder?: boolean; // 최신 데이터를 위에 표시
}
