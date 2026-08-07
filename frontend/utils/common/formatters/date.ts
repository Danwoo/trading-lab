/**
 * 일반 표시용 날짜·시각 포맷터.
 *
 * **표시 타임존 정책 — 사용자 타임존** (결정 2026-07-30, CONTEXT.md 결정 로그 / #263).
 * `date`·`datetime`·`time` 세 모드 모두 `options.timeZone` 이 없으면 런타임 기본
 * 타임존으로 렌더한다 — 브라우저에서는 사용자의 OS 타임존이다. 같은 인스턴트를 보는
 * 사용자는 각자 자기 시계와 맞는 시각을 본다.
 *
 * **경계 — 시세 차트의 시간축은 이 포맷터의 대상이 아니다.**
 * 캔들·시세 차트의 시간축은 관례상 **시장 시각**으로 고정한다 (한국 장 09:00 캔들은
 * 어디서 보든 09:00 이어야 한다). 차트 축·툴팁을 만들 때 이 포맷터의 기본값을 무심코
 * 상속하지 말고, 시장 타임존을 `options.timeZone` 에 명시하거나 차트 전용 포맷터를 쓴다.
 */

export type DateFormatType = "date" | "datetime" | "time";

export interface FormatDateOptions {
  /**
   * 표시 타임존. 기본값은 **사용자 타임존**(런타임 기본 타임존).
   * IANA 타임존 이름을 주면 그 타임존으로 변환해 표시한다 (예: 시장 시각 `"Asia/Seoul"`).
   */
  timeZone?: string;
}

const DATE_FIELDS: Intl.DateTimeFormatOptions = {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
};

// hourCycle "h23" — hour12:false 는 런타임에 따라 자정을 "24" 로 낼 여지가 있어 명시한다.
const TIME_FIELDS: Intl.DateTimeFormatOptions = {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
};

/**
 * 주어진 타임존에서 본 달력 필드를 뽑아 조회 함수로 돌려준다.
 * `timeZone` 이 undefined 면 Intl 이 런타임 기본 타임존(= 사용자 타임존)을 쓴다.
 */
const partsIn = (date: Date, timeZone: string | undefined, fields: Intl.DateTimeFormatOptions) => {
  const parts = new Intl.DateTimeFormat("sv-SE", { timeZone, ...fields }).formatToParts(date);
  return (type: Intl.DateTimeFormatPartTypes) => parts.find((p) => p.type === type)?.value ?? "";
};

export const formatDate = (value: any, type: DateFormatType, options: FormatDateOptions = {}) => {
  if (!value) return null;

  const date = new Date(value);

  // 유효한 날짜인지 확인
  if (isNaN(date.getTime())) {
    return null;
  }

  const { timeZone } = options;

  switch (type) {
    case "datetime": {
      const get = partsIn(date, timeZone, { ...DATE_FIELDS, ...TIME_FIELDS });
      return `${get("year")}-${get("month")}-${get("day")} ${get("hour")}:${get("minute")}:${get("second")}`;
    }
    case "time": {
      const get = partsIn(date, timeZone, TIME_FIELDS);
      return `${get("hour")}:${get("minute")}:${get("second")}`;
    }
    // default 는 DateFormatType 상 도달 불가하지만, 타입 없는 호출이 닿을 때도
    // 같은 타임존 정책을 따르도록 "date" 와 한 갈래로 둔다.
    case "date":
    default: {
      const get = partsIn(date, timeZone, DATE_FIELDS);
      return `${get("year")}-${get("month")}-${get("day")}`;
    }
  }
};
