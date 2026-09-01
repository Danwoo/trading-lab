/** 칸 클릭 → 리포트 갱신의 예산 (실험대 스펙 §5). */
export const REPORT_BUDGET_MS = 500;

/**
 * 갱신 시간 한 줄. 예산을 넘겼을 때 **그게 무슨 뜻이고 다음엔 어떻게 되는지**까지 말한다 —
 * 넘긴 숫자만 적어 두면 화면이 자기 예산 초과를 기록만 하고 아무 일도 안 하는 셈이다
 * (실측: 첫 조회 1,063~1,287ms, 같은 칸 재클릭 0ms 캐시).
 */
export function reportTimingLine(ms: number): string {
  const budget = `예산 ${REPORT_BUDGET_MS}ms (스펙 §5)`;
  if (ms === 0) return `칸 클릭 → 갱신 0ms (캐시) — ${budget}`;
  if (ms <= REPORT_BUDGET_MS) return `칸 클릭 → 갱신 ${ms}ms — ${budget}`;
  return `칸 클릭 → 갱신 ${ms}ms — ${budget}를 넘겼습니다. 처음 여는 칸은 서버에서 읽어 오는 시간이고, 같은 칸은 다시 누르면 캐시로 바로 뜹니다.`;
}
