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
      return new Intl.NumberFormat(undefined, {
        style: "currency",
        currency: currency,
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      }).format(num);
    }

    case "percent":
      return new Intl.NumberFormat(undefined, {
        style: "percent",
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      }).format(num / 100);

    case "decimal":
      return new Intl.NumberFormat(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      }).format(num);

    case "number":
    default:
      return new Intl.NumberFormat().format(num);
  }
};
