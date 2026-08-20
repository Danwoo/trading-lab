/**
 * 숫자 표기의 로케일을 브라우저에 맡기지 않는다 — 맡기면 같은 값이 기계마다 `1.000,5`·`1,000.5`
 * 로 갈린다(#282 의 날짜판과 같은 결함). 리포트·입력 칸이 쓰는 `toLocaleString("ko-KR")` 과
 * 같은 규칙으로 묶는다.
 */
const LOCALE = "ko-KR";

export const formatNumber = (
  val: unknown,
  type: "number" | "currency" | "percent" | "decimal" = "number",
  options?: {
    decimals?: number;
    currency?: string;
  },
): string => {
  if (typeof val !== "number" && typeof val !== "string") {
    return "";
  }

  const num = Number(val);
  if (isNaN(num)) return "";

  const decimals = options?.decimals ?? 2;

  switch (type) {
    case "currency": {
      const currency = options?.currency ?? "KRW";
      return new Intl.NumberFormat(LOCALE, {
        style: "currency",
        currency: currency,
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      }).format(num);
    }

    case "percent":
      return new Intl.NumberFormat(LOCALE, {
        style: "percent",
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      }).format(num / 100);

    case "decimal":
      return new Intl.NumberFormat(LOCALE, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      }).format(num);

    case "number":
    default:
      return new Intl.NumberFormat(LOCALE).format(num);
  }
};
