import { addHours, addDays } from "date-fns";
export { addHours, addDays };

/**
 * 날짜 문자열('YYYY-MM-DD')을 그날 끝 'YYYY-MM-DD 23:59:59' 으로 변환
 */
export function toEndOfDay(dateStr: string): string {
  return `${dateStr} 23:59:59`;
}

/**
 * KST 시간을 Unix timestamp로 변환
 * @param date 선택적, 기준 날짜. 없으면 현재 시간 기준
 */
export function getKSTTimestamp(date?: Date): number {
  const baseDate = date ?? new Date();
  return Math.floor(addHours(baseDate, 9).getTime() / 1000);
}

/**
 * KST 기준 벽시계 시각을 반환한다 — **저장(reg_dt·mod_dt 등 인스턴트 컬럼)에는 쓰지 않는다.**
 *
 * 반환값은 "진짜 인스턴트에 +9h 를 더한 가짜 Date" 다 — `getUTCHours()` 등으로 KST 필드값을
 * 읽어내는 용도(예: 파일명 타임스탬프, `hooks/shared/tableExport.ts`·`useExcelExport.ts`)에만
 * 쓴다. DB 에 저장하면 그 순간 인스턴트가 9시간 밀린다 — #303 에서 이 함수가 `reg_dt`/`mod_dt`
 * 쓰기 경로에 쓰여 전 관리 화면 타임스탬프가 뒤틀렸던 사고가 났다. 저장은 항상 `new Date()`.
 * @param date 선택적, 기준 날짜. 없으면 현재 시간 기준
 */
export function getKSTTime(date?: Date): Date {
  const baseDate = date ?? new Date();
  return addHours(baseDate, 9);
}
