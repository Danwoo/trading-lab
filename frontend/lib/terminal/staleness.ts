import { formatDate } from "@/utils/common/formatters/date";

/**
 * 적재본이 며칠 낡았나 — 화면 결정 §21.5 「절대 안 하는 것: 조용히 낡은 값으로 계속 굴리는 것」의
 * 계산부다. 낡음을 재는 자리를 화면마다 따로 두면 화면마다 다른 기준으로 낡음을 판정하게 된다.
 *
 * 시각이 아니라 **달력 날짜**로 잰다. 「08-06 장 마감분」과 「08-07 새벽 적재분」의 시각 차이는
 * 몇 시간이지만 시세로서는 하루가 다르고, 사람이 읽는 배지도 「하루 낡음」이다.
 */
export interface StalenessNote {
  /** 달력 기준 지난 날수. 1 이상일 때만 만들어진다 */
  days: number;
  /** 배지에 그대로 쓰는 한 줄 — 「하루 낡음」 · 「9일 낡음」 */
  label: string;
}

const DAY_MS = 86_400_000;

/**
 * 달력 하루를 UTC 자정 epoch 로 정규화한다. 두 값 모두 같은 표시 타임존(사용자 타임존)에서
 * 뽑은 뒤 비교하므로, 일광절약·시차가 끼어도 「며칠 전인가」는 흔들리지 않는다.
 */
function calendarDayMs(value: string | number): number | null {
  const day = formatDate(value, "date");
  if (day === null) return null;
  const [year, month, date] = day.split("-").map(Number);
  return Date.UTC(year, month - 1, date);
}

/**
 * `asOf` 가 오늘이면 `null` — 낡지 않은 것에는 배지를 달지 않는다.
 * 기준 시각을 모르면(`asOf === null`) 낡음도 모른다. **모르는 것을 「최신」으로 읽지 않는다** —
 * 호출자가 그 갈래를 따로 다뤄야 한다(`null` 은 「낡지 않음」이 아니라 「판정 대상이 아님」이다).
 */
export function describeStaleness(asOf: string | null, nowMs: number): StalenessNote | null {
  if (!asOf) return null;

  const at = calendarDayMs(asOf);
  const now = calendarDayMs(nowMs);
  if (at === null || now === null) return null;

  const days = Math.round((now - at) / DAY_MS);
  // 미래 날짜(days < 0)도 낡지 않았다 — 시계가 어긋난 것이지 데이터가 낡은 것이 아니다.
  if (days <= 0) return null;

  return { days, label: days === 1 ? "하루 낡음" : `${days}일 낡음` };
}

/** 배지에 쓰는 「08-06」 — 연도는 뺀다(같은 줄에 늘 오늘이 함께 읽힌다). */
export function formatAsOfDay(asOf: string): string | null {
  const day = formatDate(asOf, "date");
  return day === null ? null : day.slice(5);
}
